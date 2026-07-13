import json

from finalize_infini_news_publication_shift_model import (
    DISCLAIMER,
    candidate_gate_matrix,
    grouped_bootstrap_auc,
    matched_historical_placebos,
    select_final_decision,
)
from train_infini_news_publication_shift_candidates import assert_public_safe


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


def test_matched_historical_placebos_use_prediction_years_without_text():
    predictions = [
        {"document_id": "a", "publication_year": 2018, "current_era_similarity": 0.1, "url_hostname_hash": "s1"},
        {"document_id": "b", "publication_year": 2019, "current_era_similarity": 0.2, "url_hostname_hash": "s1"},
        {"document_id": "c", "publication_year": 2020, "current_era_similarity": 0.7, "url_hostname_hash": "s2"},
        {"document_id": "d", "publication_year": 2021, "current_era_similarity": 0.8, "url_hostname_hash": "s2"},
    ]

    result = matched_historical_placebos(predictions, threshold=0.5, samples=10)

    assert result["pre_llm_2018_2019_vs_2020_2021"]["test"]["roc_auc"] == 1.0
    assert result["pre_llm_2018_2019_vs_2020_2021"]["test"]["positive_count"] == 2
    assert result["historical_placebo_2016_2017_vs_later_pre_llm"]["support"]["status"] == "unsupported"
    assert_public_safe(result)


def test_candidate_gate_matrix_and_selection_retains_strongest_passing_component():
    lexical = {
        "candidate_name": "lexical_tfidf_logistic",
        "decision": "PASS-HOLD",
        "lanes": {
            "publisher_domain_heldout_primary": {"roc_auc": 0.94, "balanced_accuracy": 0.87, "ece": 0.05},
            "masked_primary_test": {"roc_auc": 0.85},
            "source_sitename_heldout": {"roc_auc": 0.97},
            "topic_heldout": {"roc_auc": 0.96},
            "author_heldout": {"roc_auc": 0.97},
        },
        "shortcut_diagnostics": {"source_only_primary_test": {"roc_auc": 0.49}, "metadata_only_primary_test": {"roc_auc": 1.0}},
    }
    stylometric = {
        "candidate_name": "stylometric_lightgbm",
        "decision": "PASS-HOLD",
        "lanes": {
            "publisher_domain_heldout_primary": {"roc_auc": 0.69, "balanced_accuracy": 0.63, "ece": 0.06},
            "masked_primary_test": {"roc_auc": 0.64},
            "source_sitename_heldout": {"roc_auc": 0.77},
            "topic_heldout": {"roc_auc": 0.69},
            "author_heldout": {"roc_auc": 0.73},
        },
        "shortcut_diagnostics": {"source_only_primary_test": {"roc_auc": 0.49}, "metadata_only_primary_test": {"roc_auc": 1.0}},
    }
    encoder = {"candidate_name": "deberta_multitask_encoder", "decision": "SMOKE-HOLD", "lanes": {}}

    matrix = candidate_gate_matrix({"lexical_tfidf_logistic": lexical, "stylometric_lightgbm": stylometric, "deberta_multitask_encoder": encoder})
    decision = select_final_decision({"lexical_tfidf_logistic": lexical, "stylometric_lightgbm": stylometric, "deberta_multitask_encoder": encoder}, matrix)

    assert matrix["lexical_tfidf_logistic"]["eligible_for_final"] is True
    assert matrix["stylometric_lightgbm"]["eligible_for_final"] is False
    assert matrix["deberta_multitask_encoder"]["eligible_for_final"] is False
    assert decision["decision"] == "PASS"
    assert decision["selected_candidate"] == "lexical_tfidf_logistic"
    assert decision["ensemble_attempted"] is False
    assert decision["disclaimer"] == DISCLAIMER
    assert_public_safe({"matrix": matrix, "decision": decision})
