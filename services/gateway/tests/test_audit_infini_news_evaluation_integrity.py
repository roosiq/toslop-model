import hashlib
import json
from pathlib import Path

import pytest

from audit_infini_news_evaluation_integrity import (
    ALTERNATE_PROTOCOLS,
    CHECKSUM_SCHEMA,
    COLLAPSE_ACCURACY,
    DEFAULT_OUTPUT,
    DISCLAIMER,
    PLACEBO_LANES,
    PRIMARY_PROTOCOL,
    SCHEMA,
    assert_public_safe,
    audit_split_integrity,
    audit_subgroup_collapses,
    inspect_placebo_file,
    recompute_protocol_assignments,
    sha256_file,
    write_outputs,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_streaming_recomputation_exposes_cross_protocol_training_overlap(tmp_path):
    seed = "fixture_seed"
    corpus_path = tmp_path / "normalized_rows.jsonl"
    rows = []
    for index in range(500):
        rows.append(
            {
                "document_id": _digest(f"document-{index}"),
                "corpus_role": "current_core" if index % 2 else "pre_llm_core",
                "publication_year": 2024 if index % 2 else 2020,
                "url_hostname": _digest(f"domain-{index % 29}"),
                "sitename": _digest(f"source-{index % 31}"),
                "topic": _digest(f"topic-{index % 11}"),
                "author_hash": _digest(f"author-{index % 113}"),
            }
        )
    _write_jsonl(corpus_path, rows)
    recomputed = recompute_protocol_assignments(corpus_path, seed)

    prediction_root = tmp_path / "predictions"
    for protocol in (PRIMARY_PROTOCOL, *ALTERNATE_PROTOCOLS):
        _write_jsonl(
            prediction_root / f"{protocol}_predictions.jsonl",
            [
                {"document_id": document_id, "lane": protocol, "split": "test"}
                for document_id in sorted(recomputed["test_ids"][protocol])
            ],
        )
    summary = {
        "seed": seed,
        "protocols": {
            protocol: {"counts": recomputed["protocol_counts"][protocol]}
            for protocol in (PRIMARY_PROTOCOL, *ALTERNATE_PROTOCOLS)
        },
    }
    result, _ = audit_split_integrity(recomputed, summary, prediction_root)

    assert result["protocols"][PRIMARY_PROTOCOL]["primary_training_overlap_count"] == 0
    assert result["gate"] == "REJECT"
    assert result["rejected_alternate_lanes"]
    for lane in result["rejected_alternate_lanes"]:
        assert result["protocols"][lane]["primary_training_overlap_count"] > 0
        assert result["protocols"][lane]["tracked_predictions_match_recomputed_test"] is True


def test_placebo_audit_rejects_early_only_substitution(tmp_path):
    lane = "placebo_2016_2017_vs_2020_2021"
    path = tmp_path / f"{lane}_predictions.jsonl"
    _write_jsonl(
        path,
        [
            {
                "document_id": _digest(f"placebo-{index}"),
                "lane": lane,
                "split": "evaluation_only",
                "publication_year": 2016 + index % 2,
                "corpus_role": "historical_placebo",
                "label": 0,
            }
            for index in range(20)
        ],
    )

    result = inspect_placebo_file(path, lane, PLACEBO_LANES[lane])

    assert result["gate"] == "FAIL"
    assert result["observed_early_arm_support"] == 20
    assert result["observed_later_arm_support"] == 0
    assert result["declared_label_counts"] == {"0": 20, "1": 0, "null": 0, "other": 0}
    assert result["substitution_detected"] is True


def test_subgroup_audit_uses_frozen_threshold_and_hashes_source_identifiers(tmp_path):
    path = tmp_path / "primary_predictions.jsonl"
    rows = []
    for index in range(120):
        rows.append(
            {
                "document_id": _digest(f"primary-{index}"),
                "lane": PRIMARY_PROTOCOL,
                "split": "test",
                "label": 1,
                "current_era_similarity": 0.1 if index < 100 else 0.9,
                "sitename_hash": "synthetic source name",
                "publication_year_month": "2024-01",
            }
        )
    _write_jsonl(path, rows)

    result, _ = audit_subgroup_collapses(path, threshold=0.5)

    assert result["gate"] == "FAIL"
    assert result["collapse_accuracy_threshold"] == COLLAPSE_ACCURACY
    failed_source = result["source_groups"]["below_threshold"][0]
    assert failed_source["count"] == 120
    assert failed_source["correct_count"] == 20
    assert failed_source["source_group_hash"] == _digest("synthetic source name")
    assert result["monthly_groups"]["below_threshold"][0]["publication_year_month"] == "2024-01"


def test_committed_audit_records_exact_failed_gates_and_reviewer_counts():
    audit = json.loads((DEFAULT_OUTPUT / "audit.json").read_text(encoding="utf-8"))

    assert audit["schema"] == SCHEMA
    assert audit["disclaimer"] == DISCLAIMER
    assert audit["decision"] == "REJECT"
    assert audit["gates"] == {
        "alternate_lane_split_integrity": "REJECT",
        "full_multitask_encoder": "HOLD",
        "historical_placebo_support": "FAIL",
        "required_subgroup_stability": "FAIL",
    }
    protocols = audit["split_integrity"]["protocols"]
    assert (protocols["source_sitename_heldout"]["primary_training_overlap_count"], protocols["source_sitename_heldout"]["test_count"]) == (31459, 50320)
    assert (protocols["topic_heldout"]["primary_training_overlap_count"], protocols["topic_heldout"]["test_count"]) == (34944, 52617)
    assert (protocols["author_heldout"]["primary_training_overlap_count"], protocols["author_heldout"]["test_count"]) == (30197, 45237)
    assert (protocols["random_diagnostic"]["primary_training_overlap_count"], protocols["random_diagnostic"]["test_count"]) == (34153, 50751)
    assert audit["encoder_status"]["status"] == "cpu_smoke_only"
    assert audit["encoder_status"]["observed_counts"]["corpus_rows"] == 160
    assert audit["subgroup_collapse"]["source_groups"]["below_threshold_group_count"] == 4
    assert audit["subgroup_collapse"]["monthly_groups"]["january_2024_reproduced"] is True


def test_public_outputs_are_deterministic_safe_and_checksummed(tmp_path):
    audit = json.loads((DEFAULT_OUTPUT / "audit.json").read_text(encoding="utf-8"))
    assert_public_safe(audit)
    with pytest.raises(ValueError):
        assert_public_safe({"title": "forbidden"})
    with pytest.raises(ValueError):
        assert_public_safe({"source_name": "forbidden"})
    with pytest.raises(ValueError):
        assert_public_safe({"value": "https://forbidden.invalid"})

    write_outputs(tmp_path, audit)
    first = {path.name: path.read_bytes() for path in sorted(tmp_path.iterdir())}
    write_outputs(tmp_path, audit)
    second = {path.name: path.read_bytes() for path in sorted(tmp_path.iterdir())}
    assert first == second
    assert first["audit.json"] == (DEFAULT_OUTPUT / "audit.json").read_bytes()
    assert first["REPORT.md"] == (DEFAULT_OUTPUT / "REPORT.md").read_bytes()

    checksums = json.loads((DEFAULT_OUTPUT / "checksums.json").read_text(encoding="utf-8"))
    assert checksums["schema"] == CHECKSUM_SCHEMA
    for name, expected in checksums["files"].items():
        assert sha256_file(DEFAULT_OUTPUT / name) == expected
    assert (DEFAULT_OUTPUT / "checksums.sha256").read_text(encoding="utf-8") == "".join(
        f"{digest}  {name}\n" for name, digest in sorted(checksums["files"].items())
    )
    for item in audit["subgroup_collapse"]["source_groups"]["below_threshold"]:
        assert len(item["source_group_hash"]) in (24, 64)
        int(item["source_group_hash"], 16)
