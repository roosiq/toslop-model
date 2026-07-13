import datetime as dt
import json

import pytest

from train_infini_news_publication_shift_candidates import assert_public_safe


def _body(prefix="word", words=170):
    return " ".join(f"{prefix}{idx}" for idx in range(words))


def _row(**overrides):
    row = {
        "content": _body(),
        "published_date": "2024-01-15",
        "link": "https://www.bbc.co.uk/news/world-test-1?utm_source=x",
        "section": "World",
        "authors": "BBC News",
    }
    row.update(overrides)
    return row


def test_bbc_default_manifest_freezes_revision_and_24k_core_targets():
    import build_bbc_external_publication_shift_validation as bbc

    manifest = bbc.default_request_manifest(include_2022=True)

    assert manifest["source_repo_id"] == "RealTimeData/bbc_news_alltime"
    assert manifest["source_revision"] == "8dd1ecdc92ac43f9c04a3da3e945537dbb08179b"
    assert manifest["source_schema_fields"] == [
        "title",
        "published_date",
        "authors",
        "item",
        "description",
        "section",
        "content",
        "link",
        "top_image",
    ]
    assert manifest["source_rights_status"] == "HOLD_no_explicit_license_public_no_text_only"
    assert manifest["targets_by_month"]["2018-01"] == 250
    assert manifest["targets_by_month"]["2021-12"] == 250
    assert manifest["targets_by_month"]["2023-01"] == 400
    assert manifest["targets_by_month"]["2025-06"] == 400
    assert "2025-07" not in manifest["targets_by_month"]
    assert manifest["target_core_rows"] == 24_000
    assert manifest["targets_by_role"]["transition_2022"] == 3000


def test_bbc_normalize_row_uses_published_date_and_rejects_partition_mismatch():
    import build_bbc_external_publication_shift_validation as bbc

    normalized = bbc.normalize_bbc_row(
        _row(published_date="2023-01-03", link="http://www.bbc.co.uk/news/uk-1?utm_campaign=y"),
        config_month="2023-01",
        row_index=7,
        retrieved_at="2026-07-13T00:00:00Z",
    )

    assert normalized["publication_date"] == "2023-01-03"
    assert normalized["publication_year_month"] == "2023-01"
    assert normalized["corpus_role"] == "current_core"
    assert normalized["label"] == 1
    assert normalized["normalized_url_hash"] == bbc.sha256_text("http://bbc.co.uk/news/uk-1")
    assert normalized["source_domain"] == "bbc.co.uk"
    assert normalized["document_id"].startswith("bbc_external_")

    with pytest.raises(bbc.BbcExternalValidationError, match="partition mismatch"):
        bbc.normalize_bbc_row(_row(published_date="2023-02-01"), config_month="2023-01", row_index=1, retrieved_at="now")


@pytest.mark.parametrize(
    "bad_row,match",
    [
        ({"content": _body(words=149)}, "fewer than 150"),
        ({"published_date": ""}, "published_date"),
        ({"link": ""}, "link"),
    ],
)
def test_bbc_normalize_row_rejects_required_source_contracts(bad_row, match):
    import build_bbc_external_publication_shift_validation as bbc

    with pytest.raises(bbc.BbcExternalValidationError, match=match):
        bbc.normalize_bbc_row(_row(**bad_row), config_month="2024-01", row_index=1, retrieved_at="now")


def test_bbc_public_writer_rejects_text_fields_and_public_manifest_is_safe(tmp_path):
    import build_bbc_external_publication_shift_validation as bbc

    row = bbc.normalize_bbc_row(_row(), config_month="2024-01", row_index=1, retrieved_at="now")
    manifest = bbc.build_public_corpus_manifest(
        [row],
        request_manifest=bbc.default_request_manifest(include_2022=False),
        rejected_counts={},
        duplicate_counts={},
        source_files=[],
        cross_dedupe_path="/private/infini.jsonl",
    )

    encoded = json.dumps(manifest, sort_keys=True).lower()
    assert "\"content\":" not in encoded
    assert "normalized_text\"" not in encoded
    assert "this score does not establish ai authorship" in encoded
    assert_public_safe(manifest)

    with pytest.raises(bbc.BbcExternalValidationError):
        bbc.write_public_json(tmp_path / "bad.json", {"records": [{"content": "do not publish"}]})


