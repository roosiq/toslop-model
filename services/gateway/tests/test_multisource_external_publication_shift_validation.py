import json

import pytest

from train_infini_news_publication_shift_candidates import assert_public_safe


def _body(prefix="word", words=170):
    return " ".join(f"{prefix}{idx}" for idx in range(words))


def _row(**overrides):
    row = {
        "maintext": _body(),
        "date_publish": "2021-08-15 12:00:00",
        "date_download": "2023-01-01",
        "date_modify": "2023-01-02",
        "url": "https://www.example.com/news/story-1?utm_source=x",
        "source_domain": "www.example.com",
        "authors": ["Reporter"],
    }
    row.update(overrides)
    return row


def test_default_manifest_freezes_two_realtime_revisions_and_date_publish_axis():
    import build_multisource_external_publication_shift_validation as ms

    manifest = ms.default_request_manifest()

    assert manifest["manifest_id"] == "multisource_external_v1_all_and_domain_matched"
    assert manifest["date_axis"] == "date_publish_only"
    assert manifest["source_rights_status"] == "HOLD_combined_cc_and_unspecified_public_no_text_only"
    assert manifest["sources"]["pre_llm_2021"]["repo_id"] == "RealTimeData/News_Seq_2021"
    assert manifest["sources"]["pre_llm_2021"]["revision"] == "b703213f35f4b604a15ffa92d3bb4090dba25ad5"
    assert manifest["sources"]["current_2023"]["repo_id"] == "RealTimeData/News_August_2023"
    assert manifest["sources"]["current_2023"]["revision"] == "eedb055bf0b5583f22854c347e51a0b5a5d76f49"
    assert manifest["minimum_words"] == 150
    assert manifest["disclaimer"] == ms.DISCLAIMER


def test_normalize_row_uses_date_publish_not_download_or_dataset_name():
    import build_multisource_external_publication_shift_validation as ms

    normalized = ms.normalize_source_row(
        _row(date_publish="2023-08-02T03:04:05Z", date_download="2021-08-01", source_domain="www.Example.COM"),
        source_key="current_2023",
        source=ms.SOURCES["current_2023"],
        row_index=7,
        retrieved_at="2026-07-13T00:00:00Z",
    )

    assert normalized["publication_date"] == "2023-08-02"
    assert normalized["publication_year_month"] == "2023-08"
    assert normalized["corpus_role"] == "current_core"
    assert normalized["label"] == 1
    assert normalized["source_domain"] == "example.com"
    assert normalized["normalized_url_hash"] == ms.sha256_text("https://example.com/news/story-1")
    assert normalized["document_id"].startswith("multisource_external_")

    with pytest.raises(ms.MultisourceExternalValidationError, match="outside source window"):
        ms.normalize_source_row(
            _row(date_publish="2021-08-10", date_download="2023-08-01"),
            source_key="current_2023",
            source=ms.SOURCES["current_2023"],
            row_index=1,
            retrieved_at="now",
        )


@pytest.mark.parametrize(
    "bad_row,match",
    [
        ({"maintext": _body(words=149)}, "fewer than 150"),
        ({"date_publish": ""}, "date_publish"),
        ({"url": ""}, "url"),
        ({"source_domain": ""}, "source_domain"),
    ],
)
def test_normalize_row_rejects_required_source_contracts(bad_row, match):
    import build_multisource_external_publication_shift_validation as ms

    with pytest.raises(ms.MultisourceExternalValidationError, match=match):
        ms.normalize_source_row(_row(**bad_row), source_key="pre_llm_2021", source=ms.SOURCES["pre_llm_2021"], row_index=1, retrieved_at="now")


def test_select_domain_matched_lane_is_exactly_balanced_per_domain():
    import build_multisource_external_publication_shift_validation as ms

    rows = []
    for domain, pre_count, current_count in [("a.com", 3, 2), ("b.com", 1, 4), ("preonly.com", 2, 0)]:
        for idx in range(pre_count):
            rows.append({"document_id": f"pre-{domain}-{idx}", "source_domain": domain, "label": 0, "publication_date": "2021-08-01", "normalized_text_sha256": f"t-pre-{domain}-{idx}"})
        for idx in range(current_count):
            rows.append({"document_id": f"cur-{domain}-{idx}", "source_domain": domain, "label": 1, "publication_date": "2023-08-01", "normalized_text_sha256": f"t-cur-{domain}-{idx}"})

    selected, proof = ms.select_domain_matched_lane(rows, seed=11)

    assert len(selected) == 6
    assert proof["overlapping_domain_count"] == 2
    assert proof["total_per_era"] == {"pre_llm_core": 3, "current_core": 3}
    assert proof["exact_per_domain_era_balance"] is True
    for domain, counts in proof["per_domain"].items():
        assert counts["selected_pre_llm_core"] == counts["selected_current_core"], domain


def test_public_artifacts_reject_text_and_report_structural_domain_chance(tmp_path):
    import build_multisource_external_publication_shift_validation as ms

    rows = [
        {"document_id": "a0", "label": 0, "current_era_similarity": 0.1, "publication_year_month": "2021-08", "corpus_role": "pre_llm_core", "source_domain_hash": "dh-a", "source_domain": "a.com", "word_count": 200, "author_hash": None},
        {"document_id": "a1", "label": 1, "current_era_similarity": 0.9, "publication_year_month": "2023-08", "corpus_role": "current_core", "source_domain_hash": "dh-a", "source_domain": "a.com", "word_count": 210, "author_hash": "h"},
        {"document_id": "b0", "label": 0, "current_era_similarity": 0.2, "publication_year_month": "2021-08", "corpus_role": "pre_llm_core", "source_domain_hash": "dh-b", "source_domain": "b.com", "word_count": 220, "author_hash": None},
        {"document_id": "b1", "label": 1, "current_era_similarity": 0.8, "publication_year_month": "2023-08", "corpus_role": "current_core", "source_domain_hash": "dh-b", "source_domain": "b.com", "word_count": 230, "author_hash": "h"},
    ]
    report = ms.build_external_report(
        rows,
        masked_rows=rows,
        lane_name="domain_matched_balanced",
        request_manifest=ms.default_request_manifest(),
        model_metadata={"model_id": ms.FROZEN_MODEL_ID},
        corpus_manifest={"lanes": {"domain_matched_balanced": {"accepted_count": 4}}},
        domain_balance_proof={"exact_per_domain_era_balance": True, "overlapping_domain_count": 2},
    )

    assert report["gates"]["domain_only_shortcut"]["status"] == "STRUCTURAL_CHANCE"
    assert report["gates"]["domain_only_shortcut"]["roc_auc"] == 0.5
    assert report["decision"] == "PASS"
    assert ms.DISCLAIMER in json.dumps(report)
    assert_public_safe(report)

    with pytest.raises(ms.MultisourceExternalValidationError):
        ms.write_public_json(tmp_path / "bad_multisource_public.json", {"records": [{"maintext": "do not publish"}]})
