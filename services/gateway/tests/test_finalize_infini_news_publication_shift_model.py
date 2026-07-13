import json
from pathlib import Path

import joblib
import pytest

from finalize_infini_news_publication_shift_model import (
    DECLARED_PLACEBO_LANES,
    DISCLAIMER,
    PRIMARY_LANE,
    assert_selected_artifact_identity,
    candidate_gate_matrix,
    declared_historical_placebos,
    grouped_bootstrap_auc,
    matched_historical_placebos,
    select_final_decision,
    sha256_file,
)
from train_infini_news_publication_shift_candidates import assert_public_safe, stable_json_sha256


def _passing_candidate(*, valid_alternates: bool = False) -> dict:
    alternate_status = {"selection_status": "valid_for_selection", "primary_training_overlap_count": 0} if valid_alternates else {}
    return {
        "candidate_name": "lexical_tfidf_logistic",
        "model_id": "infini-news-lexical_tfidf_logistic-v1-123456789abc",
        "model_family": "infini_news_word_char_tfidf_logistic",
        "score_name": "current_era_similarity",
        "decision": "PASS-HOLD",
        "training_protocol": PRIMARY_LANE,
        "lanes": {
            PRIMARY_LANE: {"roc_auc": 0.94, "balanced_accuracy": 0.87, "ece": 0.05, "threshold": 0.5},
            "masked_primary_test": {"roc_auc": 0.85, "threshold": 0.5},
            "source_sitename_heldout": {"roc_auc": 0.97, **alternate_status},
            "topic_heldout": {"roc_auc": 0.96, **alternate_status},
            "author_heldout": {"roc_auc": 0.97, **alternate_status},
            "random_diagnostic": {"roc_auc": 0.98, **alternate_status},
        },
        "shortcut_diagnostics": {
            "source_only_primary_test": {"roc_auc": 0.49},
            "metadata_only_primary_test": {"roc_auc": 1.0},
        },
    }


def _passing_global_gates() -> dict:
    return {name: {"passed": True, "status": "PASS"} for name in (
        "valid_leakage_safe_alternate_lanes",
        "declared_historical_placebos_supported",
        "placebo_lift_minimum_and_ci",
        "full_encoder_or_measured_hardware_hold",
        "no_severe_subgroup_collapse",
        "external_validation_gates",
        "rights_clearance_for_promotion",
        "selected_artifact_identity",
    )}


def test_grouped_bootstrap_auc_is_public_safe_and_returns_ci():
    result = grouped_bootstrap_auc(
        labels=[0, 0, 1, 1, 0, 1],
        scores=[0.1, 0.2, 0.8, 0.9, 0.35, 0.7],
        groups=["a", "a", "b", "b", "c", "c"],
        samples=20,
        seed=7,
    )

    assert result["samples_requested"] == 20
    assert result["samples_valid"] > 0
    assert result["lower"] <= result["median"] <= result["upper"]
    assert_public_safe(result)


def test_declared_placebo_does_not_substitute_primary_core_rows():
    declared = {
        "placebo_2016_2017_vs_2020_2021": [
            {"document_id": "a", "publication_year": 2016, "label": 0, "current_era_similarity": 0.1, "url_hostname_hash": "s1"},
            {"document_id": "b", "publication_year": 2017, "label": 0, "current_era_similarity": 0.2, "url_hostname_hash": "s2"},
        ],
        "placebo_2016_2018_vs_2019_2021": [],
    }

    result = declared_historical_placebos(declared, threshold=0.5, samples=10)

    assert set(result) == set(DECLARED_PLACEBO_LANES)
    assert result["placebo_2016_2017_vs_2020_2021"]["support"]["status"] == "unsupported"
    assert result["placebo_2016_2017_vs_2020_2021"]["test"]["roc_auc"] is None
    assert result["placebo_2016_2017_vs_2020_2021"]["observed_publication_years"] == [2016, 2017]
    with pytest.raises(ValueError, match="substitution is forbidden"):
        matched_historical_placebos(declared["placebo_2016_2017_vs_2020_2021"], threshold=0.5)
    assert_public_safe(result)


def test_alternate_split_metrics_are_invalid_for_selection_and_force_hold():
    lexical = _passing_candidate(valid_alternates=False)
    matrix = candidate_gate_matrix({"lexical_tfidf_logistic": lexical})
    decision = select_final_decision({"lexical_tfidf_logistic": lexical}, matrix, _passing_global_gates())

    gate = matrix["lexical_tfidf_logistic"]
    assert gate["eligible_for_candidate_comparison"] is True
    assert gate["eligible_for_final"] is False
    assert gate["required_alternate_lanes_leakage_safe"] is False
    assert all(item["selection_status"] == "invalid_for_selection" for item in gate["alternate_lane_evidence"].values())
    assert decision["decision"] == "HOLD"
    assert decision["selected_candidate"] is None
    assert decision["reviewed_candidate"] == "lexical_tfidf_logistic"
    assert decision["disclaimer"] == DISCLAIMER
    assert_public_safe({"matrix": matrix, "decision": decision})


