import datetime as dt
import json
import os
import stat

import pytest

import build_publication_shift_infini_news_corpus as collector
from build_publication_shift_infini_news_corpus import (
    CANDIDATE_COLLISION_QUERY,
    FROZEN_REVISION,
    InfiniNewsSchemaError,
    add_candidate_record,
    assign_corpus_role,
    build_public_safe_manifest,
    connect_private_candidate_db,
    default_manifest,
    dedupe_records,
    duplicate_counts_from_db,
    month_quota_satisfied_in_db,
    deterministic_near_duplicate_cluster,
    normalize_row,
    select_month_rows_from_db,
    select_month_rows,
    write_private_jsonl,
    write_public_json,
    write_public_manifest_streamed,
)

def _text(prefix="word", words=170):
    return " ".join(f"{prefix}{idx}" for idx in range(words))


def _row(**overrides):
    row = {
        "url": "https://Example.com/news/story?utm_source=x",
        "url_hostname": "example.com",
        "warc_filename": "CC-NEWS-20250102120000-00001.warc.gz",
        "warc_record_id": "<urn:uuid:11111111-1111-4111-8111-111111111111>",
        "warc_target_uri": "https://example.com/news/story?utm_source=x",
        "warc_date": dt.datetime(2025, 1, 2, 12, 0, tzinfo=dt.timezone.utc),
        "warc_payload_digest": "sha1:PAYLOAD",
        "http_status": 200,
        "publish_date": "2024-12-31",
        "author": "Reporter Name",
        "sitename": "Example News",
        "description": "not emitted publicly",
        "text": _text(),
        "text_xxhash64": 12345,
        "language": "eng_Latn",
        "language_iso639_3": "eng",
        "language_script": "Latn",
        "language_score": 0.99,
        "language_short": None,
        "language_short_score": None,
        "lang": "eng",
        "lang_score": 0.98,
        "month": "01",
        "year": 2025,
        "iptc_topic": "politics",
    }
    row.update(overrides)
    return row


def test_manifest_freezes_revision_and_exact_264k_month_targets():
    manifest = default_manifest()

    assert manifest["source_revision"] == FROZEN_REVISION
    assert manifest["target_total_rows"] == 264_000
    assert sum(manifest["targets_by_month"].values()) == 264_000
    assert manifest["targets_by_month"]["2016-08"] == 800
    assert manifest["targets_by_month"]["2016-12"] == 800
    assert manifest["targets_by_month"]["2018-01"] == 3000
    assert manifest["targets_by_month"]["2022-12"] in {166, 167}
    assert manifest["targets_by_month"]["2026-04"] == 500
    assert "2026-05" not in manifest["targets_by_month"]


def test_normalize_row_uses_publish_date_not_warc_partition_for_assignment():
    normalized = normalize_row(
        _row(publish_date="2024-12-31", warc_date=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc), year=2025, month="01"),
        shard_path="data/year=2025/month=01/part-test.parquet",
        shard_sha256="abc123",
        row_index=7,
        retrieved_at="2026-07-12T00:00:00Z",
    )

    assert normalized["publication_date"] == "2024-12-31"
    assert normalized["warc_date"] == "2025-01-02T00:00:00Z"
    assert normalized["publication_year"] == 2024
    assert normalized["publication_month"] == 12
    assert normalized["warc_partition_year"] == 2025
    assert normalized["warc_partition_month"] == 1
    assert normalized["corpus_role"] == "current_core"
    assert normalized["date_lag_days"] == 2
    assert normalized["document_id"].startswith("infini_news_")


def test_normalize_row_rejects_conflicting_language_short_text_and_bad_identity():
    kwargs = {"shard_path": "data/year=2025/month=01/part.parquet", "shard_sha256": "sha", "row_index": 1, "retrieved_at": "now"}
    with pytest.raises(InfiniNewsSchemaError, match="language"):
        normalize_row(_row(language_iso639_3="eng", lang="fra"), **kwargs)
    with pytest.raises(InfiniNewsSchemaError, match="150 words"):
        normalize_row(_row(text=_text(words=149)), **kwargs)
    with pytest.raises(InfiniNewsSchemaError, match="source identity"):
        normalize_row(_row(warc_record_id=""), **kwargs)


