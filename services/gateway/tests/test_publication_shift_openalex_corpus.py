import json
import os
import stat

import pytest

from build_publication_shift_openalex_corpus import (
    OpenAlexQuotaError,
    OpenAlexSchemaError,
    append_private_jsonl,
    assign_corpus_role,
    build_openalex_url,
    build_public_safe_manifest,
    cap_forward_rows,
    dedupe_records,
    deterministic_near_duplicate_cluster,
    load_progress,
    normalize_work,
    reconstruct_abstract,
    write_private_jsonl,
    write_progress,
)


def _abstract(words=170):
    tokens = [f"word{idx}" for idx in range(words)]
    inverted = {}
    for idx, token in enumerate(tokens):
        inverted.setdefault(token, []).append(idx)
    return inverted


def _abstract_from(prefix, words=170):
    tokens = [f"{prefix}{idx}" for idx in range(words)]
    inverted = {}
    for idx, token in enumerate(tokens):
        inverted.setdefault(token, []).append(idx)
    return inverted


def _work(work_id="https://openalex.org/W1", year=2023, month=5, abstract=None, doi="https://doi.org/10.1/example"):
    return {
        "id": work_id,
        "doi": doi,
        "publication_date": f"{year}-{month:02d}-15",
        "publication_year": year,
        "language": "en",
        "type": "article",
        "abstract_inverted_index": abstract if abstract is not None else _abstract(),
        "primary_location": {
            "source": {
                "id": "https://openalex.org/S1",
                "host_organization": "https://openalex.org/P1",
            }
        },
        "primary_topic": {
            "id": "https://openalex.org/T1",
            "domain": {"id": "https://openalex.org/D1"},
            "field": {"id": "https://openalex.org/F1"},
            "subfield": {"id": "https://openalex.org/SF1"},
        },
        "authorships": [
            {"author": {"id": "https://openalex.org/A1"}},
            {"author": {"id": "https://openalex.org/A2"}},
        ],
    }


def test_reconstruct_abstract_orders_by_positions_and_rejects_gaps():
    assert reconstruct_abstract({"beta": [1], "alpha": [0], "gamma": [2]}) == "alpha beta gamma"

    with pytest.raises(OpenAlexSchemaError):
        reconstruct_abstract({"alpha": [0], "gamma": [2]})


def test_normalize_work_rejects_invalid_dates_language_type_and_short_abstracts():
    manifest_id = "manifest-test"
    assert normalize_work(_work(), manifest_id=manifest_id, retrieved_at="2026-07-12T00:00:00Z")["publication_year"] == 2023

    with pytest.raises(OpenAlexSchemaError, match="publication_date"):
        normalize_work({**_work(), "publication_date": "2023"}, manifest_id=manifest_id, retrieved_at="now")
    with pytest.raises(OpenAlexSchemaError, match="language"):
        normalize_work({**_work(), "language": "fr"}, manifest_id=manifest_id, retrieved_at="now")
    with pytest.raises(OpenAlexSchemaError, match="work type"):
        normalize_work({**_work(), "type": "book"}, manifest_id=manifest_id, retrieved_at="now")
    with pytest.raises(OpenAlexSchemaError, match="150 words"):
        normalize_work(_work(abstract=_abstract(149)), manifest_id=manifest_id, retrieved_at="now")


def test_partial_2026_role_assignment_is_forward_only_and_month_limited():
    assert assign_corpus_role(2026, 4, max_forward_month=7) == "forward_2026"
    assert assign_corpus_role(2026, 8, max_forward_month=7) is None
    assert assign_corpus_role(2022, 3) == "transition_2022"
    assert assign_corpus_role(2016, 3) == "historical_placebo"
    assert assign_corpus_role(2024, 3) == "current_core"


