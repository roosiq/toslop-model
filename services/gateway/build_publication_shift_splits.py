#!/usr/bin/env python3
"""Build leakage-safe split manifests for publication-shift corpus rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

NO_TEXT_SCHEMA = "publication_shift.split_manifest.v1"
INFINI_PROTOCOL_SCHEMA = "publication_shift.infini_news_split_protocols.v1"
INFINI_SUMMARY_SCHEMA = "publication_shift.infini_news_split_summary.v1"
CAVEAT = "This score does not establish AI authorship."
LEAKAGE_KEYS = ["work_id", "doi", "normalized_text_sha256", "near_duplicate_cluster_id"]
INFINI_LEAKAGE_KEYS = [
    "identity_hash",
    "warc_identity_hash",
    "warc_payload_digest_hash",
    "normalized_url_hash",
    "normalized_text_sha256",
    "near_duplicate_cluster_id",
]
FIT_ROLES = ["current_core", "pre_llm_core"]
EVALUATION_ONLY_ROLES = ["forward_2026", "historical_placebo", "transition_2022"]
PUBLIC_BANNED_KEYS = {"text", "original_text", "normalized_text", "title", "description", "preview", "body", "content"}


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


def _counter_dict(values: Iterable[str | None]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values if value is not None).items()))


def _warc_identity_hash(row: dict[str, Any]) -> str | None:
    if row.get("warc_identity_hash"):
        return str(row["warc_identity_hash"])
    values = [row.get("warc_filename_hash"), row.get("warc_record_id_hash"), row.get("warc_target_uri_hash")]
    if all(values):
        return hashlib.sha256("|".join(str(value) for value in values).encode("utf-8")).hexdigest()
    return None


def _author_hashes(row: dict[str, Any]) -> list[str]:
    if row.get("author_hashes"):
        return sorted(str(value) for value in row.get("author_hashes") or [] if value)
    if row.get("author_hash"):
        return [str(row["author_hash"])]
    return []


def _infini_public_assignment(row: dict[str, Any], split: str) -> dict[str, Any]:
    return {
        "document_id": row["document_id"],
        "identity_hash": row.get("identity_hash"),
        "warc_identity_hash": _warc_identity_hash(row),
        "warc_payload_digest_hash": row.get("warc_payload_digest_hash"),
        "normalized_url_hash": row.get("normalized_url_hash"),
        "normalized_text_sha256": row.get("normalized_text_sha256"),
        "near_duplicate_cluster_id": row.get("near_duplicate_cluster_id"),
        "url_hostname": row.get("url_hostname"),
        "sitename": row.get("sitename"),
        "author_hash": row.get("author_hash"),
        "author_hashes": _author_hashes(row),
        "topic": row.get("topic"),
        "publication_year": row.get("publication_year"),
        "publication_month": row.get("publication_month"),
        "publication_year_month": row.get("publication_year_month"),
        "corpus_role": row.get("corpus_role"),
        "split": split,
    }


def _infini_overlap_audit(assignments: list[dict[str, Any]], extra_keys: Iterable[str] = ()) -> dict[str, int]:
    audit: dict[str, int] = {}
    for key in [*INFINI_LEAKAGE_KEYS, *extra_keys]:
        by_value: dict[str, set[str]] = defaultdict(set)
        for row in assignments:
            if key == "author_hash":
                for author_hash in row.get("author_hashes") or ([row.get("author_hash")] if row.get("author_hash") else []):
                    by_value[str(author_hash)].add(row["split"])
                continue
            value = row.get(key)
            if value:
                by_value[str(value)].add(row["split"])
        audit[key] = sum(1 for splits in by_value.values() if len(splits) > 1)
    return audit


def _fit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fit_roles = set(FIT_ROLES)
    return [row for row in rows if row.get("corpus_role") in fit_roles]


def _excluded_role_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    fit_roles = set(FIT_ROLES)
    return _counter_dict(str(row.get("corpus_role")) for row in rows if row.get("corpus_role") not in fit_roles)


def _split_manifest(
    *,
    protocol: str,
    rows: list[dict[str, Any]],
    group_key: str,
    seed: str,
    holdout_fraction: float,
    validation_fraction: float,
    extra_audit_keys: Iterable[str] = (),
    support: dict[str, Any] | None = None,
    assignments_override: list[dict[str, Any]] | None = None,
    excluded_role_counts: dict[str, int] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if assignments_override is None:
        assignments = []
        for row in sorted(rows, key=lambda item: item["document_id"]):
            value = str(row.get(group_key) or "missing")
            assignments.append(_infini_public_assignment(row, stable_split(value, f"{seed}:{protocol}", holdout_fraction, validation_fraction)))
    else:
        assignments = assignments_override
    manifest = {
        "schema": NO_TEXT_SCHEMA,
        "protocol": protocol,
        "caveat": CAVEAT,
        "seed": seed,
        "assignment_stage": "document_before_features_or_chunks",
        "fit_roles": FIT_ROLES,
        "evaluation_only_roles": EVALUATION_ONLY_ROLES,
        "holdout_fraction": holdout_fraction,
        "validation_fraction": validation_fraction,
        "excluded_role_counts": excluded_role_counts or {},
        "assignments": assignments,
        "counts": _counts(assignments),
        "counts_by_role": _counter_dict(row.get("corpus_role") for row in assignments),
        "overlap_audit": _infini_overlap_audit(assignments, extra_keys=extra_audit_keys),
        "support": support or {"status": "supported"},
    }
    if extra_fields:
        manifest.update(extra_fields)
    return manifest


def _author_heldout_manifest(rows: list[dict[str, Any]], seed: str, holdout_fraction: float, validation_fraction: float, excluded: dict[str, int]) -> dict[str, Any]:
    author_to_split: dict[str, str] = {}
    for row in rows:
        for author_hash in _author_hashes(row):
            author_to_split[author_hash] = stable_split(author_hash, f"{seed}:author_heldout", holdout_fraction, validation_fraction)
    assignments = []
    dropped_bridge = 0
    dropped_missing = 0
    for row in sorted(rows, key=lambda item: item["document_id"]):
        authors = _author_hashes(row)
        if not authors:
            dropped_missing += 1
            continue
        splits = {author_to_split[author] for author in authors if author in author_to_split}
        if len(splits) != 1:
            dropped_bridge += 1
            continue
        assignments.append(_infini_public_assignment(row, next(iter(splits))))
    support = {
        "status": "supported" if assignments else "unsupported",
        "reason": None if assignments else "no rows with non-bridging author_hash support",
    }
    manifest = _split_manifest(
        protocol="author_heldout",
        rows=rows,
        group_key="author_hash",
        seed=seed,
        holdout_fraction=holdout_fraction,
        validation_fraction=validation_fraction,
        extra_audit_keys=["author_hash"],
        support=support,
        assignments_override=assignments,
        excluded_role_counts=excluded,
        extra_fields={
            "dropped_bridge_work_count": dropped_bridge,
            "dropped_missing_author_count": dropped_missing,
        },
    )
    return manifest


def _same_author_pre_post(rows: list[dict[str, Any]], seed: str) -> dict[str, Any]:
    by_author: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for author_hash in _author_hashes(row):
            by_author[author_hash].append(row)
    pairs = []
    for author_hash, author_rows in sorted(by_author.items()):
        pre = [row for row in author_rows if row.get("corpus_role") == "pre_llm_core"]
        cur = [row for row in author_rows if row.get("corpus_role") == "current_core"]
        if not pre or not cur:
            continue
        before = sorted(pre, key=lambda row: (str(row.get("publication_year_month")), row["document_id"]))[0]
        after = sorted(cur, key=lambda row: (str(row.get("publication_year_month")), row["document_id"]))[0]
        pairs.append(
            {
                "author_hash": author_hash,
                "pre_document_id": before["document_id"],
                "pre_publication_year_month": before.get("publication_year_month"),
                "current_document_id": after["document_id"],
                "current_publication_year_month": after.get("publication_year_month"),
                "pair_id": hashlib.sha256(f"{seed}|{author_hash}|{before['document_id']}|{after['document_id']}".encode("utf-8")).hexdigest()[:24],
            }
        )
    return {
        "schema": NO_TEXT_SCHEMA,
        "protocol": "same_author_pre_post",
        "caveat": CAVEAT,
        "seed": seed,
        "assignment_stage": "document_before_features_or_chunks",
        "support": {"status": "supported" if pairs else "unsupported", "reason": None if pairs else "no authors with both pre_llm_core and current_core rows"},
        "pair_count": len(pairs),
        "pairs": pairs,
    }


def _evaluation_only_manifest(rows: list[dict[str, Any]], role: str, protocol: str, seed: str) -> dict[str, Any]:
    assignments = [_infini_public_assignment(row, "evaluation_only") for row in sorted(rows, key=lambda item: item["document_id"]) if row.get("corpus_role") == role]
    return {
        "schema": NO_TEXT_SCHEMA,
        "protocol": protocol,
        "caveat": CAVEAT,
        "seed": seed,
        "assignment_stage": "document_before_features_or_chunks",
        "fit_exclusion": "excluded_from_fitting_calibration_and_threshold_selection",
        "assignments": assignments,
        "counts": _counts(assignments),
        "counts_by_role": _counter_dict(row.get("corpus_role") for row in assignments),
        "overlap_audit": _infini_overlap_audit(assignments),
        "support": {"status": "supported" if assignments else "unsupported", "reason": None if assignments else f"no {role} rows"},
    }


def build_infini_news_protocols(
    rows: list[dict[str, Any]],
    *,
    seed: str = "infini_news_v1_publication_shift",
    holdout_fraction: float = 0.2,
    validation_fraction: float = 0.1,
) -> dict[str, Any]:
    fit_rows = _fit_rows(rows)
    excluded = _excluded_role_counts(rows)
    protocols = {
        "publisher_domain_heldout_primary": _split_manifest(
            protocol="publisher_domain_heldout_primary",
            rows=fit_rows,
            group_key="url_hostname",
            seed=seed,
            holdout_fraction=holdout_fraction,
            validation_fraction=validation_fraction,
            extra_audit_keys=["url_hostname"],
            excluded_role_counts=excluded,
        ),
        "source_sitename_heldout": _split_manifest(
            protocol="source_sitename_heldout",
            rows=fit_rows,
            group_key="sitename",
            seed=seed,
            holdout_fraction=holdout_fraction,
            validation_fraction=validation_fraction,
            extra_audit_keys=["sitename"],
            excluded_role_counts=excluded,
        ),
        "topic_heldout": _split_manifest(
            protocol="topic_heldout",
            rows=fit_rows,
            group_key="topic",
            seed=seed,
            holdout_fraction=holdout_fraction,
            validation_fraction=validation_fraction,
            extra_audit_keys=["topic"],
            excluded_role_counts=excluded,
            extra_fields={"topic_protocol": "predeclared_metadata_topic_groups_assigned_before_features"},
        ),
        "random_diagnostic": _split_manifest(
            protocol="random_diagnostic",
            rows=fit_rows,
            group_key="document_id",
            seed=seed,
            holdout_fraction=holdout_fraction,
            validation_fraction=validation_fraction,
            excluded_role_counts=excluded,
            extra_fields={"diagnostic_only": True},
        ),
        "author_heldout": _author_heldout_manifest(fit_rows, seed, holdout_fraction, validation_fraction, excluded),
        "same_author_pre_post": _same_author_pre_post(fit_rows, seed),
        "transition_2022": _evaluation_only_manifest(rows, "transition_2022", "transition_2022", seed),
        "forward_2026": _evaluation_only_manifest(rows, "forward_2026", "forward_2026_jan_apr", seed),
        "historical_placebo": _evaluation_only_manifest(rows, "historical_placebo", "historical_placebo", seed),
    }
    return {
        "schema": INFINI_PROTOCOL_SCHEMA,
        "caveat": CAVEAT,
        "seed": seed,
        "assignment_stage": "documents_assigned_before_features_or_chunks",
        "fit_roles": FIT_ROLES,
        "evaluation_only_roles": EVALUATION_ONLY_ROLES,
        "fit_exclusion": "2022_transition_and_2026_forward_rows_excluded_from_fitting_calibration_and_thresholds",
        "row_counts": {
            "total": len(rows),
            "fit_rows": len(fit_rows),
            "excluded_role_counts": excluded,
            "by_role": _counter_dict(row.get("corpus_role") for row in rows),
        },
        "protocols": protocols,
    }


def protocol_summary(package: dict[str, Any]) -> dict[str, Any]:
    protocols = package["protocols"]
    summary_protocols = {}
    for name, manifest in protocols.items():
        assignments = manifest.get("assignments") or []
        pairs = manifest.get("pairs") or []
        summary_protocols[name] = {
            "protocol": manifest.get("protocol"),
            "assignment_count": len(assignments),
            "assignment_sha256": stable_json_sha256(assignments) if assignments else None,
            "counts": manifest.get("counts"),
            "counts_by_role": manifest.get("counts_by_role"),
            "overlap_audit": manifest.get("overlap_audit"),
            "support": manifest.get("support"),
            "excluded_role_counts": manifest.get("excluded_role_counts"),
            "dropped_bridge_work_count": manifest.get("dropped_bridge_work_count"),
            "dropped_missing_author_count": manifest.get("dropped_missing_author_count"),
            "pair_count": manifest.get("pair_count"),
            "pair_sha256": stable_json_sha256(pairs) if pairs else None,
        }
    return {
        "schema": INFINI_SUMMARY_SCHEMA,
        "caveat": CAVEAT,
        "seed": package["seed"],
        "assignment_stage": package["assignment_stage"],
        "fit_roles": package["fit_roles"],
        "evaluation_only_roles": package["evaluation_only_roles"],
        "fit_exclusion": package["fit_exclusion"],
        "row_counts": package["row_counts"],
        "protocols": summary_protocols,
    }


def stable_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def render_infini_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# INFINI-NEWS v1 split protocol summary (text-free)",
        "",
        CAVEAT,
        "",
        "## Scope",
        "",
        f"- Assignment stage: `{summary['assignment_stage']}`",
        f"- Fit roles: `{json.dumps(summary['fit_roles'])}`",
        f"- Evaluation-only roles: `{json.dumps(summary['evaluation_only_roles'])}`",
        f"- Fit/calibration/threshold exclusion: `{summary['fit_exclusion']}`",
        f"- Row counts: `{json.dumps(summary['row_counts'], sort_keys=True)}`",
        "",
        "## Protocol counts and leakage audits",
        "",
        "| Protocol | Support | Assignments | Counts | Overlap audit | Assignment hash | Limitations |",
        "|---|---|---:|---|---|---|---|",
    ]
    for name, manifest in sorted(summary["protocols"].items()):
        support = manifest.get("support") or {}
        limitations = []
        if manifest.get("dropped_missing_author_count"):
            limitations.append(f"missing_author={manifest['dropped_missing_author_count']}")
        if manifest.get("dropped_bridge_work_count"):
            limitations.append(f"bridge_drops={manifest['dropped_bridge_work_count']}")
        if manifest.get("pair_count") is not None:
            limitations.append(f"same_author_pairs={manifest['pair_count']}")
        if support.get("reason"):
            limitations.append(str(support["reason"]))
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    str(support.get("status")),
                    str(manifest.get("assignment_count") or 0),
                    f"`{json.dumps(manifest.get('counts'), sort_keys=True)}`",
                    f"`{json.dumps(manifest.get('overlap_audit'), sort_keys=True)}`",
                    f"`{manifest.get('assignment_sha256') or manifest.get('pair_sha256') or ''}`",
                    ", ".join(limitations) if limitations else "none",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Integrity notes",
            "",
            "- WARC identity, payload digest, URL hash, text hash, and near-duplicate cluster overlap audits are computed across model-bearing partitions for each model-bearing protocol.",
            "- Publisher/domain, source/sitename, topic, author, and random-diagnostic assignments use only document-level metadata and occur before any features or chunks are built.",
            "- 2022 transition and January-April 2026 forward rows are written as evaluation-only protocols and are excluded from fitting, calibration, and threshold selection.",
            "- Public artifacts contain IDs, hashes, counts, and protocol metadata only; no article text, title, preview, URL, or description is emitted.",
        ]
    )
    return "\n".join(lines) + "\n"


def read_private_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def reject_public_text(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        keys_are_data_values = path.endswith("counts_by_role") or path.endswith("excluded_role_counts")
        for key, value in payload.items():
            lowered = str(key).lower()
            if not keys_are_data_values and (lowered in PUBLIC_BANNED_KEYS or "preview" in lowered):
                raise ValueError(f"split manifest would expose raw text-like field {path}/{key}")
            reject_public_text(value, f"{path}/{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            reject_public_text(value, f"{path}[{index}]")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_public_text(manifest)
    text = json.dumps(manifest, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="publication_shift_v1")
    parser.add_argument("--infini-news", action="store_true", help="Build the frozen INFINI-NEWS v1 protocol package")
    parser.add_argument("--write-full-manifests", action="store_true", help="For INFINI-NEWS, also write per-document assignment manifests")
    args = parser.parse_args(argv)
    rows = read_private_rows(args.corpus / "normalized_rows.jsonl")
    if args.infini_news:
        package = build_infini_news_protocols(rows, seed=args.seed)
        summary = protocol_summary(package)
        if args.write_full_manifests:
            for name, manifest in sorted(package["protocols"].items()):
                write_manifest(args.output / f"{name}.json", manifest)
        write_manifest(args.output / "summary.json", summary)
        (args.output / "SUMMARY_TEXT_FREE.md").write_text(render_infini_summary_markdown(summary), encoding="utf-8")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
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
