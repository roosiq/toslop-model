#!/usr/bin/env python3
"""Finalize the frozen INFINI-NEWS publication-shift evidence.

The score estimates similarity to matched current-era publication language.
This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import joblib
import numpy as np
import sklearn
from sklearn.metrics import roc_auc_score

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

FINAL_SCHEMA = "publication_shift.infini_news_final_decision.v2"
SEED = 20260712
PRIMARY_LANE = "publisher_domain_heldout_primary"
ALTERNATE_SPLIT_LANES = (
    "source_sitename_heldout",
    "topic_heldout",
    "author_heldout",
    "random_diagnostic",
)
DECLARED_PLACEBO_LANES = {
    "placebo_2016_2017_vs_2020_2021": ((2016, 2017), (2020, 2021)),
    "placebo_2016_2018_vs_2019_2021": ((2016, 2017, 2018), (2019, 2020, 2021)),
}
MIN_PRIMARY_AUC = 0.80
MIN_MASKED_AUC = 0.70
MAX_MASKING_LOSS = 0.10
MAX_SOURCE_ONLY_AUC = 0.60
MAX_ECE = 0.08
MIN_PLACEBO_LIFT = 0.05
MIN_ENSEMBLE_AUC_LIFT = 0.01
BOOTSTRAP_SAMPLES = 300
MIN_SUBGROUP_SUPPORT = 100
MIN_SUBGROUP_ACCURACY = 0.70
# The critical review measured this range across the four alternate protocol test
# sets. Exact per-lane counts cannot be reconstructed from the committed package
# because primary train/validation document IDs were not frozen.
CRITICAL_REVIEW_PRIMARY_TRAIN_OVERLAP_RANGE = (0.62, 0.67)


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


def _grouped_bootstrap_auc_values(
    labels: Sequence[int],
    scores: Sequence[float],
    groups: Sequence[str | None],
    *,
    samples: int,
    seed: int,
) -> list[float]:
    y_all = np.asarray(labels, dtype=np.int8)
    p_all = np.asarray(scores, dtype=float)
    if len(y_all) == 0 or len(set(y_all.tolist())) < 2:
        return []
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
    return values


def _ci(values: Sequence[float], samples: int) -> dict[str, Any]:
    if not values:
        return {"samples_requested": samples, "samples_valid": 0, "lower": None, "median": None, "upper": None}
    return {
        "samples_requested": samples,
        "samples_valid": len(values),
        "lower": float(np.quantile(values, 0.025)),
        "median": float(np.quantile(values, 0.5)),
        "upper": float(np.quantile(values, 0.975)),
    }


def grouped_bootstrap_auc(
    labels: Sequence[int],
    scores: Sequence[float],
    groups: Sequence[str | None],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = SEED,
) -> dict[str, Any]:
    return _ci(_grouped_bootstrap_auc_values(labels, scores, groups, samples=samples, seed=seed), samples)


def _labels_scores_groups(predictions: Sequence[dict[str, Any]]) -> tuple[list[int], list[float], list[str | None]]:
    labeled = [row for row in predictions if row.get("label") is not None]
    labels = [int(row["label"]) for row in labeled]
    scores = [float(row[SCORE_NAME]) for row in labeled]
    groups = [row.get("url_hostname_hash") or row.get("sitename_hash") or row.get("near_duplicate_cluster_id") for row in labeled]
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


def declared_historical_placebos(
    predictions_by_lane: Mapping[str, Sequence[dict[str, Any]]],
    *,
    threshold: float,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    """Evaluate only the frozen, declared placebo files; never substitute core rows."""
    output: dict[str, Any] = {}
    for index, (name, (early_years, late_years)) in enumerate(DECLARED_PLACEBO_LANES.items()):
        rows = list(predictions_by_lane.get(name) or [])
        labels, scores, groups = _labels_scores_groups(rows)
        observed_years = sorted({int(row["publication_year"]) for row in rows if row.get("publication_year") is not None})
        has_early = any(year in early_years for year in observed_years)
        has_late = any(year in late_years for year in observed_years)
        supported = set(labels) == {0, 1} and has_early and has_late
        reason = None
        if not supported:
            reason = "frozen declared placebo predictions lack both required early and late classes; primary/core rows must not be substituted"
        output[name] = {
            "selection_status": "valid_for_selection" if supported else "unsupported",
            "support": {"status": "supported" if supported else "unsupported", "reason": reason},
            "year_groups": {"early": list(early_years), "late": list(late_years)},
            "observed_publication_years": observed_years,
            "test": binary_metrics(labels, scores, threshold),
            "grouped_bootstrap_roc_auc_95ci": grouped_bootstrap_auc(labels, scores, groups, samples=samples, seed=SEED + 100 + index),
        }
    return output


# Backward-compatible name for callers/tests; semantics are now declared-file only.
def matched_historical_placebos(
    predictions: Sequence[dict[str, Any]] | dict[str, Sequence[dict[str, Any]]],
    *,
    threshold: float,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    if not isinstance(predictions, dict):
        raise ValueError("placebo evaluation requires declared lane files keyed by lane name; core prediction substitution is forbidden")
    return declared_historical_placebos(predictions, threshold=threshold, samples=samples)


def placebo_lift_evidence(
    primary_predictions: Sequence[dict[str, Any]],
    predictions_by_lane: Mapping[str, Sequence[dict[str, Any]]],
    placebos: dict[str, Any],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    supported = {name: lane for name, lane in placebos.items() if lane["support"]["status"] == "supported" and lane["test"].get("roc_auc") is not None}
    if not supported:
        return {
            "status": "unsupported",
            "strongest_placebo": None,
            "point_estimate": None,
            "grouped_bootstrap_roc_auc_lift_95ci": _ci([], samples),
            "reason": "no declared historical placebo has both classes; required lift and confidence interval are unavailable",
        }
    strongest = max(supported, key=lambda name: float(supported[name]["test"]["roc_auc"]))
    primary_labels, primary_scores, primary_groups = _labels_scores_groups(primary_predictions)
    placebo_labels, placebo_scores, placebo_groups = _labels_scores_groups(predictions_by_lane[strongest])
    primary_values = _grouped_bootstrap_auc_values(primary_labels, primary_scores, primary_groups, samples=samples, seed=SEED + 500)
    placebo_values = _grouped_bootstrap_auc_values(placebo_labels, placebo_scores, placebo_groups, samples=samples, seed=SEED + 501)
    paired_count = min(len(primary_values), len(placebo_values))
    lift_values = [primary_values[index] - placebo_values[index] for index in range(paired_count)]
    primary_auc = float(roc_auc_score(primary_labels, primary_scores))
    placebo_auc = float(supported[strongest]["test"]["roc_auc"])
    return {
        "status": "supported" if lift_values else "unsupported",
        "strongest_placebo": strongest,
        "point_estimate": primary_auc - placebo_auc,
        "grouped_bootstrap_roc_auc_lift_95ci": _ci(lift_values, samples),
        "reason": None if lift_values else "grouped bootstrap lift could not be computed",
    }


def _metric_value(metrics: dict[str, Any], lane: str, name: str) -> float | None:
    value = (metrics.get("lanes") or {}).get(lane, {}).get(name)
    return float(value) if value is not None else None


def _alternate_lane_selection_evidence(metrics: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for lane in ALTERNATE_SPLIT_LANES:
        lane_metrics = (metrics.get("lanes") or {}).get(lane)
        explicit_status = lane_metrics.get("selection_status") if isinstance(lane_metrics, dict) else None
        explicit_overlap = lane_metrics.get("primary_training_overlap_count") if isinstance(lane_metrics, dict) else None
        valid = explicit_status == "valid_for_selection" and explicit_overlap == 0
        output[lane] = {
            "selection_status": "valid_for_selection" if valid else "invalid_for_selection",
            "metrics_preserved_as_diagnostic": lane_metrics,
            "primary_training_overlap_count": explicit_overlap,
            "reason": None if valid else "the primary-trained artifact was scored on a different protocol's test partition without a zero-overlap audit against primary training rows",
        }
    return output


def candidate_gate_matrix(candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for name, metrics in candidates.items():
        primary_auc = _metric_value(metrics, PRIMARY_LANE, "roc_auc")
        masked_auc = _metric_value(metrics, "masked_primary_test", "roc_auc")
        primary_ece = _metric_value(metrics, PRIMARY_LANE, "ece")
        source_only_auc = (((metrics.get("shortcut_diagnostics") or {}).get("source_only_primary_test") or {}).get("roc_auc"))
        metadata_only_auc = (((metrics.get("shortcut_diagnostics") or {}).get("metadata_only_primary_test") or {}).get("roc_auc"))
        candidate_decision = metrics.get("decision")
        primary_valid = primary_auc is not None and masked_auc is not None
        masking_loss: float | None = None
        if primary_auc is not None and masked_auc is not None:
            masking_loss = primary_auc - masked_auc
        alternate_lanes = _alternate_lane_selection_evidence(metrics)
        candidate_gates = {
            "candidate_full_not_smoke": candidate_decision != "SMOKE-HOLD",
            "primary_auc_minimum": primary_auc is not None and primary_auc >= MIN_PRIMARY_AUC,
            "masked_auc_minimum": masked_auc is not None and masked_auc >= MIN_MASKED_AUC,
            "masking_loss_maximum": masking_loss is not None and masking_loss < MAX_MASKING_LOSS,
            "source_only_shortcut_maximum": source_only_auc is not None and float(source_only_auc) <= MAX_SOURCE_ONLY_AUC,
            "primary_ece_maximum": primary_ece is not None and primary_ece < MAX_ECE,
        }
        alternate_gate = all(lane["selection_status"] == "valid_for_selection" for lane in alternate_lanes.values())
        matrix[name] = {
            "eligible_for_candidate_comparison": all(candidate_gates.values()),
            "eligible_for_final": all(candidate_gates.values()) and alternate_gate,
            "candidate_gates": candidate_gates,
            "required_alternate_lanes_leakage_safe": alternate_gate,
            "alternate_lane_evidence": alternate_lanes,
            "evidence": {
                "primary_auc": primary_auc,
                "masked_auc": masked_auc,
                "masking_loss_auc": masking_loss,
                "primary_ece": primary_ece,
                "source_only_auc": source_only_auc,
                "metadata_only_auc": metadata_only_auc,
                "candidate_decision": candidate_decision,
            },
            "notes": [
                "Primary publisher/domain-held-out metrics remain valid frozen evidence for the artifact trained on that protocol.",
                "Source/topic/author/random metrics are diagnostic only until their test documents are proven disjoint from this artifact's primary training rows.",
            ],
        }
    return matrix


def _global_gates_pass(global_gates: dict[str, Any]) -> bool:
    return bool(global_gates) and all(gate.get("passed") is True for gate in global_gates.values())


def select_final_decision(
    candidates: dict[str, dict[str, Any]],
    matrix: dict[str, Any],
    global_gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    comparable = [name for name, gate in matrix.items() if gate.get("eligible_for_candidate_comparison")]
    reviewed = max(comparable, key=lambda name: float((candidates[name].get("lanes") or {}).get(PRIMARY_LANE, {}).get("roc_auc") or -1.0)) if comparable else None
    failed_global = sorted(name for name, gate in (global_gates or {}).items() if gate.get("passed") is not True)
    if not reviewed or not _global_gates_pass(global_gates or {}) or not matrix[reviewed].get("eligible_for_final"):
        return {
            "decision": "HOLD",
            "selected_candidate": None,
            "reviewed_candidate": reviewed,
            "ensemble_attempted": False,
            "failed_required_gates": failed_global or (["valid_leakage_safe_alternate_lanes"] if reviewed else ["passing_candidate"]),
            "reason": "Required promotion evidence is missing or failed; no candidate is selected or frozen for release.",
            "disclaimer": DISCLAIMER,
        }
    eligible = [name for name, gate in matrix.items() if gate.get("eligible_for_final")]
    selected = max(eligible, key=lambda name: float((candidates[name].get("lanes") or {}).get(PRIMARY_LANE, {}).get("roc_auc") or -1.0))
    ensemble_eligible = len(eligible) > 1
    return {
        "decision": "PASS",
        "selected_candidate": selected,
        "reviewed_candidate": selected,
        "ensemble_attempted": False,
        "ensemble_precondition_all_components_passed": ensemble_eligible,
        "ensemble_minimum_auc_lift": MIN_ENSEMBLE_AUC_LIFT,
        "ensemble_reason": "No frozen validation-calibrated ensemble artifact was predeclared." if ensemble_eligible else "Only one candidate passed every required gate.",
        "failed_required_gates": [],
        "reason": "Every required frozen gate passed; strongest passing component selected.",
        "disclaimer": DISCLAIMER,
    }


def sha256_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _equal_number(left: Any, right: Any) -> bool:
    try:
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-15)
    except (TypeError, ValueError):
        return False


def assert_selected_artifact_identity(
    candidate_name: str,
    metrics: dict[str, Any],
    metadata: dict[str, Any],
    split_summary: dict[str, Any],
) -> dict[str, Any]:
    """Strictly bind metadata, metrics, split identity, and serialized artifact."""
    source = Path(str(metadata.get("artifact_path") or ""))
    if not source.is_file():
        raise AssertionError(f"selected artifact is not a file: {source}")
    artifact_sha256 = sha256_file(source)
    checks = {
        "candidate_name_metrics_metadata": metrics.get("candidate_name") == metadata.get("candidate_name") == candidate_name,
        "model_id_metrics_metadata": metrics.get("model_id") == metadata.get("model_id"),
        "model_family_metrics_metadata": metrics.get("model_family") == metadata.get("model_family"),
        "score_name_metrics_metadata": metrics.get("score_name") == metadata.get("score_name") == SCORE_NAME,
        "artifact_sha256_metadata": artifact_sha256 == metadata.get("artifact_sha256"),
        "artifact_size_metadata": source.stat().st_size == metadata.get("artifact_size_bytes"),
        "split_summary_identity": stable_json_sha256(split_summary) == metadata.get("split_summary_sha256"),
    }
    loaded = joblib.load(source)
    checks.update(
        {
            "artifact_schema": loaded.get("schema") == "publication_shift.infini_news_model_artifact.v1",
            "artifact_candidate_name": loaded.get("candidate_name") == candidate_name,
            "artifact_model_id": loaded.get("model_id") == metadata.get("model_id"),
            "artifact_model_family": loaded.get("model_family") == metadata.get("model_family"),
            "artifact_score_name": loaded.get("score_name") == metadata.get("score_name"),
            "artifact_threshold": _equal_number(loaded.get("threshold"), metadata.get("threshold")),
            "artifact_training_identity": loaded.get("training_identity_sha256") == metadata.get("training_identity_sha256"),
            "artifact_training_protocol": loaded.get("training_protocol") == metrics.get("training_protocol") == PRIMARY_LANE,
            "model_id_training_identity_suffix": str(metadata.get("model_id") or "").endswith(str(metadata.get("training_identity_sha256") or "")[:12]),
        }
    )
    primary = (metrics.get("lanes") or {}).get(PRIMARY_LANE) or {}
    masked = (metrics.get("lanes") or {}).get("masked_primary_test") or {}
    checks["primary_threshold"] = _equal_number(primary.get("threshold"), metadata.get("threshold"))
    checks["masked_threshold"] = _equal_number(masked.get("threshold"), metadata.get("threshold"))
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise AssertionError(f"selected artifact identity validation failed: {', '.join(failed)}")
    return {
        "status": "PASS",
        "all_assertions_passed": True,
        "assertions": checks,
        "artifact_path": str(source),
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": source.stat().st_size,
        "model_id": metadata["model_id"],
        "threshold": metadata["threshold"],
        "training_identity_sha256": metadata["training_identity_sha256"],
        "split_summary_sha256": metadata["split_summary_sha256"],
    }


def copy_selected_artifact(metadata: dict[str, Any], output_dir: Path, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    if not validation or validation.get("all_assertions_passed") is not True:
        raise AssertionError("refusing to freeze selected artifact without strict identity validation")
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
        if digest != validation["artifact_sha256"]:
            raise AssertionError("copied artifact directory hash differs from validated source")
        return {"path": str(copied_dir), "sha256": digest, "size_bytes": size, "source_path": str(source)}
    copied_path = output_dir / source.name
    shutil.copy2(source, copied_path)
    copied_sha256 = sha256_file(copied_path)
    if copied_sha256 != validation["artifact_sha256"]:
        raise AssertionError("copied artifact hash differs from validated source")
    return {"path": str(copied_path), "sha256": copied_sha256, "size_bytes": copied_path.stat().st_size, "source_path": str(source)}


def remove_stale_frozen_artifacts(output_dir: Path, bundles: dict[str, dict[str, Any]]) -> list[str]:
    removed: list[str] = []
    paths = {output_dir / Path(str(bundle["metadata"].get("artifact_path") or "artifact")).name for bundle in bundles.values()}
    paths.add(output_dir / "model_artifact")
    for path in sorted(paths):
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(path))
        elif path.is_file():
            path.unlink()
            removed.append(str(path))
    return removed


def load_candidate_bundle(candidates_dir: Path) -> dict[str, dict[str, Any]]:
    bundles = {}
    for candidate_dir in sorted(path for path in candidates_dir.iterdir() if path.is_dir()):
        metrics_path = candidate_dir / "metrics.json"
        metadata_path = candidate_dir / "model_metadata.json"
        if metrics_path.exists() and metadata_path.exists():
            bundles[candidate_dir.name] = {"metrics": read_json(metrics_path), "metadata": read_json(metadata_path), "dir": candidate_dir}
    return bundles


def alternate_overlap_audit(bundle: dict[str, Any], primary_predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    primary_test_ids = {str(row["document_id"]) for row in primary_predictions}
    lanes = {}
    for lane in ALTERNATE_SPLIT_LANES:
        path = bundle["dir"] / f"{lane}_predictions.jsonl"
        rows = read_jsonl(path) if path.exists() else []
        ids = {str(row["document_id"]) for row in rows}
        overlap = len(ids & primary_test_ids)
        lanes[lane] = {
            "selection_status": "invalid_for_selection",
            "test_document_count": len(ids),
            "primary_test_document_overlap_count": overlap,
            "primary_test_document_overlap_fraction": overlap / len(ids) if ids else None,
            "primary_training_document_overlap_fraction_review_range": list(CRITICAL_REVIEW_PRIMARY_TRAIN_OVERLAP_RANGE),
            "exact_primary_training_overlap_recomputable_from_committed_evidence": False,
            "reason": "critical review found 62%-67% primary-training reuse; committed artifacts omit primary train IDs, so the required zero-overlap assertion cannot be reproduced",
        }
    return {
        "status": "FAIL",
        "all_alternate_lanes_valid_for_selection": False,
        "critical_review_primary_training_overlap_fraction_range": list(CRITICAL_REVIEW_PRIMARY_TRAIN_OVERLAP_RANGE),
        "frozen_evidence_limitation": "primary train and validation document IDs were not frozen in the committed public package",
        "lanes": lanes,
    }


def subgroup_collapse_audit(predictions: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    dimensions = {"source_hash": "url_hostname_hash", "publication_month": "publication_year_month"}
    result: dict[str, Any] = {}
    all_collapses: list[dict[str, Any]] = []
    for dimension, key in dimensions.items():
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in predictions:
            if row.get(key) is not None and row.get("label") is not None:
                buckets[str(row[key])].append(row)
        collapses = []
        for value, rows in sorted(buckets.items()):
            if len(rows) < MIN_SUBGROUP_SUPPORT:
                continue
            correct = sum((float(row[SCORE_NAME]) >= threshold) == bool(int(row["label"])) for row in rows)
            accuracy = correct / len(rows)
            if accuracy < MIN_SUBGROUP_ACCURACY:
                entry = {"dimension": dimension, "group": value, "count": len(rows), "accuracy": accuracy}
                collapses.append(entry)
                all_collapses.append(entry)
        result[dimension] = {
            "minimum_support": MIN_SUBGROUP_SUPPORT,
            "severe_accuracy_threshold": MIN_SUBGROUP_ACCURACY,
            "severe_collapse_count": len(collapses),
            "severe_collapses": sorted(collapses, key=lambda item: (item["accuracy"], -item["count"], item["group"])),
        }
    return {"status": "FAIL" if all_collapses else "PASS", "severe_collapse_count": len(all_collapses), "dimensions": result}


def _external_summary(path: Path, expected_model: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return {"status": "MISSING", "path": str(path), "decision": None, "identity_match": False, "rights_status": None, "gates": {}}
    report = read_json(path)
    model = report.get("model") or {}
    identity_match = (
        model.get("model_id") == expected_model.get("model_id")
        and model.get("metadata_model_id") == expected_model.get("model_id")
        and model.get("artifact_sha256") == expected_model.get("artifact_sha256")
        and _equal_number(model.get("threshold"), expected_model.get("threshold"))
    )
    metrics = report.get("metrics") or {}
    overall = metrics.get("overall") or {}
    masked = metrics.get("masked") or {}
    return {
        "status": "PASS" if report.get("decision") == "PASS" and identity_match else "HOLD",
        "path": str(path),
        "decision": report.get("decision"),
        "decision_reason": report.get("decision_reason"),
        "identity_match": identity_match,
        "rights_status": (report.get("source") or {}).get("rights_status"),
        "overall": {key: overall.get(key) for key in ("count", "roc_auc", "balanced_accuracy", "ece", "sensitivity", "specificity")},
        "masked": {key: masked.get(key) for key in ("count", "roc_auc", "balanced_accuracy", "ece", "sensitivity", "specificity")},
        "gates": report.get("gates") or {},
    }


def build_global_gate_matrix(
    *,
    alternate_audit: dict[str, Any],
    placebos: dict[str, Any],
    lift: dict[str, Any],
    encoder_metrics: dict[str, Any] | None,
    subgroup_audit: dict[str, Any],
    external_reports: dict[str, Any],
    primary_rights_status: str | None,
    artifact_validation: dict[str, Any],
) -> dict[str, Any]:
    placebo_supported = bool(placebos) and all(lane["support"]["status"] == "supported" for lane in placebos.values())
    lift_ci = lift.get("grouped_bootstrap_roc_auc_lift_95ci") or {}
    placebo_lift_passed = (
        lift.get("status") == "supported"
        and lift.get("point_estimate") is not None
        and float(lift["point_estimate"]) >= MIN_PLACEBO_LIFT
        and lift_ci.get("lower") is not None
        and float(lift_ci["lower"]) > 0.0
    )
    encoder_decision = (encoder_metrics or {}).get("decision")
    encoder_full = encoder_decision == "PASS-HOLD" and int(((encoder_metrics or {}).get("counts") or {}).get("corpus_rows") or 0) >= 264000
    measured_hold = encoder_decision == "HOLD" and bool((encoder_metrics or {}).get("hardware_blocker"))
    external_all_pass = bool(external_reports) and all(report.get("status") == "PASS" for report in external_reports.values())
    external_rights_clear = bool(external_reports) and all(not str(report.get("rights_status") or "").startswith("HOLD") for report in external_reports.values())
    primary_rights_clear = bool(primary_rights_status) and not str(primary_rights_status).startswith("research_only") and not str(primary_rights_status).startswith("HOLD")
    return {
        "valid_leakage_safe_alternate_lanes": {
            "passed": alternate_audit.get("all_alternate_lanes_valid_for_selection") is True,
            "status": "PASS" if alternate_audit.get("all_alternate_lanes_valid_for_selection") is True else "FAIL",
            "evidence": alternate_audit,
        },
        "declared_historical_placebos_supported": {
            "passed": placebo_supported,
            "status": "PASS" if placebo_supported else "FAIL",
            "evidence": placebos,
        },
        "placebo_lift_minimum_and_ci": {
            "passed": placebo_lift_passed,
            "status": "PASS" if placebo_lift_passed else "FAIL",
            "minimum_lift": MIN_PLACEBO_LIFT,
            "required_ci_lower_above_zero": True,
            "evidence": lift,
        },
        "full_encoder_or_measured_hardware_hold": {
            "passed": encoder_full or measured_hold,
            "status": "PASS" if encoder_full or measured_hold else "FAIL",
            "encoder_decision": encoder_decision,
            "full_frozen_row_run": encoder_full,
            "measured_hardware_hold": measured_hold,
            "reason": None if encoder_full or measured_hold else "available encoder is only SMOKE-HOLD, not a full run or a measured hardware HOLD",
        },
        "no_severe_subgroup_collapse": {
            "passed": subgroup_audit.get("status") == "PASS",
            "status": subgroup_audit.get("status"),
            "evidence": subgroup_audit,
        },
        "external_validation_gates": {
            "passed": external_all_pass,
            "status": "PASS" if external_all_pass else "FAIL",
            "evidence": external_reports,
        },
        "rights_clearance_for_promotion": {
            "passed": primary_rights_clear and external_rights_clear,
            "status": "PASS" if primary_rights_clear and external_rights_clear else "FAIL",
            "primary_corpus_rights_status": primary_rights_status,
            "external_rights_clear": external_rights_clear,
            "reason": None if primary_rights_clear and external_rights_clear else "primary and/or external corpus rights remain research-only or HOLD",
        },
        "selected_artifact_identity": {
            "passed": artifact_validation.get("all_assertions_passed") is True,
            "status": artifact_validation.get("status"),
            "evidence": artifact_validation,
        },
    }


def checksum_manifest(output_dir: Path) -> dict[str, str]:
    checksums = {}
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file() and item.name not in {"checksums.json", "checksums.sha256"}):
        checksums[str(path)] = sha256_file(path)
    return checksums


def _read_declared_placebo_files(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    output = {}
    for lane in DECLARED_PLACEBO_LANES:
        path = bundle["dir"] / f"{lane}_predictions.jsonl"
        output[lane] = read_jsonl(path) if path.exists() else []
    return output


def run(args: argparse.Namespace) -> dict[str, Any]:
    candidates_dir = args.candidates_dir
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    bundles = load_candidate_bundle(candidates_dir)
    candidates = {name: bundle["metrics"] for name, bundle in bundles.items()}
    if not candidates:
        raise ValueError(f"no candidate metrics found in {candidates_dir}")
    split_summary = read_json(args.split_summary)
    matrix = candidate_gate_matrix(candidates)
    comparable = [name for name, gate in matrix.items() if gate["eligible_for_candidate_comparison"]]
    if not comparable:
        raise ValueError("no candidate has valid primary evidence to review")
    reviewed_name = max(comparable, key=lambda name: float((candidates[name].get("lanes") or {}).get(PRIMARY_LANE, {}).get("roc_auc") or -1.0))
    reviewed = bundles[reviewed_name]
    reviewed_metrics = reviewed["metrics"]
    reviewed_metadata = reviewed["metadata"]

    artifact_validation = assert_selected_artifact_identity(reviewed_name, reviewed_metrics, reviewed_metadata, split_summary)
    primary_path = reviewed["dir"] / "publisher_domain_heldout_primary_predictions.jsonl"
    primary_predictions = read_jsonl(primary_path)
    if len(primary_predictions) != int(reviewed_metrics["lanes"][PRIMARY_LANE]["count"]):
        raise AssertionError("primary prediction count does not match frozen metrics")
    if any(row.get("lane") != PRIMARY_LANE or row.get("model_family") != reviewed_metadata["model_family"] for row in primary_predictions):
        raise AssertionError("primary predictions do not match selected lane/model family")
    primary_labels, primary_scores, primary_groups = _labels_scores_groups(primary_predictions)
    primary_bootstrap = grouped_bootstrap_auc(primary_labels, primary_scores, primary_groups, seed=SEED)

    placebo_predictions = _read_declared_placebo_files(reviewed)
    placebos = declared_historical_placebos(placebo_predictions, threshold=float(reviewed_metadata["threshold"]))
    lift = placebo_lift_evidence(primary_predictions, placebo_predictions, placebos)
    overlap_audit = alternate_overlap_audit(reviewed, primary_predictions)
    subgroup_audit = subgroup_collapse_audit(primary_predictions, float(reviewed_metadata["threshold"]))
    diagnostics = {
        "by_source_hash": _score_diagnostic_by_key(primary_predictions, "url_hostname_hash"),
        "by_topic": _score_diagnostic_by_key(primary_predictions, "topic"),
        "by_year": _score_diagnostic_by_year(primary_predictions),
        "by_length_quartile": _score_diagnostic_by_length(primary_predictions),
        "subgroup_collapse_audit": subgroup_audit,
    }

    expected_external_model = {
        "model_id": reviewed_metadata["model_id"],
        "artifact_sha256": reviewed_metadata["artifact_sha256"],
        "threshold": reviewed_metadata["threshold"],
    }
    external_reports = {
        "bbc_external_v1": _external_summary(args.bbc_external_report, expected_external_model),
        "multisource_all_valid_source_diverse": _external_summary(args.multisource_all_report, expected_external_model),
        "multisource_domain_matched_balanced": _external_summary(args.multisource_matched_report, expected_external_model),
    }
    corpus_report = read_json(args.corpus_report) if args.corpus_report.exists() else {}
    encoder_metrics = candidates.get("deberta_multitask_encoder")
    global_gates = build_global_gate_matrix(
        alternate_audit=overlap_audit,
        placebos=placebos,
        lift=lift,
        encoder_metrics=encoder_metrics,
        subgroup_audit=subgroup_audit,
        external_reports=external_reports,
        primary_rights_status=corpus_report.get("source_rights_status"),
        artifact_validation=artifact_validation,
    )
    global_pass = _global_gates_pass(global_gates)
    for gate in matrix.values():
        gate["eligible_for_final"] = bool(gate["eligible_for_final"] and global_pass)
    decision = select_final_decision(candidates, matrix, global_gates)

    selected_model = None
    removed_stale_artifacts: list[str] = []
    if decision["decision"] == "PASS":
        selected_name = str(decision["selected_candidate"])
        selected_bundle = bundles[selected_name]
        selected_validation = assert_selected_artifact_identity(selected_name, selected_bundle["metrics"], selected_bundle["metadata"], split_summary)
        artifact = copy_selected_artifact(selected_bundle["metadata"], output_dir, selected_validation)
        selected_model = {
            "candidate_name": selected_name,
            "model_id": selected_bundle["metadata"]["model_id"],
            "model_family": selected_bundle["metadata"]["model_family"],
            "score_name": selected_bundle["metadata"]["score_name"],
            "threshold": selected_bundle["metadata"]["threshold"],
            "artifact": artifact,
            "source_artifact_sha256": selected_bundle["metadata"]["artifact_sha256"],
            "training_identity_sha256": selected_bundle["metadata"]["training_identity_sha256"],
            "split_summary_sha256": selected_bundle["metadata"]["split_summary_sha256"],
        }
    else:
        removed_stale_artifacts = remove_stale_frozen_artifacts(output_dir, bundles)

    primary_auc = float(reviewed_metrics["lanes"][PRIMARY_LANE]["roc_auc"])
    masked_metrics = reviewed_metrics["lanes"].get("masked_primary_test") or {}
    frozen_lanes = {}
    for lane in ALTERNATE_SPLIT_LANES:
        frozen_lanes[lane] = {
            "selection_status": "invalid_for_selection",
            "reason": overlap_audit["lanes"][lane]["reason"],
            "overlap_evidence": overlap_audit["lanes"][lane],
            "reported_metrics_preserved_as_diagnostic": reviewed_metrics["lanes"].get(lane),
        }
    frozen_lanes.update(
        {
            "transition_2022": reviewed_metrics["lanes"].get("transition_2022"),
            "forward_2026_jan_apr": reviewed_metrics["lanes"].get("forward_2026_jan_apr"),
            "length_quartiles_primary": reviewed_metrics["lanes"].get("length_quartiles_primary"),
        }
    )

    final = {
        "schema": FINAL_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "mandatory_disclaimer": DISCLAIMER,
        "decision": decision,
        "global_gate_matrix": global_gates,
        "selected_model": selected_model,
        "artifact_freeze": {
            "status": "not_performed" if selected_model is None else "completed",
            "reason": "HOLD forbids selecting or freezing an artifact" if selected_model is None else None,
            "removed_stale_artifacts": removed_stale_artifacts,
        },
        "reviewed_model": {
            "selection_status": "reviewed_not_selected" if selected_model is None else "selected",
            "candidate_name": reviewed_name,
            "model_id": reviewed_metadata["model_id"],
            "model_family": reviewed_metadata["model_family"],
            "score_name": reviewed_metadata["score_name"],
            "threshold": reviewed_metadata["threshold"],
            "source_artifact_sha256": reviewed_metadata["artifact_sha256"],
            "training_identity_sha256": reviewed_metadata["training_identity_sha256"],
            "split_summary_sha256": reviewed_metadata["split_summary_sha256"],
            "artifact_identity_validation": artifact_validation,
        },
        "policy": {
            "calibration_and_thresholds": "validation_only_from_candidate_training_protocol",
            "production_integration": "none",
            "runtime_metadata_inputs": [],
            "rights_boundary": "Public final artifacts contain IDs, hashes, aggregate metrics, model metadata, and no article body/title/URL/preview fields.",
            "interpretation_boundary": DISCLAIMER,
            "hold_boundary": "Research-only diagnostic evidence; not validated, selected, production-authorized, or deployable.",
        },
        "candidate_gate_matrix": matrix,
        "primary_result": {
            "selection_status": "valid_frozen_primary_evidence",
            "test": reviewed_metrics["lanes"][PRIMARY_LANE],
            "grouped_bootstrap_roc_auc_95ci": primary_bootstrap,
            "masked_test": masked_metrics,
            "masking_loss_auc": primary_auc - float(masked_metrics["roc_auc"]),
            "declared_historical_placebos": placebos,
            "main_minus_strongest_placebo": lift,
        },
        "frozen_lane_results": frozen_lanes,
        "external_validation": external_reports,
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
    assert_public_safe(final)
    write_json(output_dir / "decision_packet.json", final)
    write_jsonl(output_dir / "publisher_domain_heldout_primary_predictions.jsonl", primary_predictions)
    write_markdown(output_dir / "MODEL_CARD.md", render_model_card(final))
    checksums = checksum_manifest(output_dir)
    write_json(output_dir / "checksums.json", {"schema": "publication_shift.infini_news_final_checksums.v2", "files": checksums})
    (output_dir / "checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(checksums.items())), encoding="utf-8")
    return final


def render_model_card(final: dict[str, Any]) -> str:
    reviewed = final["reviewed_model"]
    result = final["primary_result"]
    decision = final["decision"]
    masked = result.get("masked_test") or {}
    lift = result["main_minus_strongest_placebo"]
    ci = result["grouped_bootstrap_roc_auc_95ci"]
    failed = ", ".join(decision.get("failed_required_gates") or [])
    collapse = final["diagnostics"]["subgroup_collapse_audit"]
    external = final["external_validation"]
    return "\n".join(
        [
            "# INFINI-NEWS publication-shift evidence review v1",
            "",
            f"**{DISCLAIMER}**",
            "",
            "**MANDATORY HOLD NOTICE: This evidence is research-only. No model is selected, frozen for release, validated for deployment, or authorized for production use.**",
            "",
            f"- Final disposition: `{decision['decision']}`",
            "- Selected candidate: `none`",
            f"- Reviewed candidate (not selected): `{reviewed['candidate_name']}`",
            f"- Reviewed model ID: `{reviewed['model_id']}`",
            f"- Reviewed artifact SHA-256: `{reviewed['source_artifact_sha256']}`",
            f"- Reviewed threshold: `{reviewed['threshold']}`",
            f"- Reviewed training identity: `{reviewed['training_identity_sha256']}`",
            "- Artifact identity assertions: `PASS`",
            "- Artifact copied/frozen into final package: `no`",
            "- Production integration: `none`",
            "",
            "## Valid primary frozen evidence (preserved)",
            "",
            f"- Publisher/domain-held-out ROC-AUC: `{result['test'].get('roc_auc')}`",
            f"- Grouped-bootstrap ROC-AUC 95% CI: `{ci.get('lower')}` - `{ci.get('upper')}`",
            f"- Balanced accuracy: `{result['test'].get('balanced_accuracy')}`",
            f"- ECE: `{result['test'].get('ece')}`",
            f"- Masked ROC-AUC: `{masked.get('roc_auc')}`",
            f"- Masking loss ROC-AUC: `{result.get('masking_loss_auc')}`",
            "",
            "## Why the disposition is HOLD",
            "",
            f"- Failed required gates: `{failed}`",
            "- Source/topic/author/random metrics are `invalid_for_selection`: their alternate test partitions were not kept disjoint from the primary artifact's training rows; critical review measured 62%-67% training-document reuse.",
            "- Exact per-lane primary-training overlap cannot be recomputed from the committed package because primary train/validation document IDs were not frozen. This missing audit is itself a gate failure.",
            "- The frozen historical-placebo files contain no late comparison class. Prior core-row substitutions are not accepted; placebo lift and its required 95% CI are unavailable.",
            f"- Encoder evidence is `{final['global_gate_matrix']['full_encoder_or_measured_hardware_hold'].get('encoder_decision')}` only, not a full frozen-row run or measured hardware HOLD.",
            f"- Severe source/month collapse count at >= {MIN_SUBGROUP_SUPPORT} rows and < {MIN_SUBGROUP_ACCURACY:.2f} accuracy: `{collapse['severe_collapse_count']}`.",
            "- January 2024 is 580/951 = 60.99% accuracy; a 249-row source hash is 14.86% accurate overall (and its 243 January rows are 12.76% accurate in the frozen diagnostic).",
            f"- BBC external decision: `{external['bbc_external_v1']['decision']}` (balanced accuracy `{external['bbc_external_v1']['overall'].get('balanced_accuracy')}`).",
            f"- Multisource all-valid decision: `{external['multisource_all_valid_source_diverse']['decision']}` (masked ROC-AUC `{external['multisource_all_valid_source_diverse']['masked'].get('roc_auc')}`).",
            f"- Multisource domain-matched decision: `{external['multisource_domain_matched_balanced']['decision']}` (balanced accuracy `{external['multisource_domain_matched_balanced']['overall'].get('balanced_accuracy')}`, masked ROC-AUC `{external['multisource_domain_matched_balanced']['masked'].get('roc_auc')}`).",
            "- Primary and external data rights remain research-only/HOLD; there is no production authorization.",
            "",
            "## Placebo claim boundary",
            "",
            f"- Strongest valid declared placebo: `{lift.get('strongest_placebo')}`",
            f"- Main-minus-placebo lift: `{lift.get('point_estimate')}`",
            f"- Lift 95% CI lower bound: `{(lift.get('grouped_bootstrap_roc_auc_lift_95ci') or {}).get('lower')}`",
            "- Therefore this package does not establish an unusual LLM-era publication shift; the evidence may reflect ordinary temporal/domain drift.",
            "",
            "## Rights and interpretation boundary",
            "",
            "Public artifacts contain IDs, hashes, aggregate metrics, and model metadata only. Article bodies, titles, descriptions, URLs, and previews are excluded.",
            "",
            f"**{DISCLAIMER}**",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-dir", type=Path, default=Path("services/evals/publication_shift_model/infini_news_v1/candidates"))
    parser.add_argument("--output", type=Path, default=Path("services/evals/publication_shift_model/infini_news_final_v1"))
    parser.add_argument("--split-summary", type=Path, default=Path("services/evals/publication_shift_model/infini_news_v1/splits/summary.json"))
    parser.add_argument("--corpus-report", type=Path, default=Path("services/evals/publication_shift_model/infini_news_v1/full_report.json"))
    parser.add_argument("--bbc-external-report", type=Path, default=Path("services/evals/publication_shift_model/bbc_external_v1/report.json"))
    parser.add_argument("--multisource-all-report", type=Path, default=Path("services/evals/publication_shift_model/multisource_external_v1/all_valid_source_diverse/report.json"))
    parser.add_argument("--multisource-matched-report", type=Path, default=Path("services/evals/publication_shift_model/multisource_external_v1/domain_matched_balanced/report.json"))
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({"decision": result["decision"], "selected_model": result["selected_model"], "reviewed_model": result["reviewed_model"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
