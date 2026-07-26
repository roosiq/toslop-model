import json

import joblib
import numpy as np
import pytest

from train_infini_news_publication_shift_candidates import (
    CORE_ROLES,
    DISCLAIMER,
    assert_public_safe,
    default_lexical_config,
    default_stylometric_config,
    fit_lexical,
    fit_metadata_shortcut,
    fit_stylometric,
    lexical_scores,
    mask_content,
    metadata_scores,
    no_text_prediction,
    rows_for_split,
    stylometric_feature_names,
    stylometric_scores,
    stylometric_vector,
)


def _row(document_id: str, role: str, text: str, year: int = 2025, split: str = "train"):
    return {
        "document_id": document_id,
        "corpus_role": role,
        "normalized_text": text,
        "publication_year": year,
        "publication_month": 1,
        "publication_year_month": f"{year}-01",
        "url_hostname": "example.com",
        "sitename": "Example News",
        "topic": "technology",
        "author_hash": "a1",
        "identity_hash": f"identity-{document_id}",
        "normalized_text_sha256": f"text-{document_id}",
        "near_duplicate_cluster_id": f"cluster-{document_id}",
        "word_count": len(text.split()),
        "_split": split,
    }


def _training_rows():
    pre = [
        _row(f"pre{i}", "pre_llm_core", "city council meeting police court local report residents budget " + f"historic{i}", 2019)
        for i in range(16)
    ]
    current = [
        _row(f"cur{i}", "current_core", "scalable platform framework announced robust performance digital users benchmark " + f"current{i}", 2025)
        for i in range(16)
    ]
    return pre + current


def test_rows_for_split_uses_manifest_and_excludes_eval_only_roles():
    rows = _training_rows() + [_row("transition", "transition_2022", "transition text", 2022)]
    rows_by_id = {row["document_id"]: row for row in rows}
    manifest = {
        "assignments": [
            {"document_id": row["document_id"], "split": row.get("_split", "train"), "corpus_role": row["corpus_role"]}
            for row in rows
        ]
    }

    selected = rows_for_split(rows_by_id, manifest, "train", CORE_ROLES)

    assert {row["document_id"] for row in selected} == {row["document_id"] for row in rows if row["corpus_role"] in CORE_ROLES}
    assert "transition" not in {row["document_id"] for row in selected}


def test_infini_lexical_model_is_deterministic_and_loadable(tmp_path):
    rows = _training_rows()
    labels = [CORE_ROLES[row["corpus_role"]] for row in rows]
    config = default_lexical_config()
    config.update({"min_df": 1, "word_max_features": 500, "char_max_features": 500, "max_iter": 100})

    first = fit_lexical([row["normalized_text"] for row in rows], labels, config)
    second = fit_lexical([row["normalized_text"] for row in rows], labels, config)
    first_scores = lexical_scores(first, [row["normalized_text"] for row in rows])
    second_scores = lexical_scores(second, [row["normalized_text"] for row in rows])

    assert np.allclose(first_scores, second_scores)
    path = tmp_path / "lexical.joblib"
    joblib.dump({"disclaimer": DISCLAIMER, "model": first}, path)
    loaded = joblib.load(path)
    assert loaded["disclaimer"] == "This score does not establish AI authorship."
    assert lexical_scores(loaded["model"], ["robust scalable framework benchmark"])[0] >= 0.0


def test_stylometric_lightgbm_candidate_is_deterministic_and_loadable(tmp_path):
    rows = _training_rows()
    labels = [CORE_ROLES[row["corpus_role"]] for row in rows]
    config = default_stylometric_config()
    config.update({"n_estimators": 20, "n_jobs": 1, "min_child_samples": 2})

    first = fit_stylometric(rows, labels, config)
    second = fit_stylometric(rows, labels, config)
    assert stylometric_feature_names() == first["feature_names"]
    assert len(stylometric_vector(rows[0]["normalized_text"])) == len(stylometric_feature_names())
    assert np.allclose(stylometric_scores(first, rows), stylometric_scores(second, rows))

    path = tmp_path / "stylometric.joblib"
    joblib.dump({"disclaimer": DISCLAIMER, "model": first}, path)
    loaded = joblib.load(path)
    assert 0.0 <= stylometric_scores(loaded["model"], rows[:1])[0] <= 1.0


def test_metadata_shortcut_scores_without_text_features():
    rows = _training_rows()
    for index, row in enumerate(rows):
        row["sitename"] = "Current Wire" if row["corpus_role"] == "current_core" else "Historic Gazette"
        row["author_hash"] = f"author-{index}"
    labels = [CORE_ROLES[row["corpus_role"]] for row in rows]

    model = fit_metadata_shortcut(rows, labels, ["sitename"])
    scores = metadata_scores(model, rows)

    assert len(scores) == len(rows)
    assert scores[-1] > scores[0]
    assert "normalized_text" not in model["fields"]


def test_no_text_prediction_and_public_guard_reject_raw_text_url_and_preview():
    row = _training_rows()[0]
    row["url"] = "https://private.example/story"
    pred = no_text_prediction(row, 0.7, 1, "family", "lane", "test")

    assert_public_safe(pred)
    assert "normalized_text" not in pred
    assert "url" not in pred
    assert pred["url_hostname_hash"] is not None
    with pytest.raises(ValueError, match="forbidden text key"):
        assert_public_safe({"normalized_text": "private"})
    with pytest.raises(ValueError, match="forbidden text key"):
        assert_public_safe({"url": "https://private.example"})
    with pytest.raises(ValueError, match="forbidden text key"):
        assert_public_safe({"preview_text": "private"})


def test_mask_content_removes_explicit_shortcut_tokens():
    masked = mask_content("ChatGPT improved 42% in 2024 at https://example.com for New York University.")
    assert "ChatGPT" not in masked
    assert "2024" not in masked
    assert "42" not in masked
    assert "https://" not in masked
    assert "[AI_TERM]" in masked
    assert "[NUMBER]" in masked
    assert "[URL]" in masked