def test_bbc_evaluator_verifies_frozen_identity_and_reports_single_source_gates(tmp_path):
    import build_bbc_external_publication_shift_validation as bbc

    artifact = {
        "model_id": bbc.FROZEN_MODEL_ID,
        "threshold": bbc.FROZEN_THRESHOLD,
        "config": bbc.FROZEN_CONFIG,
        "model": object(),
    }
    metadata = {"model_id": bbc.FROZEN_MODEL_ID, "artifact_sha256": bbc.FROZEN_ARTIFACT_SHA256, "threshold": bbc.FROZEN_THRESHOLD, "config": bbc.FROZEN_CONFIG}

    assert bbc.verify_frozen_model_identity(artifact, metadata, artifact_sha256=bbc.FROZEN_ARTIFACT_SHA256) is None
    with pytest.raises(bbc.BbcExternalValidationError, match="threshold"):
        bbc.verify_frozen_model_identity({**artifact, "threshold": 0.5}, metadata, artifact_sha256=bbc.FROZEN_ARTIFACT_SHA256)

    rows = [
        {"document_id": "a", "label": 0, "current_era_similarity": 0.1, "publication_year_month": "2018-01", "corpus_role": "pre_llm_core", "source_domain_hash": "one", "section": "World", "word_count": 200, "author_hash": None},
        {"document_id": "b", "label": 1, "current_era_similarity": 0.9, "publication_year_month": "2023-01", "corpus_role": "current_core", "source_domain_hash": "one", "section": "World", "word_count": 210, "author_hash": "h"},
    ]
    report = bbc.build_external_report(rows, masked_rows=rows, request_manifest=bbc.default_request_manifest(include_2022=False), model_metadata=metadata, corpus_manifest={"accepted_count": 2})

    assert report["metrics"]["overall"]["roc_auc"] == 1.0
    assert report["gates"]["source_only_shortcut"]["status"] == "N/A"
    assert report["gates"]["source_diversity"]["status"] == "N/A"
    assert report["decision"] != "PASS"
    assert_public_safe(report)


def test_january_2024_diagnostic_recomputes_expected_fixture_accuracy(tmp_path):
    import build_bbc_external_publication_shift_validation as bbc

    path = tmp_path / "predictions.jsonl"
    rows = []
    for idx in range(951):
        label = idx % 2
        correct = idx < 580
        score = 0.9 if (label == 1) == correct else 0.1
        rows.append({"document_id": f"jan-{idx}", "publication_year": 2024, "publication_month": 1, "label": label, "current_era_similarity": score, "topic": "news", "word_count": 200, "author_hash": None, "url_hostname_hash": "s"})
    rows.extend([
        {"document_id": "dec", "publication_year": 2023, "publication_month": 12, "label": 0, "current_era_similarity": 0.1, "topic": "news", "word_count": 200, "author_hash": "a", "url_hostname_hash": "s"},
        {"document_id": "feb", "publication_year": 2024, "publication_month": 2, "label": 1, "current_era_similarity": 0.9, "topic": "news", "word_count": 200, "author_hash": "a", "url_hostname_hash": "s"},
    ])
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    diagnostic = bbc.january_2024_diagnostic(path, threshold=0.5)

    assert diagnostic["windows"]["january_2024"]["count"] == 951
    assert diagnostic["windows"]["january_2024"]["accuracy"] == pytest.approx(580 / 951)
    assert diagnostic["interpretation"] == "diagnostic_only_no_model_selection_or_tuning"
    assert_public_safe(diagnostic)
