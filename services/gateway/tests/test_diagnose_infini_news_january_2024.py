import json
from pathlib import Path

import pytest

from diagnose_infini_news_january_2024 import (
    CANDIDATE_ARTIFACT_SHA256,
    DEFAULT_CANDIDATE_ARTIFACT,
    DEFAULT_DECISION_PACKET,
    DEFAULT_FINAL_ARTIFACT,
    DEFAULT_METADATA,
    DEFAULT_PREDICTIONS,
    DISCLAIMER,
    METADATA_SHA256,
    MODEL_ID,
    PREDICTIONS_SHA256,
    THRESHOLD,
    assert_public_safe,
    run,
    sha256_file,
    validate_hold_release,
    validate_reviewed_candidate,
)


def _output_bytes(output_dir: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(output_dir.iterdir()) if path.is_file()}


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("january-diagnostic")
    before = {
        "predictions": sha256_file(DEFAULT_PREDICTIONS),
        "metadata": sha256_file(DEFAULT_METADATA),
        "candidate_artifact": sha256_file(DEFAULT_CANDIDATE_ARTIFACT),
        "decision_packet": sha256_file(DEFAULT_DECISION_PACKET),
        "final_artifact_present": DEFAULT_FINAL_ARTIFACT.exists(),
    }
    result = run(
        predictions_path=DEFAULT_PREDICTIONS,
        metadata_path=DEFAULT_METADATA,
        candidate_artifact_path=DEFAULT_CANDIDATE_ARTIFACT,
        decision_packet_path=DEFAULT_DECISION_PACKET,
        final_artifact_path=DEFAULT_FINAL_ARTIFACT,
        output_dir=output_dir,
    )
    after = {
        "predictions": sha256_file(DEFAULT_PREDICTIONS),
        "metadata": sha256_file(DEFAULT_METADATA),
        "candidate_artifact": sha256_file(DEFAULT_CANDIDATE_ARTIFACT),
        "decision_packet": sha256_file(DEFAULT_DECISION_PACKET),
        "final_artifact_present": DEFAULT_FINAL_ARTIFACT.exists(),
    }
    return result, output_dir, before, after


def test_recomputes_january_accuracy_and_required_time_comparisons(generated):
    result, _, _, _ = generated
    comparisons = result["comparisons"]

    assert list(comparisons) == [
        "december_2023",
        "january_2024",
        "february_2024",
        "remainder_of_2024",
        "overall_test",
    ]
    assert comparisons["december_2023"]["count"] == 669
    assert comparisons["january_2024"]["count"] == 951
    assert comparisons["january_2024"]["correct_count"] == 580
    assert comparisons["january_2024"]["error_count"] == 371
    assert comparisons["january_2024"]["accuracy"] == pytest.approx(0.6098843322818086)
    assert comparisons["february_2024"]["count"] == 706
    assert comparisons["remainder_of_2024"]["count"] == 6232
    assert comparisons["overall_test"]["count"] == 55383


def test_reports_required_no_text_slices_and_dominant_error_contributors(generated):
    result, _, _, _ = generated
    slices = result["january_2024_slices"]

    assert set(slices) == {
        "source",
        "domain",
        "topic",
        "length_band",
        "missing_author",
        "duplicate_cluster",
    }
    for diagnostic in slices.values():
        assert diagnostic["group_count"] > 0
        assert diagnostic["top_by_error_count"]
        assert diagnostic["top_by_support"]
        assert set(diagnostic["error_concentration"]) == {"top_1_share", "top_3_share", "top_5_share"}
        assert diagnostic["error_concentration"]["top_1_share"] <= diagnostic["error_concentration"]["top_3_share"]
        assert diagnostic["error_concentration"]["top_3_share"] <= diagnostic["error_concentration"]["top_5_share"]

    assert slices["source"]["top_by_error_count"][0]["error_count"] == 212
    assert slices["topic"]["top_by_error_count"][0]["group"] == "economy_business_finance"
    assert slices["length_band"]["top_by_error_count"][0]["group"] == "500_749"
    assert slices["missing_author"]["top_by_error_count"][0]["group"] == "missing"
    assert result["data_processing_diagnostic"]["defect_detected"] is False
    assert result["data_processing_diagnostic"]["anomaly_count"] == 0

    source_time = result["leading_source_time_comparison"]
    assert source_time["source_hash"] == "01749ccf37ee4b7bce18df5a"
    assert source_time["windows"]["january_2024"]["count"] == 243
    assert source_time["windows"]["january_2024"]["accuracy"] == pytest.approx(31 / 243)
    assert source_time["january_missing_author_rows"] == 243
    assert source_time["windows"]["december_2023"]["count"] == 0
    assert source_time["windows"]["february_2024"]["count"] == 0
    assert source_time["windows"]["remainder_of_2024"]["count"] == 0