def test_dedupe_uses_warc_payload_url_text_hash_and_near_duplicate_cluster():
    kwargs = {"shard_path": "data/year=2025/month=01/part.parquet", "shard_sha256": "sha", "retrieved_at": "now"}
    first = normalize_row(_row(text=_text("alpha")), row_index=1, **kwargs)
    same_warc = {**first, "document_id": "different-doc", "url_hash": "u2", "normalized_text_sha256": "h2", "near_duplicate_cluster_id": "n2"}
    same_payload = {**first, "document_id": "payload-doc", "warc_record_id": "<urn:uuid:222>", "url_hash": "u3", "normalized_text_sha256": "h3", "near_duplicate_cluster_id": "n3"}
    unique = normalize_row(_row(url="https://other.example/a", warc_record_id="<urn:uuid:333>", warc_payload_digest="sha1:OTHER", text=_text("beta")), row_index=2, **kwargs)

    records, counts = dedupe_records([first, same_warc, same_payload, unique])

    assert len(records) == 2
    assert counts["warc_identity_duplicates"] == 1
    assert counts["payload_digest_duplicates"] == 2
    assert deterministic_near_duplicate_cluster(first["normalized_text"]) == first["near_duplicate_cluster_id"]


def test_private_candidate_db_streams_global_dedupe_and_month_selection(tmp_path):
    db_path = tmp_path / "services" / "data" / "publication_shift" / "infini_news_v1" / "candidate_records.sqlite3"
    conn = connect_private_candidate_db(db_path)
    kwargs = {"shard_path": "data/year=2025/month=01/part.parquet", "shard_sha256": "sha", "retrieved_at": "now"}
    first = normalize_row(_row(text=_text("alpha")), row_index=1, **kwargs)
    duplicate_url = normalize_row(_row(text=_text("beta")), row_index=2, **kwargs)
    unique = normalize_row(
        _row(url="https://other.example/a", warc_record_id="<urn:uuid:333>", warc_payload_digest="sha1:OTHER", text=_text("gamma")),
        row_index=3,
        **kwargs,
    )

    assert add_candidate_record(conn, first) is True
    assert add_candidate_record(conn, duplicate_url) is False
    assert add_candidate_record(conn, unique) is True
    conn.commit()

    counts = duplicate_counts_from_db(conn)
    assert counts["input_count"] == 3
    assert counts["kept_count"] == 2
    assert counts["duplicate_count"] == 1
    assert counts["url_duplicates"] == 1
    selected, rejected = select_month_rows_from_db(conn, month="2024-12", target=2, seed=123, per_sitename_cap=2)
    assert [row["document_id"] for row in selected] == sorted(row["document_id"] for row in [first, unique])
    assert rejected == {}
    assert month_quota_satisfied_in_db(conn, month="2024-12", target=2, seed=123, per_sitename_cap=2) is True
    assert month_quota_satisfied_in_db(conn, month="2024-12", target=3, seed=123, per_sitename_cap=2) is False
    conn.close()
    assert stat.S_IMODE(os.stat(db_path).st_mode) == 0o600


def test_collision_query_uses_payload_partial_index_without_candidate_scan(tmp_path):
    db_path = tmp_path / "services" / "data" / "publication_shift" / "infini_news_v1" / "candidate_records.sqlite3"
    conn = connect_private_candidate_db(db_path)
    params = ("warc", "sha1:payload", "sha1:payload", "url", "text", "near")
    plan = conn.execute("EXPLAIN QUERY PLAN " + CANDIDATE_COLLISION_QUERY, params).fetchall()
    details = "\n".join(str(row[-1]) for row in plan)
    conn.close()

    assert "idx_candidates_payload" in details
    assert "SCAN candidates" not in details


def test_db_selection_matches_list_selection_without_per_document_queries(tmp_path):
    db_path = tmp_path / "services" / "data" / "publication_shift" / "infini_news_v1" / "candidate_records.sqlite3"
    conn = connect_private_candidate_db(db_path)
    kwargs = {"shard_path": "data/year=2025/month=01/part.parquet", "shard_sha256": "sha", "retrieved_at": "now"}
    records = []
    for idx in range(6):
        records.append(
            normalize_row(
                _row(
                    url=f"https://site{idx % 2}.example/story-{idx}",
                    url_hostname=f"site{idx % 2}.example",
                    sitename=f"site-{idx % 2}",
                    warc_record_id=f"<urn:uuid:{idx:032d}>",
                    warc_target_uri=f"https://site{idx % 2}.example/story-{idx}",
                    warc_payload_digest=f"sha1:{idx}",
                    text=_text(f"unique{idx}"),
                ),
                row_index=idx,
                **kwargs,
            )
        )
    for record in records:
        assert add_candidate_record(conn, record) is True
    conn.commit()

    expected, _ = select_month_rows(records, month="2024-12", target=4, seed=123, per_sitename_cap=2)
    statements = []
    conn.set_trace_callback(statements.append)
    actual, _ = select_month_rows_from_db(conn, month="2024-12", target=4, seed=123, per_sitename_cap=2)
    conn.set_trace_callback(None)
    conn.close()

    assert [row["document_id"] for row in actual] == [row["document_id"] for row in expected]
    assert not any("WHERE document_id =" in statement for statement in statements)


