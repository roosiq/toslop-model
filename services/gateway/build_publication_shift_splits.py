#!/usr/bin/env python3
"""Build leakage-safe split manifests for publication-shift corpus rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

NO_TEXT_SCHEMA = "publication_shift.split_manifest.v1"
LEAKAGE_KEYS = ["work_id", "doi", "normalized_text_sha256", "near_duplicate_cluster_id"]


def stable_bucket(value: str, seed: str) -> float:
    digest = hashlib.sha256(f"{seed}|{value}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16)


def stable_split(value: str, seed: str, holdout_fraction: float, validation_fraction: float) -> str:
    bucket = stable_bucket(value, seed)
    if bucket < holdout_fraction:
        return "test"
    if bucket < holdout_fraction + validation_fraction:
        return "validation"
    return "train"


def source_publisher_components(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Return deterministic bipartite components so neither source nor publisher crosses splits."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        parent[second] = first

    for row in rows:
        union(f"source:{row.get('source_id')}", f"publisher:{row.get('publisher_id')}")

    members: dict[str, list[str]] = defaultdict(list)
    for node in sorted(parent):
        members[find(node)].append(node)
    component_id = {root: min(nodes) for root, nodes in members.items()}
    return {node: component_id[find(node)] for node in parent}


def assert_no_leakage(assignments: list[dict[str, Any]], extra_keys: Iterable[str] = ()) -> dict[str, int]:
    audit: dict[str, int] = {}
    for key in [*LEAKAGE_KEYS, *extra_keys]:
        by_value: dict[str, set[str]] = defaultdict(set)
        for row in assignments:
            value = row.get(key)
            if key == "author_ids":
                for author_id in row.get("author_ids") or []:
                    by_value[str(author_id)].add(row["split"])
                continue
            if value:
                by_value[str(value)].add(row["split"])
        audit[key] = sum(1 for splits in by_value.values() if len(splits) > 1)
    return audit


def _public_assignment(row: dict[str, Any], split: str) -> dict[str, Any]:
    return {
        "document_id": row["document_id"],
        "work_id": row["work_id"],
        "doi": row.get("doi"),
        "normalized_text_sha256": row["normalized_text_sha256"],
        "near_duplicate_cluster_id": row["near_duplicate_cluster_id"],
        "source_id": row.get("source_id"),
        "publisher_id": row.get("publisher_id"),
        "topic_id": row.get("topic_id"),
        "author_ids": sorted(row.get("author_ids") or []),
        "publication_year": row.get("publication_year"),
        "publication_month": row.get("publication_month"),
        "corpus_role": row.get("corpus_role"),
        "split": split,
    }


def build_source_publisher_heldout_split(
    rows: list[dict[str, Any]],
    holdout_fraction: float = 0.2,
    validation_fraction: float = 0.1,
    seed: str = "publication_shift",
) -> dict[str, Any]:
    components = source_publisher_components(rows)
    assignments = []
    for row in sorted(rows, key=lambda item: item["document_id"]):
        component = components[f"source:{row.get('source_id')}"]
        split = stable_split(component, seed, holdout_fraction, validation_fraction)
        assignments.append(_public_assignment(row, split))
    audit = assert_no_leakage(assignments, extra_keys=["source_id", "publisher_id"])
    return {
        "schema": NO_TEXT_SCHEMA,
        "protocol": "source_publisher_heldout",
        "seed": seed,
        "holdout_fraction": holdout_fraction,
        "validation_fraction": validation_fraction,
        "assignments": assignments,
        "overlap_audit": audit,
        "counts": _counts(assignments),
    }


def build_author_heldout_split(
    rows: list[dict[str, Any]],
    holdout_fraction: float = 0.2,
    validation_fraction: float = 0.1,
    seed: str = "publication_shift",
) -> dict[str, Any]:
    author_split: dict[str, str] = {}
    for row in rows:
        for author_id in row.get("author_ids") or []:
            author_split[str(author_id)] = stable_split(str(author_id), seed, holdout_fraction, validation_fraction)
    assignments = []
    dropped = 0
    for row in sorted(rows, key=lambda item: item["document_id"]):
        splits = {author_split[str(author_id)] for author_id in row.get("author_ids") or [] if str(author_id) in author_split}
        if len(splits) != 1:
            dropped += 1
            continue
        assignments.append(_public_assignment(row, next(iter(splits))))
    audit = assert_no_leakage(assignments, extra_keys=["author_ids"])
    return {
        "schema": NO_TEXT_SCHEMA,
        "protocol": "author_heldout",
        "seed": seed,
        "holdout_fraction": holdout_fraction,
        "validation_fraction": validation_fraction,
        "assignments": assignments,
        "dropped_bridge_work_count": dropped,
        "overlap_audit": audit,
        "counts": _counts(assignments),
    }


def _counts(assignments: list[dict[str, Any]]) -> dict[str, int]:
    counts = defaultdict(int)
    for row in assignments:
        counts[row["split"]] += 1
    return dict(sorted(counts.items()))


def read_private_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True)
    lowered = text.lower()
    if "abstract" in lowered or "preview" in lowered:
        raise ValueError("split manifest would expose raw text")
    path.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="publication_shift_v1")
    args = parser.parse_args(argv)
    rows = read_private_rows(args.corpus / "normalized_rows.jsonl")
    source_manifest = build_source_publisher_heldout_split(rows, seed=args.seed)
    author_manifest = build_author_heldout_split(rows, seed=args.seed)
    write_manifest(args.output / "source_publisher_heldout.json", source_manifest)
    write_manifest(args.output / "author_heldout.json", author_manifest)
    summary = {
        "schema": "publication_shift.split_summary.v1",
        "source_publisher_heldout": {
            "counts": source_manifest["counts"],
            "overlap_audit": source_manifest["overlap_audit"],
        },
        "author_heldout": {
            "counts": author_manifest["counts"],
            "overlap_audit": author_manifest["overlap_audit"],
            "dropped_bridge_work_count": author_manifest["dropped_bridge_work_count"],
        },
    }
    write_manifest(args.output / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
