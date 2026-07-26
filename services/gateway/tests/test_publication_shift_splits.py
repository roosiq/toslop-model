from build_publication_shift_splits import (
    assert_no_leakage,
    build_author_heldout_split,
    build_infini_news_protocols,
    build_source_publisher_heldout_split,
)


def _row(idx, source="S1", publisher="P1", authors=None, cluster=None):
    return {
        "document_id": f"doc{idx}",
        "work_id": f"W{idx}",
        "doi": f"10.1/{idx}",
        "normalized_text_sha256": f"hash{idx}",
        "near_duplicate_cluster_id": cluster or f"cluster{idx}",
        "source_id": source,
        "publisher_id": publisher,
        "author_ids": authors or [f"A{idx}"],
        "corpus_role": "pre_llm_core" if idx % 2 else "current_core",
    }


def _infini_row(idx, *, year=2020, role="pre_llm_core", domain=None, sitename=None, author=None, topic="politics"):
    return {
        "document_id": f"infini{idx}",
        "identity_hash": f"identity{idx}",
        "warc_filename_hash": f"warc-file-{idx}",
        "warc_record_id_hash": f"warc-record-{idx}",
        "warc_target_uri_hash": f"warc-target-{idx}",
        "warc_payload_digest_hash": f"payload{idx}",
        "normalized_url_hash": f"url{idx}",
        "normalized_text_sha256": f"text{idx}",
        "near_duplicate_cluster_id": f"near{idx}",
        "url_hostname": domain or f"domain{idx % 3}.example",
        "sitename": sitename or f"Site {idx % 4}",
        "author_hash": author,
        "topic": topic,
        "publication_year": year,
        "publication_month": 1,
        "publication_year_month": f"{year}-01",
        "corpus_role": role,
    }


def test_source_publisher_heldout_keeps_groups_out_of_train():
    rows = [
        _row(1, source="S1", publisher="P1"),
        _row(2, source="S1", publisher="P1"),
        _row(3, source="S2", publisher="P2"),
        _row(4, source="S3", publisher="P3"),
    ]

    manifest = build_source_publisher_heldout_split(rows, holdout_fraction=0.5, seed="unit")

    for left, right in (("train", "test"), ("train", "validation"), ("validation", "test")):
        left_sources = {entry["source_id"] for entry in manifest["assignments"] if entry["split"] == left}
        right_sources = {entry["source_id"] for entry in manifest["assignments"] if entry["split"] == right}
        left_publishers = {entry["publisher_id"] for entry in manifest["assignments"] if entry["split"] == left}
        right_publishers = {entry["publisher_id"] for entry in manifest["assignments"] if entry["split"] == right}
        assert left_sources.isdisjoint(right_sources)
        assert left_publishers.isdisjoint(right_publishers)
    assert manifest["overlap_audit"]["source_id"] == 0
    assert manifest["overlap_audit"]["publisher_id"] == 0


def test_shared_publisher_connects_sources_into_one_partition():
    rows = [
        _row(1, source="S1", publisher="P1"),
        _row(2, source="S2", publisher="P1"),
        _row(3, source="S2", publisher="P2"),
    ]

    manifest = build_source_publisher_heldout_split(rows, holdout_fraction=0.3, validation_fraction=0.3, seed="bridge")

    assert len({entry["split"] for entry in manifest["assignments"]}) == 1
    assert manifest["overlap_audit"]["source_id"] == 0
    assert manifest["overlap_audit"]["publisher_id"] == 0


def test_author_heldout_drops_bridge_works_before_assignment():
    rows = [
        _row(1, authors=["A_train"]),
        _row(2, authors=["A_test"]),
        _row(3, authors=["A_train", "A_test"]),
        _row(4, authors=["A_other"]),
    ]

    manifest = build_author_heldout_split(rows, holdout_fraction=0.75, seed="unit")

    assigned_docs = {entry["document_id"] for entry in manifest["assignments"]}
    assert "doc3" not in assigned_docs
    assert manifest["dropped_bridge_work_count"] == 1
    assert manifest["overlap_audit"]["author_ids"] == 0