def test_collect_stops_inside_shard_when_publish_month_quota_is_satisfied(tmp_path, monkeypatch):
    shard_path = "data/year=2025/month=01/part-test.parquet"
    consumed = []
    rows = []
    for idx in range(5):
        rows.append(
            _row(
                publish_date="2025-01-01",
                warc_date=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
                url=f"https://site{idx}.example/story-{idx}",
                url_hostname=f"site{idx}.example",
                sitename=f"site-{idx}",
                warc_record_id=f"<urn:uuid:{idx:032d}>",
                warc_target_uri=f"https://site{idx}.example/story-{idx}",
                warc_payload_digest=f"sha1:{idx}",
                text=_text(f"row{idx}"),
            )
        )

    def fake_read_shard_rows(_path):
        for idx, row in enumerate(rows):
            consumed.append(idx)
            yield idx, row

    monkeypatch.setattr(
        collector,
        "hub_file_manifest",
        lambda **_kwargs: [{"path": shard_path, "year_month": "2025-01", "lfs_sha256": "sha"}],
    )
    monkeypatch.setattr(collector, "read_shard_rows", fake_read_shard_rows)
    monkeypatch.setattr(collector, "IN_SHARD_QUOTA_CHECK_EVERY_ACCEPTED", 1)
    manifest = {
        "source_revision": FROZEN_REVISION,
        "targets_by_month": {"2025-01": 2},
        "sample_seed": 123,
        "per_sitename_month_cap": 1,
    }
    output_root = tmp_path / "services" / "data" / "publication_shift" / "infini_news_v1"

    result = collector.collect(manifest, output_root)
    progress = json.loads((output_root / "progress.json").read_text())

    assert consumed == [0, 1]
    assert len(result["records"]) == 2
    assert progress["shards"][shard_path]["rows_seen"] == 2
    assert progress["shards"][shard_path]["complete"] is False
    assert progress["shards"][shard_path]["skipped"] == "month_quota_satisfied_mid_shard"


def test_in_shard_quota_stop_uses_publish_date_not_partition_month(tmp_path, monkeypatch):
    shard_path = "data/year=2025/month=01/part-date-lag.parquet"
    consumed = []
    rows = []
    for idx, publish_date in enumerate(["2024-12-31", "2024-12-31", "2025-01-01", "2025-01-01", "2025-01-01"]):
        rows.append(
            _row(
                publish_date=publish_date,
                warc_date=dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc),
                url=f"https://date{idx}.example/story-{idx}",
                url_hostname=f"date{idx}.example",
                sitename=f"site-{idx}",
                warc_record_id=f"<urn:uuid:{idx + 100:032d}>",
                warc_target_uri=f"https://date{idx}.example/story-{idx}",
                warc_payload_digest=f"sha1:date-{idx}",
                text=_text(f"date{idx}"),
            )
        )

    def fake_read_shard_rows(_path):
        for idx, row in enumerate(rows):
            consumed.append(idx)
            yield idx, row

    monkeypatch.setattr(
        collector,
        "hub_file_manifest",
        lambda **_kwargs: [{"path": shard_path, "year_month": "2025-01", "lfs_sha256": "sha"}],
    )
    monkeypatch.setattr(collector, "read_shard_rows", fake_read_shard_rows)
    monkeypatch.setattr(collector, "IN_SHARD_QUOTA_CHECK_EVERY_ACCEPTED", 1)
    manifest = {
        "source_revision": FROZEN_REVISION,
        "targets_by_month": {"2025-01": 2},
        "sample_seed": 123,
        "per_sitename_month_cap": 1,
    }
    output_root = tmp_path / "services" / "data" / "publication_shift" / "infini_news_v1"

    result = collector.collect(manifest, output_root)

    assert consumed == [0, 1, 2, 3]
    assert len(result["records"]) == 2
    assert {row["publication_year_month"] for row in result["records"]} == {"2025-01"}


def test_seeded_month_selection_is_deterministic_and_enforces_sitename_cap():
    rows = []
    for idx in range(6):
        rows.append({"document_id": f"a{idx}", "publication_date": "2025-01-01", "publication_year_month": "2025-01", "sitename": "A"})
    for idx in range(6):
        rows.append({"document_id": f"b{idx}", "publication_date": "2025-01-01", "publication_year_month": "2025-01", "sitename": "B"})

    selected1, rejected1 = select_month_rows(rows, month="2025-01", target=6, seed=123, per_sitename_cap=3)
    selected2, rejected2 = select_month_rows(rows, month="2025-01", target=6, seed=123, per_sitename_cap=3)

    assert [r["document_id"] for r in selected1] == [r["document_id"] for r in selected2]
    assert {r["sitename"] for r in selected1} == {"A", "B"}
    assert sum(1 for r in selected1 if r["sitename"] == "A") <= 3
    assert rejected1 == rejected2