def test_frozen_inputs_candidate_identity_and_hold_status_are_immutable(generated):
    result, _, before, after = generated

    assert before == after == {
        "predictions": PREDICTIONS_SHA256,
        "metadata": METADATA_SHA256,
        "candidate_artifact": CANDIDATE_ARTIFACT_SHA256,
        "decision_packet": sha256_file(DEFAULT_DECISION_PACKET),
        "final_artifact_present": False,
    }
    reviewed = result["reviewed_candidate"]
    assert reviewed["model_id"] == MODEL_ID
    assert reviewed["threshold"] == THRESHOLD
    assert reviewed["source_artifact_sha256"] == CANDIDATE_ARTIFACT_SHA256
    assert reviewed["selection_status"] == "reviewed_not_selected"
    assert reviewed["artifact_used_for_scoring"] is False
    assert reviewed["changed_or_tuned"] is False
    assert result["release_status"] == {
        "decision": "HOLD",
        "selected_candidate": None,
        "selected_model": None,
        "artifact_freeze": "not_performed",
        "reviewed_candidate_selection_status": "reviewed_not_selected",
        "final_artifact_present": False,
    }
    assert result["interpretation"]["model_selection_or_tuning_performed"] is False
    assert result["disclaimer"] == DISCLAIMER


def test_public_outputs_are_deterministic_text_free_and_checksummed(generated):
    result, output_dir, _, _ = generated
    first = _output_bytes(output_dir)

    run(
        predictions_path=DEFAULT_PREDICTIONS,
        metadata_path=DEFAULT_METADATA,
        candidate_artifact_path=DEFAULT_CANDIDATE_ARTIFACT,
        decision_packet_path=DEFAULT_DECISION_PACKET,
        final_artifact_path=DEFAULT_FINAL_ARTIFACT,
        output_dir=output_dir,
    )
    second = _output_bytes(output_dir)
    assert second == first

    checksums = json.loads((output_dir / "checksums.json").read_text(encoding="utf-8"))
    for name, expected in checksums["files"].items():
        assert sha256_file(output_dir / name) == expected
    assert (output_dir / "checksums.sha256").read_text(encoding="utf-8") == "".join(
        f"{digest}  {name}\n" for name, digest in sorted(checksums["files"].items())
    )

    assert_public_safe(result)
    public_content = (output_dir / "diagnostic.json").read_text(encoding="utf-8")
    public_content += (output_dir / "REPORT.md").read_text(encoding="utf-8")
    for forbidden in ('"text":', '"normalized_text":', '"original_text":', '"document_id":', '"identity_hash":'):
        assert forbidden not in public_content
    assert DISCLAIMER in public_content


def test_model_metadata_drift_fails_closed(tmp_path):
    metadata = json.loads(DEFAULT_METADATA.read_text(encoding="utf-8"))
    metadata["threshold"] = THRESHOLD + 0.01
    changed = tmp_path / "model_metadata.json"
    changed.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="metadata checksum changed"):
        validate_reviewed_candidate(changed, DEFAULT_CANDIDATE_ARTIFACT)


def test_hold_release_semantic_drift_or_final_artifact_fails_closed(tmp_path):
    changed_packet = json.loads(DEFAULT_DECISION_PACKET.read_text(encoding="utf-8"))
    changed_packet["selected_model"] = {"model_id": MODEL_ID}
    changed = tmp_path / "decision_packet.json"
    changed.write_text(json.dumps(changed_packet), encoding="utf-8")
    with pytest.raises(ValueError, match="selected_candidate and selected_model"):
        validate_hold_release(changed, DEFAULT_FINAL_ARTIFACT)

    unexpected_final_artifact = tmp_path / "unexpected-final.joblib"
    unexpected_final_artifact.write_bytes(b"must not exist")
    with pytest.raises(ValueError, match="must remain absent"):
        validate_hold_release(DEFAULT_DECISION_PACKET, unexpected_final_artifact)


def test_public_safety_rejects_raw_or_row_level_fields():
    with pytest.raises(ValueError, match="forbidden key"):
        assert_public_safe({"normalized_text": "not public"})
    with pytest.raises(ValueError, match="forbidden key"):
        assert_public_safe({"document_id": "row-level"})