def test_forward_collection_uses_calendar_month_filters_and_deterministic_caps():
    url = build_openalex_url(2026, "*", 200, "test@example.com", month=2)
    assert "from_publication_date:2026-02-01" in url
    assert "to_publication_date:2026-02-28" in url

    rows = [
        {"publication_year": 2025, "publication_month": 1, "publication_date": "2025-01-01", "document_id": "old", "work_id": "W0"},
        {"publication_year": 2026, "publication_month": 1, "publication_date": "2026-01-02", "document_id": "jan2", "work_id": "W2"},
        {"publication_year": 2026, "publication_month": 1, "publication_date": "2026-01-01", "document_id": "jan1", "work_id": "W1"},
        {"publication_year": 2026, "publication_month": 2, "publication_date": "2026-02-01", "document_id": "feb1", "work_id": "W3"},
    ]
    retained, removed = cap_forward_rows(rows, {"1": 1, "2": 1})

    assert removed == 1
    assert {row["document_id"] for row in retained} == {"old", "jan1", "feb1"}


def test_schema_and_quota_errors_are_explicit():
    with pytest.raises(OpenAlexQuotaError):
        OpenAlexQuotaError.from_status(429, "too many")
    with pytest.raises(OpenAlexSchemaError):
        normalize_work({**_work(), "id": None}, manifest_id="m", retrieved_at="now")


def test_private_jsonl_uses_restrictive_permissions(tmp_path):
    path = tmp_path / "rows.jsonl"
    write_private_jsonl(path, [{"secret": "text"}])

    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
    assert stat.S_IMODE(os.stat(tmp_path).st_mode) & 0o077 == 0


def test_private_jsonl_append_preserves_existing_rows(tmp_path):
    path = tmp_path / "rows.jsonl"
    write_private_jsonl(path, [{"page": 1}])
    append_private_jsonl(path, [{"page": 2}])

    assert [json.loads(line) for line in path.read_text().splitlines()] == [{"page": 1}, {"page": 2}]
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_progress_preserves_cursors_request_count_and_rejections(tmp_path):
    path = tmp_path / "progress.json"
    write_progress(
        path,
        {
            "cursors": {"2019": "cursor-2019"},
            "stats": {
                "request_count": 7,
                "rejected_counts": {"too_short": 3},
                "duplicate_counts": {"doi_duplicates": 1},
            },
        },
    )

    progress = load_progress(path)

    assert progress["cursors"]["2019"] == "cursor-2019"
    assert progress["stats"]["request_count"] == 7
    assert progress["stats"]["rejected_counts"] == {"too_short": 3}
    assert progress["stats"]["duplicate_counts"] == {"doi_duplicates": 1}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_progress_reads_legacy_cursor_only_shape(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text(json.dumps({"2020": "legacy-cursor"}), encoding="utf-8")

    progress = load_progress(path)

    assert progress["cursors"] == {"2020": "legacy-cursor"}
    assert progress["stats"] == {"request_count": 0, "rejected_counts": {}, "duplicate_counts": {}}


def test_dedupe_uses_work_doi_hash_and_near_duplicate_cluster():
    first = normalize_work(_work(work_id="https://openalex.org/W1", doi="https://doi.org/10.1/a"), manifest_id="m", retrieved_at="now")
    same_work = {**first, "document_id": "other", "doi": "https://doi.org/10.1/b"}
    same_doi = {**first, "document_id": "third", "work_id": "https://openalex.org/W3"}
    unique = normalize_work(_work(work_id="https://openalex.org/W4", doi="https://doi.org/10.1/d", abstract=_abstract_from("unique", 171)), manifest_id="m", retrieved_at="now")

    records, counts = dedupe_records([first, same_work, same_doi, unique])

    assert len(records) == 2
    assert counts["work_id_duplicates"] == 1
    assert counts["doi_duplicates"] == 1
    assert all(record["near_duplicate_cluster_id"] for record in records)
    assert deterministic_near_duplicate_cluster(first["normalized_abstract"]) == first["near_duplicate_cluster_id"]


def test_public_manifest_excludes_raw_text_and_preview_fields(tmp_path):
    row = normalize_work(_work(), manifest_id="m", retrieved_at="now")
    manifest = build_public_safe_manifest([row], request_count=3, rejected_counts={"too_short": 2}, duplicate_counts={"exact": 1})
    encoded = json.dumps(manifest, sort_keys=True)

    assert "abstract" not in encoded.lower()
    assert "preview" not in encoded.lower()
    assert row["normalized_text_sha256"] in encoded
    assert manifest["request_count"] == 3
    assert manifest["accepted_count"] == 1