def test_selection_requires_every_global_gate_even_with_valid_alternates():
    lexical = _passing_candidate(valid_alternates=True)
    matrix = candidate_gate_matrix({"lexical_tfidf_logistic": lexical})
    gates = _passing_global_gates()
    gates["external_validation_gates"] = {"passed": False, "status": "FAIL"}

    hold = select_final_decision({"lexical_tfidf_logistic": lexical}, matrix, gates)
    passed = select_final_decision({"lexical_tfidf_logistic": lexical}, matrix, _passing_global_gates())

    assert matrix["lexical_tfidf_logistic"]["eligible_for_final"] is True
    assert hold["decision"] == "HOLD"
    assert hold["selected_candidate"] is None
    assert hold["failed_required_gates"] == ["external_validation_gates"]
    assert passed["decision"] == "PASS"
    assert passed["selected_candidate"] == "lexical_tfidf_logistic"


def _write_artifact_fixture(tmp_path: Path) -> tuple[dict, dict, dict]:
    split_summary = {"schema": "publication_shift.infini_news_split_summary.v1", "seed": "frozen"}
    training_identity = "123456789abc" + "0" * 52
    model_id = "infini-news-lexical_tfidf_logistic-v1-123456789abc"
    artifact = {
        "schema": "publication_shift.infini_news_model_artifact.v1",
        "model_id": model_id,
        "model_family": "infini_news_word_char_tfidf_logistic",
        "score_name": "current_era_similarity",
        "candidate_name": "lexical_tfidf_logistic",
        "threshold": 0.5,
        "training_identity_sha256": training_identity,
        "training_protocol": PRIMARY_LANE,
        "model": {"fixture": True},
    }
    artifact_path = tmp_path / "candidate.joblib"
    joblib.dump(artifact, artifact_path)
    metrics = _passing_candidate(valid_alternates=True)
    metrics["model_id"] = model_id
    metadata = {
        "artifact_path": str(artifact_path),
        "artifact_sha256": sha256_file(artifact_path),
        "artifact_size_bytes": artifact_path.stat().st_size,
        "candidate_name": "lexical_tfidf_logistic",
        "model_id": model_id,
        "model_family": "infini_news_word_char_tfidf_logistic",
        "score_name": "current_era_similarity",
        "threshold": 0.5,
        "training_identity_sha256": training_identity,
        "split_summary_sha256": stable_json_sha256(split_summary),
    }
    return metrics, metadata, split_summary


def test_selected_artifact_identity_asserts_all_frozen_identities(tmp_path):
    metrics, metadata, split_summary = _write_artifact_fixture(tmp_path)

    evidence = assert_selected_artifact_identity("lexical_tfidf_logistic", metrics, metadata, split_summary)

    assert evidence["status"] == "PASS"
    assert evidence["all_assertions_passed"] is True
    assert all(evidence["assertions"].values())
    assert evidence["artifact_sha256"] == metadata["artifact_sha256"]
    assert evidence["model_id"] == metadata["model_id"]
    assert evidence["threshold"] == 0.5
    assert evidence["training_identity_sha256"] == metadata["training_identity_sha256"]


@pytest.mark.parametrize("field,bad_value", [("model_id", "wrong"), ("threshold", 0.4), ("training_identity_sha256", "0" * 64), ("artifact_sha256", "0" * 64)])
def test_selected_artifact_identity_rejects_partial_or_mismatched_identity(tmp_path, field, bad_value):
    metrics, metadata, split_summary = _write_artifact_fixture(tmp_path)
    metadata[field] = bad_value

    with pytest.raises(AssertionError, match="identity validation failed"):
        assert_selected_artifact_identity("lexical_tfidf_logistic", metrics, metadata, split_summary)


def test_committed_final_packet_is_hold_with_no_frozen_selection():
    output = Path("services/evals/publication_shift_model/infini_news_final_v1")
    packet = json.loads((output / "decision_packet.json").read_text(encoding="utf-8"))
    checksums = json.loads((output / "checksums.json").read_text(encoding="utf-8"))

    assert packet["decision"]["decision"] == "HOLD"
    assert packet["decision"]["selected_candidate"] is None
    assert packet["selected_model"] is None
    assert packet["artifact_freeze"]["status"] == "not_performed"
    assert packet["mandatory_disclaimer"] == DISCLAIMER
    assert packet["primary_result"]["selection_status"] == "valid_frozen_primary_evidence"
    assert packet["primary_result"]["main_minus_strongest_placebo"]["point_estimate"] is None
    assert all(
        packet["frozen_lane_results"][lane]["selection_status"] == "invalid_for_selection"
        for lane in ("source_sitename_heldout", "topic_heldout", "author_heldout", "random_diagnostic")
    )
    assert not (output / "infini_news_word_char_tfidf_logistic.joblib").exists()
    assert all(Path(path).is_file() and sha256_file(Path(path)) == digest for path, digest in checksums["files"].items())
