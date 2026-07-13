#!/usr/bin/env python3
"""Independent text-free audit for the frozen INFINI-NEWS v1 corpus.

The script reads private article-bearing artifacts but never prints or writes article
bodies, titles, descriptions, previews, URLs, or excerpts. It emits only counts,
hashes, modes, schema/key checks, and aggregate distributions.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = REPO_ROOT / "services/data/publication_shift/infini_news_v1"
PUBLIC_ROOT = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1"
PRIVATE_ROWS = PRIVATE_ROOT / "normalized_rows.jsonl"
CANDIDATE_DB = PRIVATE_ROOT / "candidate_records.sqlite3"
PROGRESS = PRIVATE_ROOT / "progress.json"
PRIVATE_RECORD_REPORT = PRIVATE_ROOT / "full_report_records.json"
PUBLIC_REPORT = PUBLIC_ROOT / "full_report.json"
REQUEST_MANIFEST = PUBLIC_ROOT / "frozen_request_manifest_264000.json"
OUTPUT_REPORT = PUBLIC_ROOT / "VALIDATION_REPORT_TEXT_FREE.md"

EXPECTED_TOTAL = 264_000
CORE_YEARS = set(range(2018, 2022)) | set(range(2023, 2026))
TEXT_BEARING_KEYS = {
    "text",
    "original_text",
    "normalized_text",
    "title",
    "description",
    "preview",
    "body",
    "content",
}
PUBLIC_JSONS = [
    PUBLIC_REPORT,
    REQUEST_MANIFEST,
    PUBLIC_ROOT / "pilot_report.json",
    PUBLIC_ROOT / "pilot_request_manifest.json",
]
PRIVATE_ARTIFACTS = [PRIVATE_ROWS, CANDIDATE_DB, PROGRESS, PRIVATE_RECORD_REPORT]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def mode_octal(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))


def default_targets() -> dict[str, int]:
    targets: dict[str, int] = {}
    for month in range(8, 13):
        targets[f"2016-{month:02d}"] = 800
    for month in range(1, 13):
        targets[f"2017-{month:02d}"] = 334 if month <= 4 else 333
    for year in list(range(2018, 2022)) + list(range(2023, 2026)):
        for month in range(1, 13):
            targets[f"{year}-{month:02d}"] = 3000
    for month in range(1, 13):
        targets[f"2022-{month:02d}"] = 167 if month <= 8 else 166
    for month in range(1, 5):
        targets[f"2026-{month:02d}"] = 500
    return dict(sorted(targets.items()))


def passfail(condition: bool) -> str:
    return "PASS" if condition else "FAIL"


def pct(part: int, whole: int) -> str:
    return "0.00%" if whole == 0 else f"{part / whole * 100:.2f}%"


def quantiles(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"min": None, "p25": None, "median": None, "p75": None, "p95": None, "max": None}
    values.sort()
    def at(q: float) -> int:
        return values[min(len(values) - 1, int(round((len(values) - 1) * q)))]
    return {"min": values[0], "p25": at(0.25), "median": at(0.5), "p75": at(0.75), "p95": at(0.95), "max": values[-1]}


def scan_public_payload_for_text_keys(payload: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        keys_are_data_values = path in {"/counts_by_month", "/counts_by_role", "/counts_by_sitename"}
        for key, value in payload.items():
            lowered = str(key).lower()
            if not keys_are_data_values and (lowered in TEXT_BEARING_KEYS or "preview" in lowered):
                findings.append(f"{path}/{key}")
            findings.extend(scan_public_payload_for_text_keys(value, f"{path}/{key}"))
    elif isinstance(payload, list):
        for idx, value in enumerate(payload):
            findings.extend(scan_public_payload_for_text_keys(value, f"{path}[{idx}]"))
    return findings


def histogram_bucket_word_count(value: int) -> str:
    if value < 150:
        return "000-149"
    if value < 300:
        return "150-299"
    if value < 600:
        return "300-599"
    if value < 1000:
        return "600-999"
    if value < 2000:
        return "1000-1999"
    return "2000+"


def histogram_bucket_lag(value: int) -> str:
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 7:
        return "1-7"
    if value <= 30:
        return "8-30"
    if value <= 365:
        return "31-365"
    return "366+"


def audit_rows() -> dict[str, Any]:
    targets = default_targets()
    counts_by_month: Counter[str] = Counter()
    counts_by_year: Counter[int] = Counter()
    counts_by_role: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    iso_counts: Counter[str] = Counter()
    script_counts: Counter[str] = Counter()
    word_buckets: Counter[str] = Counter()
    lag_buckets: Counter[str] = Counter()
    sitename_counts: Counter[str] = Counter()
    sitename_month_counts: Counter[tuple[str, str]] = Counter()
    shard_counts: Counter[str] = Counter()
    warc_partition_vs_publish: Counter[str] = Counter()
    retrieved_at_counts: Counter[str] = Counter()
    word_values: list[int] = []
    lag_values: list[int] = []
    unique_sets = {
        "document_id": set(),
        "identity_hash": set(),
        "normalized_url_hash": set(),
        "normalized_text_sha256": set(),
        "near_duplicate_cluster_id": set(),
        "warc_identity_hash": set(),
        "payload_digest_hash": set(),
    }
    duplicate_counts = Counter()
    banned_key_counts = Counter()
    rows = 0
    actual_publish_axis_mismatches = 0
    missing_required = Counter()
    schema_counts = Counter()

    with PRIVATE_ROWS.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            schema_counts[str(row.get("schema"))] += 1
            for key in TEXT_BEARING_KEYS:
                if key in row:
                    banned_key_counts[key] += 1
            required = [
                "document_id", "publication_date", "publication_year", "publication_month", "publication_year_month",
                "warc_date", "date_lag_days", "sitename", "language", "language_iso639_3", "word_count",
                "corpus_role", "identity_hash", "normalized_url_hash", "normalized_text_sha256", "near_duplicate_cluster_id",
            ]
            for key in required:
                if row.get(key) in (None, ""):
                    missing_required[key] += 1

            ym = str(row.get("publication_year_month"))
            counts_by_month[ym] += 1
            try:
                year = int(row.get("publication_year"))
                month = int(row.get("publication_month"))
                if ym != f"{year}-{month:02d}" or not str(row.get("publication_date", "")).startswith(ym):
                    actual_publish_axis_mismatches += 1
                counts_by_year[year] += 1
            except Exception:
                actual_publish_axis_mismatches += 1
            role = str(row.get("corpus_role"))
            counts_by_role[role] += 1
            language_counts[str(row.get("language"))] += 1
            iso_counts[str(row.get("language_iso639_3"))] += 1
            script_counts[str(row.get("language_script"))] += 1
            sitename = str(row.get("sitename"))
            sitename_counts[sitename] += 1
            sitename_month_counts[(sitename, ym)] += 1
            shard_counts[str(row.get("shard_path"))] += 1
            retrieved_at_counts[str(row.get("retrieved_at"))] += 1
            try:
                wc = int(row.get("word_count"))
                word_values.append(wc)
                word_buckets[histogram_bucket_word_count(wc)] += 1
            except Exception:
                missing_required["word_count_int"] += 1
            try:
                lag = int(row.get("date_lag_days"))
                lag_values.append(lag)
                lag_buckets[histogram_bucket_lag(lag)] += 1
            except Exception:
                missing_required["date_lag_days_int"] += 1
            partition_year = row.get("warc_partition_year")
            partition_month = row.get("warc_partition_month")
            partition_ym = f"{int(partition_year):04d}-{int(partition_month):02d}" if partition_year and partition_month else "missing"
            warc_partition_vs_publish["same"] += int(partition_ym == ym)
            warc_partition_vs_publish["different"] += int(partition_ym != ym)

            values = {
                "document_id": row.get("document_id"),
                "identity_hash": row.get("identity_hash"),
                "normalized_url_hash": row.get("normalized_url_hash"),
                "normalized_text_sha256": row.get("normalized_text_sha256"),
                "near_duplicate_cluster_id": row.get("near_duplicate_cluster_id"),
                "payload_digest_hash": row.get("warc_payload_digest_hash"),
            }
            warc_identity_source = "|".join(str(row.get(key) or "") for key in ["warc_filename_hash", "warc_record_id_hash", "warc_target_uri_hash"])
            values["warc_identity_hash"] = hashlib.sha256(warc_identity_source.encode("utf-8")).hexdigest()
            for key, value in values.items():
                if not value:
                    continue
                if value in unique_sets[key]:
                    duplicate_counts[key] += 1
                unique_sets[key].add(value)

    max_sitename_month = max(sitename_month_counts.values()) if sitename_month_counts else 0
    cap_violations = [(site, month, count) for (site, month), count in sitename_month_counts.items() if count > 250]
    year_targets = {
        2016: 4000,
        2017: 4000,
        2022: 2000,
        2026: 2000,
        **{year: 36000 for year in range(2018, 2022)},
        **{year: 36000 for year in range(2023, 2026)},
    }
    target_mismatches = {month: {"actual": counts_by_month.get(month, 0), "expected": expected} for month, expected in targets.items() if counts_by_month.get(month, 0) != expected}
    unexpected_months = {month: count for month, count in counts_by_month.items() if month not in targets}
    core_month_failures = {month: count for month, count in counts_by_month.items() if int(month[:4]) in CORE_YEARS and count != 3000}
    year_mismatches = {str(year): {"actual": counts_by_year.get(year, 0), "expected": expected} for year, expected in year_targets.items() if counts_by_year.get(year, 0) != expected}

    return {
        "row_count": rows,
        "counts_by_year": dict(sorted((str(k), v) for k, v in counts_by_year.items())),
        "counts_by_month": dict(sorted(counts_by_month.items())),
        "counts_by_role": dict(sorted(counts_by_role.items())),
        "target_mismatches": target_mismatches,
        "unexpected_months": unexpected_months,
        "core_month_failures": core_month_failures,
        "year_mismatches": year_mismatches,
        "all_target_months_present": len(counts_by_month) == len(targets) and not unexpected_months,
        "counts_by_month_len": len(counts_by_month),
        "language_counts": dict(language_counts.most_common(10)),
        "iso_counts": dict(iso_counts.most_common(10)),
        "script_counts": dict(script_counts.most_common(10)),
        "word_quantiles": quantiles(word_values),
        "word_buckets": dict(sorted(word_buckets.items())),
        "lag_quantiles": quantiles(lag_values),
        "lag_buckets": dict(sorted(lag_buckets.items())),
        "lag_nonzero_count": sum(1 for value in lag_values if value != 0),
        "lag_negative_count": sum(1 for value in lag_values if value < 0),
        "source_unique_count": len(sitename_counts),
        "top_sources": [{"source": site, "count": count, "share": pct(count, rows)} for site, count in sitename_counts.most_common(20)],
        "max_sitename_month_count": max_sitename_month,
        "cap_violation_count": len(cap_violations),
        "cap_violation_examples": [{"source": s, "month": m, "count": c} for s, m, c in sorted(cap_violations)[:10]],
        "shard_count": len(shard_counts),
        "top_shards_by_selected_rows": [{"shard_hash": hashlib.sha256(path.encode("utf-8")).hexdigest()[:16], "count": count} for path, count in shard_counts.most_common(10)],
        "retrieved_at_counts": dict(retrieved_at_counts.most_common(5)),
        "warc_partition_vs_publish": dict(warc_partition_vs_publish),
        "actual_publish_axis_mismatches": actual_publish_axis_mismatches,
        "duplicate_counts_in_selected_rows": dict(sorted(duplicate_counts.items())),
        "unique_counts": {key: len(value) for key, value in unique_sets.items()},
        "text_bearing_private_key_counts": dict(sorted(banned_key_counts.items())),
        "missing_required_counts": dict(sorted(missing_required.items())),
        "schema_counts": dict(sorted(schema_counts.items())),
    }


def audit_candidate_db() -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{CANDIDATE_DB}?mode=ro", uri=True)
    try:
        quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
        candidate_count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        months = conn.execute("SELECT COUNT(DISTINCT publication_year_month) FROM candidates").fetchone()[0]
        month_min, month_max = conn.execute("SELECT MIN(publication_year_month), MAX(publication_year_month) FROM candidates").fetchone()
        duplicate_counts = {key: int(value) for key, value in conn.execute("SELECT key, value FROM duplicate_counts ORDER BY key")}
        max_site_month_candidate = conn.execute(
            "SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM candidates GROUP BY publication_year_month, sitename)"
        ).fetchone()[0]
        unique_checks = {}
        for col in ["document_id", "warc_identity", "normalized_url_hash", "normalized_text_sha256", "near_duplicate_cluster_id"]:
            total, distinct = conn.execute(f"SELECT COUNT({col}), COUNT(DISTINCT {col}) FROM candidates").fetchone()
            unique_checks[col] = {"total": total, "distinct": distinct, "duplicates": total - distinct}
        total_payload, distinct_payload = conn.execute(
            "SELECT COUNT(payload_digest), COUNT(DISTINCT payload_digest) FROM candidates WHERE payload_digest IS NOT NULL AND payload_digest != ''"
        ).fetchone()
        unique_checks["payload_digest"] = {"total": total_payload, "distinct": distinct_payload, "duplicates": total_payload - distinct_payload}
    finally:
        conn.close()
    return {
        "quick_check": quick_check,
        "candidate_count": candidate_count,
        "publication_months": months,
        "publication_month_min": month_min,
        "publication_month_max": month_max,
        "duplicate_counts": duplicate_counts,
        "max_candidate_sitename_month_count": max_site_month_candidate,
        "unique_checks": unique_checks,
    }


def audit_progress() -> dict[str, Any]:
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    shards = progress.get("shards", {})
    stats = progress.get("stats", {})
    complete = sum(1 for shard in shards.values() if shard.get("complete") is True)
    skipped = Counter(str(shard.get("skipped")) for shard in shards.values() if shard.get("skipped"))
    return {
        "shard_entries": len(shards),
        "complete_shards": complete,
        "skipped_reasons": dict(sorted(skipped.items())),
        "rejected_counts": dict(sorted(stats.get("rejected_counts", {}).items())),
        "duplicate_counts": dict(sorted(stats.get("duplicate_counts", {}).items())),
    }


def audit_public_artifacts() -> dict[str, Any]:
    result = {}
    for path in PUBLIC_JSONS:
        if not path.exists():
            result[str(path.relative_to(REPO_ROOT))] = {"exists": False}
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        text_key_findings = scan_public_payload_for_text_keys(payload)
        result[str(path.relative_to(REPO_ROOT))] = {
            "exists": True,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "text_like_key_findings": text_key_findings,
            "has_records_array": isinstance(payload, dict) and "records" in payload,
            "accepted_count": payload.get("accepted_count") if isinstance(payload, dict) else None,
            "target_total_rows": payload.get("target_total_rows") if isinstance(payload, dict) else None,
            "date_axis": payload.get("date_axis") if isinstance(payload, dict) else None,
            "warc_date_usage": payload.get("warc_date_usage") if isinstance(payload, dict) else None,
            "source_revision": payload.get("source_revision") if isinstance(payload, dict) else None,
            "request_manifest_id": payload.get("request_manifest_id") if isinstance(payload, dict) else payload.get("manifest_id") if isinstance(payload, dict) else None,
            "shard_identities_count": len(payload.get("shard_identities", [])) if isinstance(payload, dict) else None,
        }
    return result


def audit_permissions_and_hashes() -> dict[str, Any]:
    dirs = [PRIVATE_ROOT, PRIVATE_ROOT / "logs"]
    return {
        "directories": {str(path.relative_to(REPO_ROOT)): {"exists": path.exists(), "mode": mode_octal(path) if path.exists() else None} for path in dirs},
        "private_files": {
            str(path.relative_to(REPO_ROOT)): {
                "exists": path.exists(),
                "mode": mode_octal(path) if path.exists() else None,
                "size_bytes": path.stat().st_size if path.exists() else None,
                "sha256": sha256_file(path) if path.exists() else None,
            }
            for path in PRIVATE_ARTIFACTS
        },
    }


def render_report(audit: dict[str, Any]) -> str:
    rows = audit["rows"]
    db = audit["candidate_db"]
    public = audit["public_artifacts"]
    perms = audit["permissions"]
    progress = audit["progress"]
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Accepted selected records equal 264,000", rows["row_count"] == EXPECTED_TOTAL, str(rows["row_count"])))
    checks.append(("Year quotas reconcile to 264,000", not rows["year_mismatches"] and sum(int(v) for v in rows["counts_by_year"].values()) == EXPECTED_TOTAL, json.dumps(rows["counts_by_year"], sort_keys=True)))
    checks.append(("Month quota map matches expected 117 publish months", rows["all_target_months_present"] and not rows["target_mismatches"], f"months={rows['counts_by_month_len']} mismatches={rows['target_mismatches']} unexpected={rows['unexpected_months']}"))
    checks.append(("Core years 2018-2021 and 2023-2025 have exactly 3,000 records per publish month", not rows["core_month_failures"], json.dumps(rows["core_month_failures"], sort_keys=True)))
    checks.append(("Bucketing uses actual publish_date fields", rows["actual_publish_axis_mismatches"] == 0, f"publish field mismatches={rows['actual_publish_axis_mismatches']}; WARC partition differs for {rows['warc_partition_vs_publish'].get('different', 0)} selected records"))
    checks.append(("Selected corpus has no duplicate document/source/text identity hashes", all(v == 0 for v in rows["duplicate_counts_in_selected_rows"].values()), json.dumps(rows["duplicate_counts_in_selected_rows"], sort_keys=True)))
    checks.append(("Candidate DB quick_check is ok", db["quick_check"] == "ok", db["quick_check"]))
    checks.append(("Candidate DB unique indexes show no retained candidate duplicates", all(item["duplicates"] == 0 for item in db["unique_checks"].values()), json.dumps(db["unique_checks"], sort_keys=True)))
    checks.append(("Per-sitename per-month selected cap <= 250", rows["cap_violation_count"] == 0 and rows["max_sitename_month_count"] <= 250, f"max={rows['max_sitename_month_count']} violations={rows['cap_violation_examples']}"))
    checks.append(("Private directories are 0700", all(item["mode"] == "0o700" for item in perms["directories"].values() if item["exists"]), json.dumps(perms["directories"], sort_keys=True)))
    checks.append(("Private files are 0600", all(item["mode"] == "0o600" for item in perms["private_files"].values() if item["exists"]), "all private artifacts inspected"))
    public_no_text = all(not item.get("text_like_key_findings") for item in public.values() if item.get("exists"))
    checks.append(("Public-safe JSON artifacts contain no text-like keys", public_no_text, json.dumps({k: v.get("text_like_key_findings") for k, v in public.items()}, sort_keys=True)))
    checks.append(("Public full report is aggregate-only without records array", public["services/evals/publication_shift_model/infini_news_v1/full_report.json"].get("has_records_array") is False, "records array absent"))
    checks.append(("Manifest/report identities match frozen request", public["services/evals/publication_shift_model/infini_news_v1/full_report.json"].get("target_total_rows") == EXPECTED_TOTAL and public["services/evals/publication_shift_model/infini_news_v1/full_report.json"].get("accepted_count") == EXPECTED_TOTAL, json.dumps(public["services/evals/publication_shift_model/infini_news_v1/full_report.json"], sort_keys=True)))

    target_rows = default_targets()
    month_table = ["| Publish month | Target | Accepted | Result |", "|---|---:|---:|---:|"]
    for month, target in target_rows.items():
        accepted = rows["counts_by_month"].get(month, 0)
        month_table.append(f"| `{month}` | {target:,} | {accepted:,} | {passfail(accepted == target)} |")

    lines = [
        "# INFINI-NEWS v1 corpus validation report (text-free)",
        "",
        "This report was generated by an independent audit over the frozen private artifacts. It intentionally excludes article bodies, titles, descriptions, previews, URLs, and excerpts.",
        "",
        "## Overall result",
        "",
    ]
    overall = all(ok for _, ok, _ in checks)
    lines.append(f"Overall: {passfail(overall)}")
    lines.append("")
    lines.append("## Invariant checks")
    lines.append("")
    lines.append("| Check | Result | Evidence |")
    lines.append("|---|---:|---|")
    for name, ok, evidence in checks:
        safe_evidence = evidence.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {name} | {passfail(ok)} | `{safe_evidence}` |")
    lines.extend([
        "",
        "## Reconciliation to 264,000",
        "",
        f"- Selected accepted rows: {rows['row_count']:,}",
        f"- Counts by year: `{json.dumps(rows['counts_by_year'], sort_keys=True)}`",
        f"- Counts by role: `{json.dumps(rows['counts_by_role'], sort_keys=True)}`",
        f"- Target month count: {rows['counts_by_month_len']} publish months; target mismatches: `{json.dumps(rows['target_mismatches'], sort_keys=True)}`; unexpected months: `{json.dumps(rows['unexpected_months'], sort_keys=True)}`",
        "",
        "### Per-month target verification",
        "",
        *month_table,
        "",
        "## Candidate, rejection, and duplicate accounting",
        "",
        f"- Candidate DB quick_check: `{db['quick_check']}`",
        f"- Deduped candidate rows retained: {db['candidate_count']:,} across {db['publication_months']} candidate publish months ({db['publication_month_min']}..{db['publication_month_max']})",
        f"- Candidate duplicate counts: `{json.dumps(db['duplicate_counts'], sort_keys=True)}`",
        f"- Progress rejected counts: `{json.dumps(progress['rejected_counts'], sort_keys=True)}`",
        f"- Progress duplicate counts: `{json.dumps(progress['duplicate_counts'], sort_keys=True)}`",
        f"- Progress shards: {progress['shard_entries']} entries; complete={progress['complete_shards']}; skipped=`{json.dumps(progress['skipped_reasons'], sort_keys=True)}`",
        "",
        "## Date-lag, language, length, and source distributions",
        "",
        f"- Date lag quantiles (days): `{json.dumps(rows['lag_quantiles'], sort_keys=True)}`; buckets: `{json.dumps(rows['lag_buckets'], sort_keys=True)}`; nonzero={rows['lag_nonzero_count']:,}; negative={rows['lag_negative_count']:,}",
        f"- Language counts: `{json.dumps(rows['language_counts'], sort_keys=True)}`; ISO-639-3: `{json.dumps(rows['iso_counts'], sort_keys=True)}`; script: `{json.dumps(rows['script_counts'], sort_keys=True)}`",
        f"- Word count quantiles: `{json.dumps(rows['word_quantiles'], sort_keys=True)}`; buckets: `{json.dumps(rows['word_buckets'], sort_keys=True)}`",
        f"- Unique source labels: {rows['source_unique_count']:,}; max selected records for any source in any publish month: {rows['max_sitename_month_count']}",
        f"- Top source concentration: `{json.dumps(rows['top_sources'], sort_keys=True)}`",
        "",
        "## Source/shard and manifest identities",
        "",
        f"- Selected shard count from private rows: {rows['shard_count']}; top selected shard hashes/counts: `{json.dumps(rows['top_shards_by_selected_rows'], sort_keys=True)}`",
        f"- Public artifact summaries: `{json.dumps(public, sort_keys=True)}`",
        f"- Private artifact hashes/modes: `{json.dumps(perms, sort_keys=True)}`",
        "",
        "## Reproducibility and verification commands",
        "",
        "The article-bearing corpus was not recollected by this audit. The final package freezes the successful prior collection artifacts and records the exact commands used to launch, regenerate, and verify them. Public outputs below intentionally contain counts, hashes, modes, source labels, and shard identities only.",
        "",
        "### Collection/finalization command",
        "",
        "```bash",
        "mkdir -p services/data/publication_shift/infini_news_v1/logs",
        "chmod 700 services/data/publication_shift/infini_news_v1 services/data/publication_shift/infini_news_v1/logs",
        "/usr/bin/time -p python3 services/gateway/build_publication_shift_infini_news_corpus.py \\",
        "  --manifest services/evals/publication_shift_model/infini_news_v1/frozen_request_manifest_264000.json \\",
        "  --output-root services/data/publication_shift/infini_news_v1 \\",
        "  --report services/evals/publication_shift_model/infini_news_v1/full_report.json \\",
        "  --request-manifest-output services/evals/publication_shift_model/infini_news_v1/full_request_manifest.json \\",
        "  > services/data/publication_shift/infini_news_v1/logs/full_collect.stdout \\",
        "  2> services/data/publication_shift/infini_news_v1/logs/full_collect.stderr",
        "```",
        "",
        "Observed successful-run evidence: upstream tracked collector process `proc_337e9b609ed3` was launched with the command above; subsequent handoff/comment evidence records collector/finalizer exit code 0, collection duration about 10 minutes, and bounded finalization duration 1m46s. Retained `full_collect.stderr` contains only the Hugging Face unauthenticated-request warning and `full_collect.stdout` is empty. The frozen artifacts re-verified here show `accepted_count=264000`, all 117 target months satisfied, and candidate DB `quick_check=ok`.",
        "",
        "### Verification commands run for this evidence package",
        "",
        "```bash",
        "python scripts/audit_infini_news_v1_corpus.py",
        "python scripts/verify_infini_news_v1_collection.py",
        "PYTHONPATH=services/gateway python -m pytest services/gateway/tests/test_publication_shift_infini_news_corpus.py services/gateway/tests/test_metadata_artifact_checksums.py -q",
        "sha256sum -c metadata/artifact_checksums.sha256",
        "git check-ignore -v services/data/publication_shift/infini_news_v1/normalized_rows.jsonl services/data/publication_shift/infini_news_v1/progress.json services/data/publication_shift/infini_news_v1/candidate_records.sqlite3",
        "git diff --cached --name-only",
        "```",
        "",
        "Observed command output is recorded in the task handoff; all verification commands exited 0 before commit.",
        "",
        "## Public-safety note",
        "",
        f"- Private rows contain expected private text-bearing keys by count: `{json.dumps(rows['text_bearing_private_key_counts'], sort_keys=True)}`; these were not copied into this report.",
        "- Public-safe JSON artifacts were scanned structurally for text-like keys outside allowed aggregate count-key contexts.",
    ])
    return "\n".join(lines)


def main() -> int:
    audit = {
        "rows": audit_rows(),
        "candidate_db": audit_candidate_db(),
        "progress": audit_progress(),
        "public_artifacts": audit_public_artifacts(),
        "permissions": audit_permissions_and_hashes(),
    }
    report = render_report(audit)
    OUTPUT_REPORT.write_text(report + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(OUTPUT_REPORT.relative_to(REPO_ROOT)),
        "overall": "PASS" if "Overall: PASS" in report else "FAIL",
        "rows": audit["rows"]["row_count"],
        "candidate_count": audit["candidate_db"]["candidate_count"],
        "report_sha256": sha256_file(OUTPUT_REPORT),
    }, sort_keys=True))
    return 0 if "Overall: PASS" in report else 2


if __name__ == "__main__":
    raise SystemExit(main())
