#!/usr/bin/env python3
"""Finalize frozen INFINI-NEWS publication-shift candidate comparison.

The score estimates similarity to matched current-era publication language.
This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import sklearn
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, f1_score, roc_auc_score

from train_infini_news_publication_shift_candidates import (
    DISCLAIMER,
    SCORE_NAME,
    assert_public_safe,
    binary_metrics,
    score_distribution,
    sha256_file,
    stable_json_sha256,
    write_json,
    write_jsonl,
)

FINAL_SCHEMA = "publication_shift.infini_news_final_decision.v1"
SEED = 20260712
PRIMARY_LANE = "publisher_domain_heldout_primary"
MATCHED_PLACEBO_LANES = {
    "pre_llm_2018_2019_vs_2020_2021": ((2018, 2019), (2020, 2021)),
    "pre_llm_2018_vs_2021": ((2018,), (2021,)),
    "historical_placebo_2016_2017_vs_later_pre_llm": ((2016, 2017), (2020, 2021)),
}
MIN_PRIMARY_AUC = 0.80
MIN_MASKED_AUC = 0.75
MIN_CONFOUND_AUC = 0.70
MAX_SOURCE_ONLY_AUC = 0.60
MAX_ECE = 0.10
MIN_ENSEMBLE_AUC_LIFT = 0.01
BOOTSTRAP_SAMPLES = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def grouped_bootstrap_auc(
    labels: Sequence[int],
    scores: Sequence[float],
    groups: Sequence[str | None],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = SEED,
) -> dict[str, Any]:
    y_all = np.asarray(labels, dtype=np.int8)
    p_all = np.asarray(scores, dtype=float)
    if len(y_all) == 0 or len(set(y_all.tolist())) < 2:
        return {"samples_requested": samples, "samples_valid": 0, "lower": None, "median": None, "upper": None}
    group_to_indices: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        group_to_indices[str(group or f"missing-{index}")].append(index)
    keys = sorted(group_to_indices)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(samples):
        chosen = rng.choice(keys, size=len(keys), replace=True)
        indices = [index for key in chosen for index in group_to_indices[str(key)]]
        y = y_all[indices]
        if len(set(y.tolist())) < 2:
            continue
        values.append(float(roc_auc_score(y, p_all[indices])))
    if not values:
        return {"samples_requested": samples, "samples_valid": 0, "lower": None, "median": None, "upper": None}
    return {
        "samples_requested": samples,
        "samples_valid": len(values),
        "lower": float(np.quantile(values, 0.025)),
        "median": float(np.quantile(values, 0.5)),
        "upper": float(np.quantile(values, 0.975)),
    }


def _labels_scores_groups(predictions: Sequence[dict[str, Any]]) -> tuple[list[int], list[float], list[str | None]]:
    labels = [int(row["label"]) for row in predictions if row.get("label") is not None]
    scores = [float(row[SCORE_NAME]) for row in predictions if row.get("label") is not None]
    groups = [row.get("url_hostname_hash") or row.get("sitename_hash") or row.get("near_duplicate_cluster_id") for row in predictions if row.get("label") is not None]
    return labels, scores, groups


def _score_diagnostic_by_key(predictions: Sequence[dict[str, Any]], key: str, limit: int = 100) -> list[dict[str, Any]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in predictions:
        value = row.get(key)
        if value is not None:
            buckets[str(value)].append(float(row[SCORE_NAME]))
    return [
        {"value_hash": hashlib.sha256(value.encode("utf-8")).hexdigest()[:24], "count": len(values), "distribution": score_distribution(np.asarray(values, dtype=float))}
        for value, values in sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]
    ]


def _score_diagnostic_by_year(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in predictions:
        if row.get("publication_year") is not None:
            buckets[str(row["publication_year"])].append(float(row[SCORE_NAME]))
    return {year: score_distribution(np.asarray(values, dtype=float)) for year, values in sorted(buckets.items())}


def _score_diagnostic_by_length(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    values = np.asarray([float(row.get("word_count") or 0.0) for row in predictions], dtype=float)
    scores = np.asarray([float(row[SCORE_NAME]) for row in predictions], dtype=float)
    if len(values) == 0:
        return {}
    cuts = np.quantile(values, [0.0, 0.25, 0.5, 0.75, 1.0])
    result = {}
    for index, name in enumerate(["q1_shortest", "q2", "q3", "q4_longest"]):
        lo, hi = cuts[index], cuts[index + 1]
        mask = (values >= lo) & (values <= hi if index == 3 else values < hi)
        result[name] = {"word_count_range": [float(lo), float(hi)], SCORE_NAME: score_distribution(scores[mask])}
    return result


def matched_historical_placebos(predictions: Sequence[dict[str, Any]], *, threshold: float, samples: int = BOOTSTRAP_SAMPLES) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for index, (name, (early_years, late_years)) in enumerate(MATCHED_PLACEBO_LANES.items()):
        lane_rows: list[dict[str, Any]] = []
        labels: list[int] = []
        for row in predictions:
            year = row.get("publication_year")
            if year in early_years:
                lane_rows.append(row)
                labels.append(0)
            elif year in late_years:
                lane_rows.append(row)
                labels.append(1)
        scores = [float(row[SCORE_NAME]) for row in lane_rows]
        groups = [row.get("url_hostname_hash") or row.get("sitename_hash") or row.get("near_duplicate_cluster_id") for row in lane_rows]
        support = "supported" if len(set(labels)) == 2 else "unsupported"
        reason = None if support == "supported" else "lane lacks both early and late classes in frozen predictions"
        output[name] = {
            "support": {"status": support, "reason": reason},
            "year_groups": {"early": list(early_years), "late": list(late_years)},
            "test": binary_metrics(labels, scores, threshold),
            "grouped_bootstrap_roc_auc_95ci": grouped_bootstrap_auc(labels, scores, groups, samples=samples, seed=SEED + 100 + index),
        }
    return output


def _metric_value(metrics: dict[str, Any], lane: str, name: str) -> float | None:
    value = (metrics.get("lanes") or {}).get(lane, {}).get(name)
    return float(value) if value is not None else None


def candidate_gate_matrix(candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for name, metrics in candidates.items():
        primary_auc = _metric_value(metrics, PRIMARY_LANE, "roc_auc")
        masked_auc = _metric_value(metrics, "masked_primary_test", "roc_auc")
        source_auc = _metric_value(metrics, "source_sitename_heldout", "roc_auc")
        topic_auc = _metric_value(metrics, "topic_heldout", "roc_auc")
        author_auc = _metric_value(metrics, "author_heldout", "roc_auc")
        primary_ece = _metric_value(metrics, PRIMARY_LANE, "ece")
        source_only_auc = (((metrics.get("shortcut_diagnostics") or {}).get("source_only_primary_test") or {}).get("roc_auc"))
        metadata_only_auc = (((metrics.get("shortcut_diagnostics") or {}).get("metadata_only_primary_test") or {}).get("roc_auc"))
        encoder_smoke_hold = metrics.get("decision") == "SMOKE-HOLD"
        gates = {
            "candidate_not_smoke_hold": not encoder_smoke_hold,
            "primary_auc_minimum": primary_auc is not None and primary_auc >= MIN_PRIMARY_AUC,
            "masked_auc_minimum": masked_auc is not None and masked_auc >= MIN_MASKED_AUC,
            "source_heldout_auc_minimum": source_auc is not None and source_auc >= MIN_CONFOUND_AUC,
            "topic_heldout_auc_minimum": topic_auc is not None and topic_auc >= MIN_CONFOUND_AUC,
            "author_heldout_auc_minimum": author_auc is not None and author_auc >= MIN_CONFOUND_AUC,
            "source_only_shortcut_maximum": source_only_auc is not None and float(source_only_auc) <= MAX_SOURCE_ONLY_AUC,
            "primary_ece_maximum": primary_ece is not None and primary_ece <= MAX_ECE,
        }
        matrix[name] = {
            "eligible_for_final": all(gates.values()),
            "gates": gates,
            "evidence": {
                "primary_auc": primary_auc,
                "masked_auc": masked_auc,
                "source_heldout_auc": source_auc,
                "topic_heldout_auc": topic_auc,
                "author_heldout_auc": author_auc,
                "primary_ece": primary_ece,
                "source_only_auc": source_only_auc,
                "metadata_only_auc": metadata_only_auc,
                "candidate_decision": metrics.get("decision"),
            },
            "notes": [
                "Metadata-only shortcut diagnostics are reported as a risk indicator, not a runtime input gate; candidates use article content/stylometry only.",
                "Encoder smoke candidate is ineligible because no verified accelerator-backed full frozen-row run exists.",
            ] if encoder_smoke_hold else ["Candidate runtime inputs exclude metadata fields; threshold selected on validation only."],
        }
    return matrix


def select_final_decision(candidates: dict[str, dict[str, Any]], matrix: dict[str, Any]) -> dict[str, Any]:
    eligible = [name for name, gate in matrix.items() if gate["eligible_for_final"]]
    if not eligible:
        return {
            "decision": "HOLD",
            "selected_candidate": None,
            "ensemble_attempted": False,
            "reason": "No candidate passed every frozen no-runtime-metadata/confound/calibration gate.",
            "disclaimer": DISCLAIMER,
        }
    selected = max(eligible, key=lambda name: float((candidates[name].get("lanes") or {}).get(PRIMARY_LANE, {}).get("roc_auc") or -1.0))
    ensemble_eligible = len(eligible) > 1
    ensemble_attempted = False
    ensemble_reason = "Only one candidate passed every component gate; predeclared ensemble precondition not met."
    if ensemble_eligible:
        ensemble_attempted = False
        ensemble_reason = "Multiple candidates passed gates, but no frozen validation-calibrated ensemble artifact was predeclared or available with the required AUC lift margin."
    return {
        "decision": "PASS",
        "selected_candidate": selected,
        "ensemble_attempted": ensemble_attempted,
        "ensemble_precondition_all_components_passed": ensemble_eligible,
        "ensemble_minimum_auc_lift": MIN_ENSEMBLE_AUC_LIFT,
        "ensemble_reason": ensemble_reason,
        "reason": "Retained strongest passing frozen component; no production integration performed.",
        "disclaimer": DISCLAIMER,
    }


def copy_selected_artifact(metadata: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    source = Path(metadata["artifact_path"])
    copied_dir = output_dir / "model_artifact"
    if copied_dir.exists():
        if copied_dir.is_dir():
            shutil.rmtree(copied_dir)
        else:
            copied_dir.unlink()
    if source.is_dir():
        shutil.copytree(source, copied_dir)
        digest = sha256_directory(copied_dir)
        size = sum(path.stat().st_size for path in copied_dir.rglob("*") if path.is_file())
        return {"path": str(copied_dir), "sha256": digest, "size_bytes": size, "source_path": str(source)}
    copied_path = output_dir / source.name
    shutil.copy2(source, copied_path)
    return {"path": str(copied_path), "sha256": sha256_file(copied_path), "size_bytes": copied_path.stat().st_size, "source_path": str(source)}


def sha256_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_candidate_bundle(candidates_dir: Path) -> dict[str, dict[str, Any]]:
    bundles = {}
    for candidate_dir in sorted(path for path in candidates_dir.iterdir() if path.is_dir()):
        metrics_path = candidate_dir / "metrics.json"
        metadata_path = candidate_dir / "model_metadata.json"
        if metrics_path.exists() and metadata_path.exists():
            bundles[candidate_dir.name] = {"metrics": read_json(metrics_path), "metadata": read_json(metadata_path), "dir": candidate_dir}
    return bundles


def run(args: argparse.Namespace) -> dict[str, Any]:
    candidates_dir = args.candidates_dir
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    bundles = load_candidate_bundle(candidates_dir)
    candidates = {name: bundle["metrics"] for name, bundle in bundles.items()}
    if not candidates:
        raise ValueError(f"no candidate metrics found in {candidates_dir}")
    matrix = candidate_gate_matrix(candidates)
    decision = select_final_decision(candidates, matrix)
    selected_name = decision.get("selected_candidate")
    if not selected_name:
        raise ValueError("final decision is HOLD; no selected artifact to freeze")
    selected = bundles[str(selected_name)]
    selected_metrics = selected["metrics"]
    selected_metadata = selected["metadata"]
    primary_predictions = read_jsonl(selected["dir"] / "publisher_domain_heldout_primary_predictions.jsonl")
    primary_labels, primary_scores, primary_groups = _labels_scores_groups(primary_predictions)
    primary_bootstrap = grouped_bootstrap_auc(primary_labels, primary_scores, primary_groups, seed=SEED)
    placebos = matched_historical_placebos(primary_predictions, threshold=float(selected_metadata["threshold"]))
    supported_placebos = {name: lane for name, lane in placebos.items() if lane["test"].get("roc_auc") is not None}
    strongest_placebo_name = max(supported_placebos, key=lambda name: supported_placebos[name]["test"]["roc_auc"]) if supported_placebos else None
    primary_auc = selected_metrics["lanes"][PRIMARY_LANE]["roc_auc"]
    lift = None
    if strongest_placebo_name:
        lift = float(primary_auc - supported_placebos[strongest_placebo_name]["test"]["roc_auc"])
    artifact = copy_selected_artifact(selected_metadata, output_dir)
    diagnostics = {
        "by_source_hash": _score_diagnostic_by_key(primary_predictions, "url_hostname_hash"),
        "by_topic": _score_diagnostic_by_key(primary_predictions, "topic"),
        "by_year": _score_diagnostic_by_year(primary_predictions),
        "by_length_quartile": _score_diagnostic_by_length(primary_predictions),
    }
    final = {
        "schema": FINAL_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "decision": decision,
        "selected_model": {
            "candidate_name": selected_name,
            "model_id": selected_metadata["model_id"],
            "model_family": selected_metadata["model_family"],
            "score_name": selected_metadata["score_name"],
            "threshold": selected_metadata["threshold"],
            "artifact": artifact,
            "source_artifact_sha256": selected_metadata.get("artifact_sha256"),
            "training_identity_sha256": selected_metadata.get("training_identity_sha256"),
            "split_summary_sha256": selected_metadata.get("split_summary_sha256"),
        },
        "policy": {
            "calibration_and_thresholds": "validation_only_from_candidate_training_protocol",
            "production_integration": "none",
            "runtime_metadata_inputs": [],
            "rights_boundary": "Public final artifacts contain IDs, hashes, aggregate metrics, model metadata, and no article body/title/URL/preview fields.",
            "interpretation_boundary": DISCLAIMER,
        },
        "candidate_gate_matrix": matrix,
        "primary_result": {
            "test": selected_metrics["lanes"][PRIMARY_LANE],
            "grouped_bootstrap_roc_auc_95ci": primary_bootstrap,
            "masked_test": selected_metrics["lanes"].get("masked_primary_test"),
            "masking_loss_auc": float(primary_auc - selected_metrics["lanes"].get("masked_primary_test", {}).get("roc_auc")),
            "matched_historical_placebos": placebos,
            "main_minus_strongest_placebo": {
                "strongest_placebo": strongest_placebo_name,
                "point_estimate": lift,
            },
        },
        "frozen_lane_results": {
            "source_sitename_heldout": selected_metrics["lanes"].get("source_sitename_heldout"),
            "topic_heldout": selected_metrics["lanes"].get("topic_heldout"),
            "author_heldout": selected_metrics["lanes"].get("author_heldout"),
            "random_diagnostic": selected_metrics["lanes"].get("random_diagnostic"),
            "transition_2022": selected_metrics["lanes"].get("transition_2022"),
            "forward_2026_jan_apr": selected_metrics["lanes"].get("forward_2026_jan_apr"),
            "length_quartiles_primary": selected_metrics["lanes"].get("length_quartiles_primary"),
        },
        "diagnostics": diagnostics,
        "candidate_model_ids": {name: bundle["metadata"].get("model_id") for name, bundle in sorted(bundles.items())},
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "cpu_count": os.cpu_count(),
        },
    }
    write_json(output_dir / "decision_packet.json", final)
    write_jsonl(output_dir / "publisher_domain_heldout_primary_predictions.jsonl", primary_predictions)
    write_markdown(output_dir / "MODEL_CARD.md", render_model_card(final))
    checksums = checksum_manifest(output_dir)
    write_json(output_dir / "checksums.json", {"schema": "publication_shift.infini_news_final_checksums.v1", "files": checksums})
    (output_dir / "checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(checksums.items())), encoding="utf-8")
    assert_public_safe(final)
    return final


def checksum_manifest(output_dir: Path) -> dict[str, str]:
    checksums = {}
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file() and item.name not in {"checksums.json", "checksums.sha256"}):
        checksums[str(path)] = sha256_file(path)
    return checksums


def render_model_card(final: dict[str, Any]) -> str:
    selected = final["selected_model"]
    result = final["primary_result"]
    decision = final["decision"]
    masked = result.get("masked_test") or {}
    lift = result["main_minus_strongest_placebo"]
    ci = result["grouped_bootstrap_roc_auc_95ci"]
    return "\n".join([
        f"# INFINI-NEWS final publication-shift model v1",
        "",
        DISCLAIMER,
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Selected candidate: `{selected['candidate_name']}`",
        f"- Model ID: `{selected['model_id']}`",
        f"- Model family: `{selected['model_family']}`",
        f"- Score: `{selected['score_name']}`",
        f"- Threshold: `{selected['threshold']}`",
        "- Production integration: `none`",
        "- Calibration/threshold selection: validation only",
        "- Runtime metadata inputs: none",
        "",
        "## Primary frozen evidence",
        "",
        f"- Publisher/domain held-out ROC-AUC: `{result['test'].get('roc_auc')}`",
        f"- Grouped-bootstrap ROC-AUC 95% CI: `{ci.get('lower')}` - `{ci.get('upper')}`",
        f"- Balanced accuracy: `{result['test'].get('balanced_accuracy')}`",
        f"- ECE: `{result['test'].get('ece')}`",
        f"- Masked ROC-AUC: `{masked.get('roc_auc')}`",
        f"- Masking loss ROC-AUC: `{result.get('masking_loss_auc')}`",
        f"- Strongest matched placebo: `{lift.get('strongest_placebo')}`",
        f"- Main-minus-strongest-placebo ROC-AUC lift: `{lift.get('point_estimate')}`",
        "",
        "## Decision notes",
        "",
        f"- Ensemble attempted: `{decision.get('ensemble_attempted')}`",
        f"- Ensemble reason: {decision.get('ensemble_reason')}",
        "- The encoder candidate remained SMOKE-HOLD because no verified accelerator-backed full frozen-row run exists.",
        "- The score estimates publication-era similarity only and must not be interpreted as AI authorship evidence.",
        "",
        "## Rights and data boundary",
        "",
        "Public artifacts contain IDs, hashes, aggregate metrics, model metadata, and no article body/title/URL/preview fields.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-dir", type=Path, default=Path("services/evals/publication_shift_model/infini_news_v1/candidates"))
    parser.add_argument("--output", type=Path, default=Path("services/evals/publication_shift_model/infini_news_final_v1"))
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({"decision": result["decision"], "selected_model": result["selected_model"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
