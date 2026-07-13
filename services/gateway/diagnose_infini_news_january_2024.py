#!/usr/bin/env python3
"""Generate the frozen INFINI-NEWS January 2024 no-text diagnostic.

This lane only aggregates already-frozen predictions. It does not load article
text, score articles, select a model, tune a threshold, or modify the model.
This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

DISCLAIMER = "This score does not establish AI authorship."
SCHEMA = "publication_shift.infini_news_january_2024_diagnostic.v1"
CHECKSUM_SCHEMA = "publication_shift.infini_news_january_2024_checksums.v1"
MODEL_ID = "infini-news-lexical_tfidf_logistic-v1-cca5838ac34f"
MODEL_FAMILY = "infini_news_word_char_tfidf_logistic"
CANDIDATE_NAME = "lexical_tfidf_logistic"
SCORE_NAME = "current_era_similarity"
THRESHOLD = 0.49690983649044096
ARTIFACT_SHA256 = "0ca8956726b101fd585ff663caf4119e4911d3ec2789cf25fab415669691d403"
PREDICTIONS_SHA256 = "ea95783593fcbdd75dfe07c9156000dbc9f03de88360be0965bb8253b5b95c33"
METADATA_SHA256 = "1917395aa1d71201d8680822658b8a74156ecc9b4e88a38d8ea936d95e234089"
TRAINING_IDENTITY_SHA256 = "cca5838ac34f170c53d1552ed8e8ca09fed187f9111b37c20f5e87cf9456e7b5"
SPLIT_SUMMARY_SHA256 = "a2ab127c5421c7c14444d7053e08125205e03118067e8194d1fe75618ccbaa1d"
PRIMARY_LANE = "publisher_domain_heldout_primary"
EXPECTED_CONFIG = {
    "C": 1.0,
    "char_max_features": 100000,
    "char_ngram_range": [3, 5],
    "class_weight": "balanced",
    "max_df": 0.995,
    "max_iter": 500,
    "min_df": 3,
    "random_seed": 20260712,
    "solver": "liblinear",
    "word_max_features": 100000,
    "word_ngram_range": [1, 3],
}
REQUIRED_PREDICTION_FIELDS = {
    "author_hash",
    "corpus_role",
    "document_id",
    "identity_hash",
    "label",
    "lane",
    "model_family",
    "near_duplicate_cluster_id",
    "normalized_text_sha256",
    "publication_month",
    "publication_year",
    "publication_year_month",
    SCORE_NAME,
    "sitename_hash",
    "split",
    "topic",
    "url_hostname_hash",
    "word_count",
}
RAW_INPUT_FIELDS = {
    "body",
    "content",
    "description",
    "normalized_text",
    "original_text",
    "preview",
    "text",
    "title",
    "url",
    "normalized_url",
    "warc_target_uri",
}
FORBIDDEN_PUBLIC_KEYS = RAW_INPUT_FIELDS | {"document_id", "identity_hash", "normalized_text_sha256"}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREDICTIONS = REPO_ROOT / "services/evals/publication_shift_model/infini_news_final_v1/publisher_domain_heldout_primary_predictions.jsonl"
DEFAULT_METADATA = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1/candidates/lexical_tfidf_logistic/model_metadata.json"
DEFAULT_ARTIFACT = REPO_ROOT / "services/evals/publication_shift_model/infini_news_final_v1/infini_news_word_char_tfidf_logistic.joblib"
DEFAULT_OUTPUT = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1/diagnostics/january_2024"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def assert_public_safe(payload: Any) -> None:
    """Reject row-level identifiers and any raw/normalized text-bearing field."""

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = key.lower()
                if (
                    lowered in FORBIDDEN_PUBLIC_KEYS
                    or "preview" in lowered
                    or "abstract" in lowered
                    or lowered.endswith("_text")
                ):
                    raise ValueError(f"public diagnostic contains forbidden key: {key}")
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)


def validate_frozen_model(metadata_path: Path, artifact_path: Path) -> dict[str, Any]:
    metadata_digest = sha256_file(metadata_path)
    if metadata_digest != METADATA_SHA256:
        raise ValueError(f"selected-candidate metadata checksum changed: {metadata_digest}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = {
        "model_id": MODEL_ID,
        "model_family": MODEL_FAMILY,
        "candidate_name": CANDIDATE_NAME,
        "score_name": SCORE_NAME,
        "threshold": THRESHOLD,
        "artifact_sha256": ARTIFACT_SHA256,
        "training_identity_sha256": TRAINING_IDENTITY_SHA256,
        "split_summary_sha256": SPLIT_SUMMARY_SHA256,
        "config": EXPECTED_CONFIG,
    }
    for key, expected_value in expected.items():
        if metadata.get(key) != expected_value:
            raise ValueError(f"frozen model metadata differs for {key}")
    artifact_digest = sha256_file(artifact_path)
    if artifact_digest != ARTIFACT_SHA256:
        raise ValueError(f"frozen model artifact checksum changed: {artifact_digest}")
    return metadata


def load_frozen_predictions(path: Path) -> list[dict[str, Any]]:
    digest = sha256_file(path)
    if digest != PREDICTIONS_SHA256:
        raise ValueError(f"frozen prediction checksum changed: {digest}")
    rows: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = REQUIRED_PREDICTION_FIELDS - row.keys()
            if missing:
                raise ValueError(f"prediction line {line_number} lacks fields: {sorted(missing)}")
            forbidden = RAW_INPUT_FIELDS & row.keys()
            if forbidden:
                raise ValueError(f"prediction line {line_number} includes raw fields: {sorted(forbidden)}")
            document_id = str(row["document_id"])
            if document_id in seen_documents:
                raise ValueError(f"duplicate document_id at line {line_number}")
            seen_documents.add(document_id)
            if row["lane"] != PRIMARY_LANE or row["split"] != "test" or row["model_family"] != MODEL_FAMILY:
                raise ValueError(f"prediction line {line_number} is not from the frozen primary test lane")
            if row["label"] not in (0, 1):
                raise ValueError(f"prediction line {line_number} has a non-binary label")
            score = float(row[SCORE_NAME])
            if not math.isfinite(score) or not 0.0 <= score <= 1.0:
                raise ValueError(f"prediction line {line_number} has an invalid score")
            rows.append(row)
    if not rows:
        raise ValueError("frozen prediction file is empty")
    return rows


def _quantile(sorted_values: Sequence[float], probability: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction)


def score_distribution(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(float(row[SCORE_NAME]) for row in rows)
    if not values:
        return {"count": 0, "mean": None, "p05": None, "p25": None, "median": None, "p75": None, "p95": None}
    return {
        "count": len(values),
        "mean": float(sum(values) / len(values)),
        "p05": _quantile(values, 0.05),
        "p25": _quantile(values, 0.25),
        "median": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p95": _quantile(values, 0.95),
    }


def metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    confusion = Counter()
    for row in rows:
        label = int(row["label"])
        prediction = int(float(row[SCORE_NAME]) >= THRESHOLD)
        confusion[(label, prediction)] += 1
    count = len(rows)
    correct = confusion[(0, 0)] + confusion[(1, 1)]
    errors = count - correct
    return {
        "count": count,
        "label_0_count": confusion[(0, 0)] + confusion[(0, 1)],
        "label_1_count": confusion[(1, 0)] + confusion[(1, 1)],
        "correct_count": correct,
        "error_count": errors,
        "accuracy": float(correct / count) if count else None,
        "error_rate": float(errors / count) if count else None,
        "true_negative": confusion[(0, 0)],
        "false_positive": confusion[(0, 1)],
        "false_negative": confusion[(1, 0)],
        "true_positive": confusion[(1, 1)],
        "score_distribution": score_distribution(rows),
    }


def _is_error(row: dict[str, Any]) -> bool:
    return int(float(row[SCORE_NAME]) >= THRESHOLD) != int(row["label"])


def _length_band(row: dict[str, Any]) -> str:
    value = row.get("word_count")
    if value is None:
        return "missing"
    count = int(value)
    if count < 150:
        return "under_150"
    if count < 300:
        return "150_299"
    if count < 500:
        return "300_499"
    if count < 750:
        return "500_749"
    if count < 1000:
        return "750_999"
    return "1000_plus"


def _missing_author(row: dict[str, Any]) -> str:
    return "missing" if not row.get("author_hash") else "present"


def slice_diagnostic(
    rows: Sequence[dict[str, Any]],
    extractor: Callable[[dict[str, Any]], str],
    *,
    limit: int = 15,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        extracted = extractor(row)
        buckets[str(extracted if extracted is not None else "missing")].append(row)
    total_errors = sum(_is_error(row) for row in rows)

    def item(group: str, group_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        summary = metrics(group_rows)
        return {
            "group": group,
            "count": summary["count"],
            "error_count": summary["error_count"],
            "accuracy": summary["accuracy"],
            "error_rate": summary["error_rate"],
            "error_share": float(summary["error_count"] / total_errors) if total_errors else 0.0,
            "score_mean": summary["score_distribution"]["mean"],
            "score_median": summary["score_distribution"]["median"],
        }

    all_items = [item(group, group_rows) for group, group_rows in buckets.items()]
    by_errors = sorted(all_items, key=lambda value: (-value["error_count"], -value["count"], value["group"]))
    by_support = sorted(all_items, key=lambda value: (-value["count"], value["group"]))

    def concentration(top_n: int) -> float:
        if not total_errors:
            return 0.0
        return float(sum(value["error_count"] for value in by_errors[:top_n]) / total_errors)

    return {
        "group_count": len(all_items),
        "top_by_error_count": by_errors[:limit],
        "top_by_support": by_support[:limit],
        "error_concentration": {"top_1_share": concentration(1), "top_3_share": concentration(3), "top_5_share": concentration(5)},
    }


def data_quality(rows: Sequence[dict[str, Any]], january_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "publication_year_month_mismatch_rows": 0,
        "corpus_role_label_mismatch_rows": 0,
        "missing_source_rows": 0,
        "missing_domain_rows": 0,
        "missing_topic_rows": 0,
        "missing_word_count_rows": 0,
        "missing_duplicate_cluster_rows": 0,
        "invalid_word_count_rows": 0,
        "january_non_current_label_rows": 0,
    }
    identity_counts: Counter[str] = Counter()
    normalized_hash_counts: Counter[str] = Counter()
    for row in rows:
        expected_year_month = f"{int(row['publication_year']):04d}-{int(row['publication_month']):02d}"
        checks["publication_year_month_mismatch_rows"] += row["publication_year_month"] != expected_year_month
        role = str(row.get("corpus_role") or "")
        expected_label = {"pre_llm_core": 0, "current_core": 1}.get(role)
        checks["corpus_role_label_mismatch_rows"] += expected_label is None or expected_label != row["label"]
        checks["missing_source_rows"] += not bool(row.get("sitename_hash"))
        checks["missing_domain_rows"] += not bool(row.get("url_hostname_hash"))
        checks["missing_topic_rows"] += not bool(row.get("topic"))
        checks["missing_word_count_rows"] += row.get("word_count") is None
        checks["missing_duplicate_cluster_rows"] += not bool(row.get("near_duplicate_cluster_id"))
        checks["invalid_word_count_rows"] += row.get("word_count") is not None and int(row["word_count"]) < 150
        identity_counts[str(row["identity_hash"])] += 1
        normalized_hash_counts[str(row["normalized_text_sha256"])] += 1
    checks["january_non_current_label_rows"] = sum(int(row["label"]) != 1 for row in january_rows)
    checks["duplicate_identity_rows"] = sum(count - 1 for count in identity_counts.values() if count > 1)
    checks["duplicate_normalized_hash_rows"] = sum(count - 1 for count in normalized_hash_counts.values() if count > 1)
    anomaly_count = sum(checks.values())
    return {
        "defect_detected": anomaly_count > 0,
        "anomaly_count": anomaly_count,
        "checks": checks,
        "conclusion": (
            "A possible data-processing defect is present in the frozen metadata fields."
            if anomaly_count
            else "No data-processing defect was detected in the frozen no-text metadata and prediction fields. This diagnostic cannot assess an unseen article-text pipeline."
        ),
    }


def build_diagnostic(rows: Sequence[dict[str, Any]], *, source_inputs: dict[str, Any]) -> dict[str, Any]:
    windows = {
        "december_2023": [row for row in rows if row["publication_year_month"] == "2023-12"],
        "january_2024": [row for row in rows if row["publication_year_month"] == "2024-01"],
        "february_2024": [row for row in rows if row["publication_year_month"] == "2024-02"],
        "remainder_of_2024": [
            row for row in rows if int(row["publication_year"]) == 2024 and int(row["publication_month"]) not in (1, 2)
        ],
        "overall_test": list(rows),
    }
    comparisons = {name: metrics(window_rows) for name, window_rows in windows.items()}
    january = windows["january_2024"]
    if comparisons["january_2024"]["count"] != 951:
        raise ValueError("frozen January 2024 support changed from 951")
    if comparisons["january_2024"]["correct_count"] != 580:
        raise ValueError("frozen January 2024 correct count changed from 580")
    slices = {
        "source": slice_diagnostic(january, lambda row: row.get("sitename_hash") or "missing"),
        "domain": slice_diagnostic(january, lambda row: row.get("url_hostname_hash") or "missing"),
        "topic": slice_diagnostic(january, lambda row: row.get("topic") or "missing"),
        "length_band": slice_diagnostic(january, _length_band),
        "missing_author": slice_diagnostic(january, _missing_author),
        "duplicate_cluster": slice_diagnostic(january, lambda row: row.get("near_duplicate_cluster_id") or "missing"),
    }
    leading_source = slices["source"]["top_by_error_count"][0]["group"]
    leading_source_windows = {
        name: metrics([row for row in window_rows if (row.get("sitename_hash") or "missing") == leading_source])
        for name, window_rows in windows.items()
        if name != "overall_test"
    }
    leading_source_missing_author_rows = sum(
        not row.get("author_hash") for row in january if (row.get("sitename_hash") or "missing") == leading_source
    )
    payload = {
        "schema": SCHEMA,
        "disclaimer": DISCLAIMER,
        "purpose": "Post-hoc diagnosis of existing frozen predictions only; not model selection, calibration, threshold tuning, or production scoring.",
        "frozen_model": {
            "model_id": MODEL_ID,
            "model_family": MODEL_FAMILY,
            "candidate_name": CANDIDATE_NAME,
            "score_name": SCORE_NAME,
            "threshold": THRESHOLD,
            "artifact_sha256": ARTIFACT_SHA256,
            "training_identity_sha256": TRAINING_IDENTITY_SHA256,
            "split_summary_sha256": SPLIT_SUMMARY_SHA256,
            "changed_or_tuned": False,
        },
        "source_inputs": source_inputs,
        "content_boundary": {
            "article_body_loaded": False,
            "row_level_records_published": False,
            "public_output": "Aggregate metrics and already-hashed source/domain identifiers only; no raw or normalized article content.",
        },
        "window_definitions": {
            "december_2023": "publication_year_month == 2023-12",
            "january_2024": "publication_year_month == 2024-01",
            "february_2024": "publication_year_month == 2024-02",
            "remainder_of_2024": "2024 excluding January and February",
            "overall_test": "all frozen publisher/domain-held-out primary test rows",
        },
        "comparisons": comparisons,
        "january_2024_slices": slices,
        "january_2024_error_concentration": {
            name: diagnostic["error_concentration"] for name, diagnostic in slices.items()
        },
        "leading_source_time_comparison": {
            "source_hash": leading_source,
            "windows": leading_source_windows,
            "january_missing_author_rows": leading_source_missing_author_rows,
            "conclusion": (
                "The leading source appears in the frozen 2024 test only in January, accounts for more than half of January errors, "
                "and has missing author metadata on every January row. This supports a source-composition explanation for the monthly dip; "
                "it does not by itself establish a text-pipeline defect or justify source-specific tuning."
            ),
        },
        "data_processing_diagnostic": data_quality(rows, january),
        "interpretation": {
            "status": "diagnosis_only",
            "threshold_selection": "unchanged frozen validation-selected threshold",
            "model_selection_or_tuning_performed": False,
            "production_integration": "none",
        },
    }
    assert_public_safe(payload)
    return payload


def _render_group_line(name: str, diagnostic: dict[str, Any]) -> str:
    leaders = diagnostic["top_by_error_count"][:3]
    rendered = "; ".join(
        f"`{item['group']}` ({item['error_count']} errors, {item['error_share']:.1%} of January errors, {item['accuracy']:.2%} accuracy)"
        for item in leaders
    )
    return f"- {name}: {rendered}"


def render_report(diagnostic: dict[str, Any]) -> str:
    comparisons = diagnostic["comparisons"]
    january = comparisons["january_2024"]
    slices = diagnostic["january_2024_slices"]
    lines = [
        "# January 2024 frozen-prediction diagnostic (no-text)",
        "",
        DISCLAIMER,
        "",
        "This is a post-hoc diagnostic of frozen predictions. It is not model selection, calibration, threshold tuning, retraining, or production scoring.",
        "",
        "## Frozen subject and data boundary",
        "",
        f"- Model ID: `{MODEL_ID}`",
        f"- Artifact SHA-256: `{ARTIFACT_SHA256}`",
        f"- Threshold: `{THRESHOLD}` (unchanged)",
        "- Inputs: frozen publisher/domain-held-out primary predictions plus frozen selected-candidate metadata.",
        "- Public output: aggregates and already-hashed source/domain identifiers; no article body, title, URL, or raw/normalized article content.",
        "",
        "## Time comparison",
        "",
        "| Window | N | Correct | Errors | Accuracy | Mean score | Median score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "december_2023": "December 2023",
        "january_2024": "January 2024",
        "february_2024": "February 2024",
        "remainder_of_2024": "Remainder of 2024 (Mar-Dec)",
        "overall_test": "Overall frozen test",
    }
    for key in labels:
        value = comparisons[key]
        distribution = value["score_distribution"]
        lines.append(
            f"| {labels[key]} | {value['count']} | {value['correct_count']} | {value['error_count']} | {value['accuracy']:.2%} | {distribution['mean']:.6f} | {distribution['median']:.6f} |"
        )
    lines.extend(
        [
            "",
            f"January 2024 recomputes to **{january['correct_count']}/{january['count']} = {january['accuracy']:.2%} accuracy** at the unchanged threshold.",
            "",
            "## Dominant January error contributors",
            "",
            _render_group_line("Source hash", slices["source"]),
            _render_group_line("Domain hash", slices["domain"]),
            _render_group_line("Topic", slices["topic"]),
            _render_group_line("Word-count band", slices["length_band"]),
            _render_group_line("Missing-author status", slices["missing_author"]),
            _render_group_line("Near-duplicate cluster", slices["duplicate_cluster"]),
            "",
            "The JSON artifact includes top-by-error and top-by-support tables plus top-1/top-3/top-5 error-concentration shares for every dimension.",
            "",
            "## Data-processing check",
            "",
            diagnostic["data_processing_diagnostic"]["conclusion"],
            "",
            "The checks cover date-field consistency, corpus-role/label consistency, source/domain/topic/length/cluster presence, January labels, duplicate identities, and duplicate normalized-content hashes. They do not inspect article content.",
            "",
            "## Source-composition finding",
            "",
            diagnostic["leading_source_time_comparison"]["conclusion"],
            "",
            f"The leading source hash contributes {diagnostic['january_2024_slices']['source']['top_by_error_count'][0]['error_share']:.1%} of January errors. "
            f"It has {diagnostic['leading_source_time_comparison']['windows']['january_2024']['count']} January rows, "
            f"{diagnostic['leading_source_time_comparison']['windows']['january_2024']['accuracy']:.2%} accuracy, and "
            f"{diagnostic['leading_source_time_comparison']['january_missing_author_rows']} rows with missing author metadata. "
            f"Its December, February, and March-December supports are "
            f"{diagnostic['leading_source_time_comparison']['windows']['december_2023']['count']}, "
            f"{diagnostic['leading_source_time_comparison']['windows']['february_2024']['count']}, and "
            f"{diagnostic['leading_source_time_comparison']['windows']['remainder_of_2024']['count']} respectively.",
            "",
            "## Interpretation boundary",
            "",
            "The observed January drop is diagnostic evidence only. No model, feature, threshold, split, prediction, or training/tuning input was changed.",
            "",
            DISCLAIMER,
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    assert_public_safe(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_outputs(output_dir: Path, diagnostic: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_path = output_dir / "diagnostic.json"
    report_path = output_dir / "REPORT.md"
    _write_json(diagnostic_path, diagnostic)
    report_path.write_text(render_report(diagnostic), encoding="utf-8")
    output_checksums = {
        "REPORT.md": sha256_file(report_path),
        "diagnostic.json": sha256_file(diagnostic_path),
    }
    checksum_payload = {"schema": CHECKSUM_SCHEMA, "files": output_checksums}
    _write_json(output_dir / "checksums.json", checksum_payload)
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(output_checksums.items())), encoding="utf-8"
    )
    return output_checksums


def run(*, predictions_path: Path, metadata_path: Path, artifact_path: Path, output_dir: Path) -> dict[str, Any]:
    validate_frozen_model(metadata_path, artifact_path)
    rows = load_frozen_predictions(predictions_path)
    source_inputs = {
        "predictions": {"path": _repo_path(predictions_path), "sha256": PREDICTIONS_SHA256, "row_count": len(rows)},
        "selected_candidate_metadata": {"path": _repo_path(metadata_path), "sha256": METADATA_SHA256},
        "model_artifact": {"path": _repo_path(artifact_path), "sha256": ARTIFACT_SHA256},
    }
    diagnostic = build_diagnostic(rows, source_inputs=source_inputs)
    write_outputs(output_dir, diagnostic)
    return diagnostic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = run(
        predictions_path=args.predictions,
        metadata_path=args.metadata,
        artifact_path=args.artifact,
        output_dir=args.output,
    )
    january = result["comparisons"]["january_2024"]
    print(json.dumps({"january_2024": {"count": january["count"], "accuracy": january["accuracy"]}, "output": _repo_path(args.output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