def test_leakage_audit_catches_work_doi_hash_and_cluster_overlap():
    assignments = [
        {**_row(1), "split": "train"},
        {**_row(2), "work_id": "W1", "split": "test"},
        {**_row(3), "doi": "10.1/1", "split": "validation"},
        {**_row(4), "normalized_text_sha256": "hash1", "split": "test"},
        {**_row(5), "near_duplicate_cluster_id": "cluster1", "split": "validation"},
    ]

    audit = assert_no_leakage(assignments)

    assert audit["work_id"] == 1
    assert audit["doi"] == 1
    assert audit["normalized_text_sha256"] == 1
    assert audit["near_duplicate_cluster_id"] == 1


def test_infini_news_protocols_freeze_required_lanes_and_eval_only_years():
    rows = [
        _infini_row(1, year=2018, role="pre_llm_core", domain="a.example", sitename="A", author="alice", topic="politics"),
        _infini_row(2, year=2019, role="pre_llm_core", domain="a.example", sitename="A", author="bob", topic="sports"),
        _infini_row(3, year=2023, role="current_core", domain="b.example", sitename="B", author="alice", topic="politics"),
        _infini_row(4, year=2024, role="current_core", domain="c.example", sitename="C", author="carol", topic="finance"),
        _infini_row(5, year=2022, role="transition_2022", domain="transition.example", sitename="Transition", author="dana"),
        _infini_row(6, year=2026, role="forward_2026", domain="forward.example", sitename="Forward", author="erin"),
    ]

    package = build_infini_news_protocols(rows, seed="unit")

    assert package["schema"] == "publication_shift.infini_news_split_protocols.v1"
    assert package["caveat"] == "This score does not establish AI authorship."
    assert package["fit_roles"] == ["current_core", "pre_llm_core"]
    assert package["evaluation_only_roles"] == ["forward_2026", "historical_placebo", "transition_2022"]
    assert set(package["protocols"]) >= {
        "publisher_domain_heldout_primary",
        "source_sitename_heldout",
        "author_heldout",
        "topic_heldout",
        "random_diagnostic",
        "transition_2022",
        "forward_2026",
        "same_author_pre_post",
    }
    for protocol_name in ["publisher_domain_heldout_primary", "source_sitename_heldout", "topic_heldout", "random_diagnostic"]:
        manifest = package["protocols"][protocol_name]
        assert {entry["corpus_role"] for entry in manifest["assignments"]} <= {"pre_llm_core", "current_core"}
        assert manifest["excluded_role_counts"] == {"forward_2026": 1, "transition_2022": 1}
        assert all(value == 0 for value in manifest["overlap_audit"].values())
    assert {entry["split"] for entry in package["protocols"]["transition_2022"]["assignments"]} == {"evaluation_only"}
    assert {entry["split"] for entry in package["protocols"]["forward_2026"]["assignments"]} == {"evaluation_only"}


def test_infini_author_heldout_drops_missing_and_bridge_author_rows():
    rows = [
        _infini_row(1, author="same-author", role="pre_llm_core", year=2018),
        _infini_row(2, author="same-author", role="current_core", year=2023),
        _infini_row(3, author=None, role="pre_llm_core", year=2019),
        {**_infini_row(4, author="bridge", role="current_core", year=2024), "author_hashes": ["bridge-a", "bridge-b"]},
    ]

    package = build_infini_news_protocols(rows, seed="unit")
    author = package["protocols"]["author_heldout"]

    assert author["support"]["status"] == "supported"
    assert author["dropped_missing_author_count"] == 1
    assert author["dropped_bridge_work_count"] == 1
    assert {entry["document_id"] for entry in author["assignments"]} == {"infini1", "infini2"}
    assert author["overlap_audit"]["author_hash"] == 0
    same_author = package["protocols"]["same_author_pre_post"]
    assert same_author["pair_count"] == 1
    assert same_author["support"]["status"] == "supported"