def test_private_and_public_outputs_are_restrictive_and_no_text(tmp_path):
    private = tmp_path / "services" / "data" / "publication_shift" / "infini_news_v1" / "rows.jsonl"
    write_private_jsonl(private, [{"text": "private fixture body"}])
    assert stat.S_IMODE(os.stat(private).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(private.parent).st_mode) == 0o700

    row = normalize_row(_row(), shard_path="data/year=2025/month=01/part.parquet", shard_sha256="sha", row_index=1, retrieved_at="now")
    manifest = build_public_safe_manifest([row], request_manifest=default_manifest(pilot=True), rejected_counts={}, duplicate_counts={}, shard_identities=[])
    encoded = json.dumps(manifest, sort_keys=True).lower()
    assert "original_text" not in encoded
    assert "normalized_text\"" not in encoded
    assert "title\"" not in encoded
    assert "preview\"" not in encoded
    assert "\"sitename\"" not in encoded
    assert "\"url_hostname\"" not in encoded
    assert manifest["counts_by_sitename_hash"] == {collector.public_identifier_hash(row["sitename"]): 1}
    assert manifest["records"][0]["sitename_hash"] == collector.public_identifier_hash(row["sitename"])
    assert manifest["records"][0]["url_hostname_hash"] == collector.public_identifier_hash(row["url_hostname"])
    assert "this score does not establish ai authorship" in encoded

    public = tmp_path / "report.json"
    write_public_json(public, manifest)
    assert public.exists()

    streamed = tmp_path / "streamed_report.json"
    no_records = {key: value for key, value in manifest.items() if key != "records"}
    write_public_manifest_streamed(streamed, no_records, [row])
    streamed_payload = json.loads(streamed.read_text(encoding="utf-8"))
    assert streamed_payload["records"] == manifest["records"]


def test_streamed_public_manifest_many_records_is_valid_json(tmp_path):
    rows = []
    for idx in range(3):
        rows.append(
            normalize_row(
                _row(
                    url=f"https://stream{idx}.example/story",
                    url_hostname=f"stream{idx}.example",
                    sitename=f"stream-{idx}",
                    warc_record_id=f"<urn:uuid:{idx:032d}>",
                    warc_target_uri=f"https://stream{idx}.example/story",
                    warc_payload_digest=f"sha1:stream-{idx}",
                    text=_text(f"stream{idx}"),
                ),
                shard_path="data/year=2025/month=01/part.parquet",
                shard_sha256="sha",
                row_index=idx,
                retrieved_at="now",
            )
        )
    manifest = build_public_safe_manifest(
        rows,
        request_manifest=default_manifest(pilot=True),
        rejected_counts={},
        duplicate_counts={},
        shard_identities=[],
        include_records=False,
    )

    streamed = tmp_path / "streamed_many_records.json"
    write_public_manifest_streamed(streamed, manifest, rows)

    parsed = json.loads(streamed.read_text(encoding="utf-8"))
    assert [record["document_id"] for record in parsed["records"]] == [record["document_id"] for record in rows]


def test_public_writer_rejects_text_like_public_artifacts(tmp_path):
    with pytest.raises(InfiniNewsSchemaError):
        write_public_json(tmp_path / "bad.json", {"records": [{"title": "do not publish"}]})


@pytest.mark.parametrize(
    "payload",
    [
        {"counts_by_sitename": {"Aston Villa v Juventus Odds & Match Preview": 3}},
        {"counts_by_sitename_hash": {"Aston Villa v Juventus Odds & Match Preview": 3}},
        {"counts_by_unregistered": {"arbitrary title-like value": 3}},
        {"counts_by_sitename_hash": {"a" * 64: "not-an-integer"}},
        {"private_path": "/home/example/private/article.jsonl"},
    ],
)
def test_public_writer_fails_closed_on_unsafe_count_maps_and_local_paths(tmp_path, payload):
    with pytest.raises(InfiniNewsSchemaError):
        write_public_json(tmp_path / "unsafe.json", payload)


def test_public_writer_allows_only_hashed_sitename_counts(tmp_path):
    path = tmp_path / "safe-counts.json"
    payload = {"counts_by_sitename_hash": {"a" * 64: 3}}

    write_public_json(path, payload)

    assert json.loads(path.read_text()) == payload


def test_role_assignment_matches_design_windows():
    assert assign_corpus_role(2016, 8) == "historical_placebo"
    assert assign_corpus_role(2016, 7) is None
    assert assign_corpus_role(2018, 1) == "pre_llm_core"
    assert assign_corpus_role(2022, 6) == "transition_2022"
    assert assign_corpus_role(2025, 12) == "current_core"
    assert assign_corpus_role(2026, 4) == "forward_2026"
    assert assign_corpus_role(2026, 5) is None
