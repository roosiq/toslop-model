import joblib
import numpy as np
import pytest

from train_publication_shift_baseline import (
    CORE_ROLES,
    DISCLAIMER,
    SCORE_NAME,
    assert_public_safe,
    binary_metrics,
    default_config,
    fit_model,
    mask_content,
    predict_scores,
    select_rows,
)


def _tiny_training():
    pre = [
        "traditional experimental study reports careful observations and established methods " + f"historic{i}"
        for i in range(12)
    ]
    current = [
        "comprehensive scalable framework demonstrates robust performance across diverse benchmarks " + f"current{i}"
        for i in range(12)
    ]
    return pre + current, [0] * len(pre) + [1] * len(current)


def test_text_only_model_is_deterministic_and_loadable(tmp_path):
    texts, labels = _tiny_training()
    config = default_config()
    config.update({"min_df": 1, "word_max_features": 500, "char_max_features": 500})

    first_features, first_classifier = fit_model(texts, labels, config)
    second_features, second_classifier = fit_model(texts, labels, config)
    first_scores = predict_scores(first_features, first_classifier, texts)
    second_scores = predict_scores(second_features, second_classifier, texts)

    assert np.allclose(first_scores, second_scores)
    artifact = {
        "score_name": SCORE_NAME,
        "disclaimer": DISCLAIMER,
        "features": first_features,
        "classifier": first_classifier,
        "threshold": 0.5,
    }
    path = tmp_path / "model.joblib"
    joblib.dump(artifact, path)
    loaded = joblib.load(path)
    probe = loaded["classifier"].predict_proba(loaded["features"].transform(["robust scalable benchmark framework"]))[0, 1]
    assert 0.0 <= probe <= 1.0
    assert loaded["score_name"] == "current_era_similarity"
    assert loaded["disclaimer"] == "This score does not establish AI authorship."


def test_training_selection_excludes_transition_and_forward_rows():
    rows = [
        {"document_id": "pre", "corpus_role": "pre_llm_core"},
        {"document_id": "current", "corpus_role": "current_core"},
        {"document_id": "transition", "corpus_role": "transition_2022"},
        {"document_id": "forward", "corpus_role": "forward_2026"},
    ]
    assignments = {row["document_id"]: {"split": "train"} for row in rows}

    selected = select_rows(rows, assignments, "train", CORE_ROLES)

    assert {row["document_id"] for row in selected} == {"pre", "current"}


def test_public_artifact_guard_rejects_text_and_preview_fields():
    assert_public_safe({"document_id": "d1", "current_era_similarity": 0.7})
    with pytest.raises(ValueError, match="forbidden text key"):
        assert_public_safe({"normalized_abstract": "private"})
    with pytest.raises(ValueError, match="forbidden text key"):
        assert_public_safe({"preview_text": "private"})


def test_masking_removes_dates_numbers_urls_citations_and_ai_terms():
    masked = mask_content("ChatGPT improved 42% in 2024 (Smith et al., 2023) at https://example.com for New York University.")
    assert "ChatGPT" not in masked
    assert "2024" not in masked
    assert "42" not in masked
    assert "https://" not in masked
    assert "[AI_TERM]" in masked
    assert "[NUMBER]" in masked
    assert "[URL]" in masked


def test_binary_metrics_reports_calibration_and_discrimination():
    metrics = binary_metrics([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], 0.5)
    assert metrics["roc_auc"] == 1.0
    assert metrics["balanced_accuracy"] == 1.0
    assert metrics["ece"] is not None
    assert metrics["brier"] is not None
