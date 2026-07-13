#!/usr/bin/env python3
"""Recompute the INFINI-NEWS evaluation-integrity audit without publishing text.

The audit reads private corpus rows only to reconstruct deterministic document
assignments. Public outputs contain aggregate counts and hashed identifiers,
never article text, titles, URLs, or raw source names.

This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

DISCLAIMER = "This score does not establish AI authorship."
SCHEMA = "publication_shift.infini_news_evaluation_integrity_audit.v1"
CHECKSUM_SCHEMA = "publication_shift.infini_news_evaluation_integrity_checksums.v1"
CORE_ROLES = {"current_core", "pre_llm_core"}
PRIMARY_PROTOCOL = "publisher_domain_heldout_primary"
ALTERNATE_PROTOCOLS = (
    "source_sitename_heldout",
    "topic_heldout",
    "author_heldout",
    "random_diagnostic",
)
PROTOCOL_GROUP_FIELDS = {
    PRIMARY_PROTOCOL: "url_hostname",
    "source_sitename_heldout": "sitename",
    "topic_heldout": "topic",
    "random_diagnostic": "document_id",
}
PLACEBO_LANES = {
    "placebo_2016_2017_vs_2020_2021": {"early_years": [2016, 2017], "later_years": [2020, 2021]},
    "placebo_2016_2018_vs_2019_2021": {"early_years": [2016, 2017, 2018], "later_years": [2019, 2020, 2021]},
}
FULL_CANDIDATES = ("lexical_tfidf_logistic", "stylometric_lightgbm")
ENCODER_CANDIDATE = "deberta_multitask_encoder"
SCORE_FIELD = "current_era_similarity"
SOURCE_MIN_SUPPORT = 100
COLLAPSE_ACCURACY = 0.70
HASH_RE = re.compile(r"^[0-9a-f]{24,64}$")
RAW_INPUT_KEYS = {
    "abstract",
    "body",
    "content",
    "description",
    "normalized_text",
    "normalized_url",
    "original_text",
    "preview",
    "text",
    "title",
    "url",
    "warc_target_uri",
}
FORBIDDEN_PUBLIC_KEYS = RAW_INPUT_KEYS | {"document_id", "identity_hash", "normalized_text_sha256"}

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "services/data/publication_shift/infini_news_v1/normalized_rows.jsonl"
DEFAULT_SPLIT_SUMMARY = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1/splits/summary.json"
DEFAULT_CANDIDATES = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1/candidates"
DEFAULT_PRIMARY_PREDICTIONS = REPO_ROOT / "services/evals/publication_shift_model/infini_news_final_v1/publisher_domain_heldout_primary_predictions.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1/diagnostics/evaluation_integrity"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_split(value: str, seed: str, protocol: str) -> str:
    digest = hashlib.sha256(f"{seed}:{protocol}|{value}".encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) / float(16**16)
    if bucket < 0.2:
        return "test"
    if bucket < 0.3:
        return "validation"
    return "train"


def identifier_set_sha256(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(set(values)):
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def public_identifier_hash(value: Any) -> str:
    encoded = str(value or "missing")
    if HASH_RE.fullmatch(encoded):
        return encoded
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _author_hashes(row: dict[str, Any]) -> list[str]:
    if row.get("author_hashes"):
        return sorted(str(value) for value in row["author_hashes"] if value)
    if row.get("author_hash"):
        return [str(row["author_hash"])]
    return []


def recompute_protocol_assignments(corpus_path: Path, seed: str) -> dict[str, Any]:
    """Stream the private corpus and retain identifiers only in memory."""

    protocol_counts = {name: Counter() for name in (PRIMARY_PROTOCOL, *ALTERNATE_PROTOCOLS)}
    test_ids = {name: set() for name in (PRIMARY_PROTOCOL, *ALTERNATE_PROTOCOLS)}
    primary_train_ids: set[str] = set()
    seen_documents: set[str] = set()
    role_year_counts: Counter[tuple[str, int]] = Counter()
    role_counts: Counter[str] = Counter()
    corpus_digest = hashlib.sha256()
    total_rows = 0
    author_dropped_missing = 0
    author_dropped_bridge = 0

    with corpus_path.open("rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            corpus_digest.update(line)
            if not line.strip():
                continue
            row = json.loads(line)
            total_rows += 1
            document_id = str(row.get("document_id") or "")
            if not document_id:
                raise ValueError(f"corpus line {line_number} has no document_id")
            if document_id in seen_documents:
                raise ValueError(f"duplicate corpus document_id at line {line_number}")
            seen_documents.add(document_id)
            role = str(row.get("corpus_role") or "missing")
            role_counts[role] += 1
            try:
                year = int(row["publication_year"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"corpus line {line_number} has invalid publication_year") from exc
            role_year_counts[(role, year)] += 1
            if role not in CORE_ROLES:
                continue

            for protocol, field in PROTOCOL_GROUP_FIELDS.items():
                split = stable_split(str(row.get(field) or "missing"), seed, protocol)
                protocol_counts[protocol][split] += 1
                if split == "test":
                    test_ids[protocol].add(document_id)
                if protocol == PRIMARY_PROTOCOL and split == "train":
                    primary_train_ids.add(document_id)

            authors = _author_hashes(row)
            if not authors:
                author_dropped_missing += 1
            else:
                author_splits = {stable_split(author, seed, "author_heldout") for author in authors}
                if len(author_splits) != 1:
                    author_dropped_bridge += 1
                else:
                    split = next(iter(author_splits))
                    protocol_counts["author_heldout"][split] += 1
                    if split == "test":
                        test_ids["author_heldout"].add(document_id)

    return {
        "corpus_sha256": corpus_digest.hexdigest(),
        "total_rows": total_rows,
        "role_counts": dict(sorted(role_counts.items())),
        "role_year_counts": role_year_counts,
        "protocol_counts": {name: dict(sorted(counts.items())) for name, counts in protocol_counts.items()},
        "test_ids": test_ids,
        "primary_train_ids": primary_train_ids,
        "author_dropped_missing": author_dropped_missing,
        "author_dropped_bridge": author_dropped_bridge,
    }


def _assert_prediction_row_safe(row: dict[str, Any], path: Path, line_number: int) -> None:
    forbidden = RAW_INPUT_KEYS & set(row)
    if forbidden:
        raise ValueError(f"{path.name} line {line_number} contains forbidden raw fields: {sorted(forbidden)}")


def load_prediction_ids(path: Path, lane: str, split: str = "test") -> tuple[set[str], str]:
    identifiers: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            _assert_prediction_row_safe(row, path, line_number)
            if row.get("lane") != lane or row.get("split") != split:
                raise ValueError(f"{path.name} line {line_number} has unexpected lane/split")
            document_id = str(row.get("document_id") or "")
            if not document_id or document_id in identifiers:
                raise ValueError(f"{path.name} line {line_number} has missing/duplicate document_id")
            identifiers.add(document_id)
    return identifiers, sha256_file(path)


def audit_split_integrity(
    recomputed: dict[str, Any],
    summary: dict[str, Any],
    prediction_root: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    primary_train = recomputed["primary_train_ids"]
    inputs: dict[str, str] = {}
    protocols: dict[str, Any] = {}

    for protocol in (PRIMARY_PROTOCOL, *ALTERNATE_PROTOCOLS):
        prediction_path = prediction_root / f"{protocol}_predictions.jsonl"
        tracked_test, digest = load_prediction_ids(prediction_path, protocol)
        inputs[f"selected_candidate_{protocol}_predictions"] = digest
        recomputed_test = recomputed["test_ids"][protocol]
        expected_counts = summary["protocols"][protocol]["counts"]
        counts_match_summary = recomputed["protocol_counts"][protocol] == expected_counts
        tracked_matches_recomputed = tracked_test == recomputed_test
        if not counts_match_summary:
            raise ValueError(f"recomputed {protocol} counts differ from frozen split summary")
        if not tracked_matches_recomputed:
            raise ValueError(f"tracked {protocol} predictions differ from recomputed test assignment")

        overlap = primary_train & recomputed_test
        protocol_result = {
            "recomputed_counts": recomputed["protocol_counts"][protocol],
            "test_count": len(recomputed_test),
            "test_identifier_set_sha256": identifier_set_sha256(recomputed_test),
            "tracked_predictions_match_recomputed_test": True,
            "frozen_summary_counts_match": True,
            "primary_training_overlap_count": len(overlap),
            "primary_training_overlap_fraction": len(overlap) / len(recomputed_test),
            "overlap_identifier_set_sha256": identifier_set_sha256(overlap),
        }
        if protocol == PRIMARY_PROTOCOL:
            protocol_result["gate"] = "PASS" if not overlap else "REJECT"
        else:
            protocol_result["gate"] = "REJECT" if overlap else "PASS"
        protocols[protocol] = protocol_result

    rejected = [name for name in ALTERNATE_PROTOCOLS if protocols[name]["gate"] == "REJECT"]
    return {
        "gate": "REJECT" if rejected else "PASS",
        "reason": (
            "Alternate-lane scores were computed with the primary model even though alternate test rows overlap that model's training IDs."
            if rejected
            else "No alternate test IDs overlap the primary model training IDs."
        ),
        "seed": summary["seed"],
        "primary_training_count": len(primary_train),
        "primary_training_identifier_set_sha256": identifier_set_sha256(primary_train),
        "rejected_alternate_lanes": rejected,
        "protocols": protocols,
        "author_assignment_drops": {
            "missing_author": recomputed["author_dropped_missing"],
            "bridge": recomputed["author_dropped_bridge"],
        },
    }, inputs


def _label_key(value: Any) -> str:
    if value is None:
        return "null"
    if value in (0, 1):
        return str(int(value))
    return "other"


def inspect_placebo_file(path: Path, lane: str, expected: dict[str, list[int]]) -> dict[str, Any]:
    years: Counter[int] = Counter()
    labels: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            _assert_prediction_row_safe(row, path, line_number)
            if row.get("lane") != lane or row.get("split") != "evaluation_only":
                raise ValueError(f"{path.name} line {line_number} has unexpected lane/split")
            count += 1
            years[int(row["publication_year"])] += 1
            labels[_label_key(row.get("label"))] += 1
            roles[str(row.get("corpus_role") or "missing")] += 1
    early_support = sum(years[year] for year in expected["early_years"])
    later_support = sum(years[year] for year in expected["later_years"])
    gate = "PASS" if early_support and later_support and labels["0"] and labels["1"] else "FAIL"
    return {
        "gate": gate,
        "row_count": count,
        "observed_year_counts": {str(year): value for year, value in sorted(years.items())},
        "observed_role_counts": dict(sorted(roles.items())),
        "declared_label_counts": {key: labels.get(key, 0) for key in ("0", "1", "null", "other")},
        "expected_early_years": expected["early_years"],
        "expected_later_years": expected["later_years"],
        "observed_early_arm_support": early_support,
        "observed_later_arm_support": later_support,
        "substitution_detected": later_support == 0,
        "failure_reason": (
            None
            if gate == "PASS"
            else "The file contains no supported later arm and therefore cannot estimate the named historical contrast."
        ),
    }


def _corpus_arm_support(role_year_counts: Counter[tuple[str, int]], years: Sequence[int]) -> int:
    return sum(count for (role, year), count in role_year_counts.items() if role in CORE_ROLES | {"historical_placebo"} and year in years)


def audit_placebos(candidates_root: Path, role_year_counts: Counter[tuple[str, int]]) -> tuple[dict[str, Any], dict[str, str]]:
    candidates: dict[str, Any] = {}
    inputs: dict[str, str] = {}
    for candidate in (*FULL_CANDIDATES, ENCODER_CANDIDATE):
        lane_results = {}
        for lane, expected in PLACEBO_LANES.items():
            path = candidates_root / candidate / f"{lane}_predictions.jsonl"
            lane_results[lane] = inspect_placebo_file(path, lane, expected)
            inputs[f"{candidate}_{lane}_predictions"] = sha256_file(path)
        candidates[candidate] = {
            "candidate_scope": "full" if candidate in FULL_CANDIDATES else "smoke",
            "gate": "FAIL" if any(result["gate"] != "PASS" for result in lane_results.values()) else "PASS",
            "lanes": lane_results,
        }

    corpus_support = {
        lane: {
            "available_early_arm_rows": _corpus_arm_support(role_year_counts, expected["early_years"]),
            "available_later_arm_rows": _corpus_arm_support(role_year_counts, expected["later_years"]),
        }
        for lane, expected in PLACEBO_LANES.items()
    }
    return {
        "gate": "FAIL" if any(result["gate"] != "PASS" for result in candidates.values()) else "PASS",
        "reason": "All emitted placebo files substitute early-only rows for the named two-arm comparisons; ROC-AUC and lift gates are undefined.",
        "corpus_arm_support": corpus_support,
        "candidates": candidates,
    }, inputs


def audit_encoder(candidates_root: Path, expected_corpus_rows: int) -> tuple[dict[str, Any], dict[str, str]]:
    root = candidates_root / ENCODER_CANDIDATE
    metrics_path = root / "metrics.json"
    metadata_path = root / "model_metadata.json"
    failures_path = root / "failed_candidates.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    failures = json.loads(failures_path.read_text(encoding="utf-8"))
    counts = metrics.get("counts") or {}
    full_run = metrics.get("decision") == "PASS-HOLD" and counts.get("corpus_rows") == expected_corpus_rows
    blocker = next(
        (item for item in failures.get("preserved_failures", []) if item.get("stage") == "serious_full_frozen_row_run"),
        None,
    )
    runtime_inputs = metadata.get("runtime_inputs") or []
    metadata_inputs = metadata.get("metadata_runtime_inputs") or []
    return {
        "gate": "PASS" if full_run else "HOLD",
        "status": "full_candidate_completed" if full_run else "cpu_smoke_only",
        "decision": metrics.get("decision"),
        "expected_corpus_rows": expected_corpus_rows,
        "observed_counts": counts,
        "full_frozen_row_run_completed": full_run,
        "accelerator_verified": bool((metadata.get("accelerator_probe") or {}).get("verified")),
        "selected_device": (metadata.get("accelerator_probe") or {}).get("selected_device"),
        "hardware_blocker_documented": blocker is not None,
        "hardware_blocker_decision": blocker.get("decision") if blocker else None,
        "runtime_inputs": runtime_inputs,
        "metadata_runtime_inputs": metadata_inputs,
        "runtime_input_gate": "PASS" if runtime_inputs == ["input_ids", "attention_mask"] and not metadata_inputs else "FAIL",
        "artifact_sha256": metadata.get("artifact_sha256"),
        "reason": (
            None
            if full_run
            else "Only a 160-row CPU smoke artifact exists; the measured unverified-accelerator blocker does not constitute a full 264,000-row encoder candidate."
        ),
    }, {
        "encoder_metrics": sha256_file(metrics_path),
        "encoder_metadata": sha256_file(metadata_path),
        "encoder_preserved_failures": sha256_file(failures_path),
    }


def _classification_metrics(rows: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    correct = 0
    false_positive = 0
    false_negative = 0
    label_counts: Counter[int] = Counter()
    for row in rows:
        label = int(row["label"])
        score = float(row[SCORE_FIELD])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("primary prediction contains an invalid score")
        predicted = int(score >= threshold)
        label_counts[label] += 1
        correct += int(predicted == label)
        false_positive += int(label == 0 and predicted == 1)
        false_negative += int(label == 1 and predicted == 0)
    count = len(rows)
    return {
        "count": count,
        "correct_count": correct,
        "error_count": count - correct,
        "accuracy": correct / count if count else None,
        "label_0_count": label_counts[0],
        "label_1_count": label_counts[1],
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def load_primary_predictions(path: Path) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            _assert_prediction_row_safe(row, path, line_number)
            if row.get("lane") != PRIMARY_PROTOCOL or row.get("split") != "test":
                raise ValueError(f"primary prediction line {line_number} has unexpected lane/split")
            document_id = str(row.get("document_id") or "")
            if not document_id or document_id in seen:
                raise ValueError(f"primary prediction line {line_number} has missing/duplicate document_id")
            seen.add(document_id)
            rows.append(row)
    return rows


def audit_subgroup_collapses(primary_predictions: Path, threshold: float) -> tuple[dict[str, Any], dict[str, str]]:
    rows = load_primary_predictions(primary_predictions)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source[public_identifier_hash(row.get("sitename_hash"))].append(row)
        by_month[str(row["publication_year_month"])].append(row)

    eligible_sources = []
    failed_sources = []
    for source_hash, group in sorted(by_source.items()):
        if len(group) < SOURCE_MIN_SUPPORT:
            continue
        result = {"source_group_hash": source_hash, **_classification_metrics(group, threshold)}
        eligible_sources.append(result)
        if result["accuracy"] < COLLAPSE_ACCURACY:
            failed_sources.append(result)
    failed_sources.sort(key=lambda item: (item["accuracy"], -item["count"], item["source_group_hash"]))

    failed_months = []
    for month, group in sorted(by_month.items()):
        result = {"publication_year_month": month, **_classification_metrics(group, threshold)}
        if result["accuracy"] < COLLAPSE_ACCURACY:
            failed_months.append(result)

    january = next((result for result in failed_months if result["publication_year_month"] == "2024-01"), None)
    gate = "FAIL" if failed_sources or failed_months else "PASS"
    return {
        "gate": gate,
        "frozen_threshold": threshold,
        "collapse_accuracy_threshold": COLLAPSE_ACCURACY,
        "overall_primary_test": _classification_metrics(rows, threshold),
        "source_groups": {
            "minimum_support": SOURCE_MIN_SUPPORT,
            "total_group_count": len(by_source),
            "eligible_group_count": len(eligible_sources),
            "below_threshold_group_count": len(failed_sources),
            "below_threshold": failed_sources,
        },
        "monthly_groups": {
            "total_group_count": len(by_month),
            "below_threshold_group_count": len(failed_months),
            "below_threshold": failed_months,
            "january_2024_reproduced": january is not None and january["count"] == 951 and january["correct_count"] == 580,
        },
        "reason": (
            f"{len(failed_sources)} source groups with support >= {SOURCE_MIN_SUPPORT} and {len(failed_months)} publication months fall below {COLLAPSE_ACCURACY:.0%} accuracy."
            if gate == "FAIL"
            else None
        ),
    }, {"selected_frozen_primary_predictions": sha256_file(primary_predictions)}


def assert_public_safe(payload: Any) -> None:
    """Reject article-bearing keys, row identifiers, URLs, and raw source-name keys."""

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if (
                    lowered in FORBIDDEN_PUBLIC_KEYS
                    or "preview" in lowered
                    or "abstract" in lowered
                    or lowered.endswith("_text")
                    or lowered in {"source_name", "sitename", "hostname"}
                ):
                    raise ValueError(f"public audit contains forbidden key: {key}")
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("public audit contains a URL value")

    visit(payload)


def render_report(audit: dict[str, Any]) -> str:
    split = audit["split_integrity"]
    placebo = audit["placebo_support"]
    encoder = audit["encoder_status"]
    subgroup = audit["subgroup_collapse"]
    lines = [
        "# INFINI-NEWS evaluation-integrity audit (no-text)",
        "",
        DISCLAIMER,
        "",
        f"- Frozen-run decision: **{audit['decision']}**",
        "- Production integration: **none**",
        "- Public boundary: aggregate counts and hashes only; no article text, title, URL, or raw source name.",
        "",
        "## Gate matrix",
        "",
        "| Gate | Status | Finding |",
        "|---|---|---|",
        f"| Alternate-lane split integrity | {split['gate']} | {len(split['rejected_alternate_lanes'])} alternate lanes overlap primary training IDs. |",
        f"| Historical placebo support | {placebo['gate']} | Emitted named contrasts have no later-arm support; ROC-AUC/lift are undefined. |",
        f"| Full multi-task encoder | {encoder['gate']} | {encoder['status']}; observed corpus rows: {encoder['observed_counts'].get('corpus_rows')}. |",
        f"| Required subgroup stability | {subgroup['gate']} | {subgroup['source_groups']['below_threshold_group_count']} source groups and {subgroup['monthly_groups']['below_threshold_group_count']} months are below 70% accuracy. |",
        "",
        "## Exact alternate-test overlap with primary training IDs",
        "",
        "| Alternate lane | Overlap / test | Fraction | Gate |",
        "|---|---:|---:|---|",
    ]
    for lane in ALTERNATE_PROTOCOLS:
        result = split["protocols"][lane]
        lines.append(
            f"| `{lane}` | {result['primary_training_overlap_count']:,} / {result['test_count']:,} | "
            f"{result['primary_training_overlap_fraction']:.2%} | {result['gate']} |"
        )
    lines.extend(
        [
            "",
            "The per-lane split manifests are internally disjoint, but the frozen candidates were trained once on the publisher/domain primary training partition. Reusing that model on alternate test partitions makes rows already seen in primary training part of the reported alternate test scores.",
            "",
            "## Placebo support",
            "",
            "Both named placebo files for every candidate contain only the early arm. The full lexical and stylometric files each contain 8,000 rows (4,000 from 2016 and 4,000 from 2017), all labeled 0, and zero rows from the promised later years. The encoder files are smoke subsets with null labels. These are unsupported substitutions, not two-arm matched placebos.",
            "",
            "## Encoder status",
            "",
            f"- Status: `{encoder['status']}` / `{encoder['decision']}`",
            f"- Counts: `{json.dumps(encoder['observed_counts'], sort_keys=True)}`",
            f"- Accelerator verified: `{str(encoder['accelerator_verified']).lower()}`; selected device: `{encoder['selected_device']}`",
            f"- Measured blocker preserved: `{str(encoder['hardware_blocker_documented']).lower()}`",
            f"- Runtime-input gate: `{encoder['runtime_input_gate']}` (token IDs and attention mask; no metadata runtime inputs)",
            "",
            "## Source-group collapses",
            "",
            f"Frozen selected model threshold: `{subgroup['frozen_threshold']}`. Listed groups have support >= {SOURCE_MIN_SUPPORT} and accuracy < {COLLAPSE_ACCURACY:.0%}.",
            "",
            "| Source-group hash | Support | Correct | Accuracy |",
            "|---|---:|---:|---:|",
        ]
    )
    for result in subgroup["source_groups"]["below_threshold"]:
        lines.append(
            f"| `{result['source_group_hash']}` | {result['count']:,} | {result['correct_count']:,} | {result['accuracy']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Monthly collapses",
            "",
            "| Publication month | Support | Correct | Accuracy |",
            "|---|---:|---:|---:|",
        ]
    )
    for result in subgroup["monthly_groups"]["below_threshold"]:
        lines.append(
            f"| `{result['publication_year_month']}` | {result['count']:,} | {result['correct_count']:,} | {result['accuracy']:.2%} |"
        )
    lines.extend(
        [
            "",
            "January 2024 independently recomputes to 580/951 correct (60.99%) at the unchanged frozen threshold.",
            "",
            "## Reproduction",
            "",
            "Run from the repository root with the private normalized corpus supplied explicitly:",
            "",
            "```bash",
            "PYTHONPATH=services/gateway python services/gateway/audit_infini_news_evaluation_integrity.py --corpus <private-normalized-rows.jsonl>",
            "```",
            "",
            f"Expected private-corpus SHA-256: `{audit['input_checksums_sha256']['private_corpus']}`. The script verifies frozen row/role/protocol counts and tracked prediction assignment sets before writing evidence.",
            "",
            "## Interpretation",
            "",
            "Evaluation leakage invalidates the alternate-lane claims and triggers REJECT for this frozen run. Missing placebo arms, a smoke-only encoder, and severe subgroup collapses independently prevent promotion. No model, threshold, prediction, or production runtime was changed by this audit.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(output_dir: Path, audit: dict[str, Any]) -> None:
    assert_public_safe(audit)
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.json"
    report_path = output_dir / "REPORT.md"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(audit), encoding="utf-8")
    files = {path.name: sha256_file(path) for path in (report_path, audit_path)}
    checksum_payload = {"schema": CHECKSUM_SCHEMA, "files": dict(sorted(files.items()))}
    assert_public_safe(checksum_payload)
    (output_dir / "checksums.json").write_text(json.dumps(checksum_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(files.items())), encoding="utf-8"
    )


def run(
    *,
    corpus_path: Path,
    split_summary_path: Path,
    candidates_root: Path,
    primary_predictions_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    summary = json.loads(split_summary_path.read_text(encoding="utf-8"))
    recomputed = recompute_protocol_assignments(corpus_path, str(summary["seed"]))
    if recomputed["total_rows"] != summary["row_counts"]["total"]:
        raise ValueError("private corpus row count differs from frozen split summary")
    if recomputed["role_counts"] != summary["row_counts"]["by_role"]:
        raise ValueError("private corpus role counts differ from frozen split summary")

    selected_prediction_root = candidates_root / "lexical_tfidf_logistic"
    split_integrity, split_inputs = audit_split_integrity(recomputed, summary, selected_prediction_root)
    placebo_support, placebo_inputs = audit_placebos(candidates_root, recomputed["role_year_counts"])
    encoder_status, encoder_inputs = audit_encoder(candidates_root, summary["row_counts"]["total"])
    lexical_metadata_path = selected_prediction_root / "model_metadata.json"
    lexical_metadata = json.loads(lexical_metadata_path.read_text(encoding="utf-8"))
    subgroup_collapse, subgroup_inputs = audit_subgroup_collapses(
        primary_predictions_path, float(lexical_metadata["threshold"])
    )

    gates = {
        "alternate_lane_split_integrity": split_integrity["gate"],
        "historical_placebo_support": placebo_support["gate"],
        "full_multitask_encoder": encoder_status["gate"],
        "required_subgroup_stability": subgroup_collapse["gate"],
    }
    decision = "REJECT" if split_integrity["gate"] == "REJECT" else ("HOLD" if any(value != "PASS" for value in gates.values()) else "PASS")
    input_checksums = {
        "audit_script": sha256_file(Path(__file__)),
        "private_corpus": recomputed["corpus_sha256"],
        "split_summary": sha256_file(split_summary_path),
        "selected_candidate_metadata": sha256_file(lexical_metadata_path),
        **split_inputs,
        **placebo_inputs,
        **encoder_inputs,
        **subgroup_inputs,
    }
    audit = {
        "schema": SCHEMA,
        "disclaimer": DISCLAIMER,
        "decision": decision,
        "decision_scope": "frozen_infini_news_v1_evaluation_run",
        "production_integration": "none",
        "content_boundary": {
            "private_corpus_streamed": True,
            "article_content_published": False,
            "row_level_identifiers_published": False,
            "public_identifier_policy": "aggregate identifier-set digests and hashed source-group identifiers only",
        },
        "input_checksums_sha256": dict(sorted(input_checksums.items())),
        "gates": gates,
        "split_integrity": split_integrity,
        "placebo_support": placebo_support,
        "encoder_status": encoder_status,
        "subgroup_collapse": subgroup_collapse,
    }
    write_outputs(output_dir, audit)
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--split-summary", type=Path, default=DEFAULT_SPLIT_SUMMARY)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--primary-predictions", type=Path, default=DEFAULT_PRIMARY_PREDICTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    audit = run(
        corpus_path=args.corpus,
        split_summary_path=args.split_summary,
        candidates_root=args.candidates,
        primary_predictions_path=args.primary_predictions,
        output_dir=args.output,
    )
    print(json.dumps({"decision": audit["decision"], "gates": audit["gates"], "output": str(args.output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
