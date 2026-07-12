from build_publication_shift_splits import (
    assert_no_leakage,
    build_author_heldout_split,
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
