#!/usr/bin/env python3
"""Build a local INFINI-NEWS corpus for the publication-shift model.

Article bodies are research-only local inputs. Raw and normalized text written by
this script stays below ignored services/data/publication_shift/infini_news_v1
with restrictive permissions. Public reports under services/evals contain only
IDs, hashes, counts, metadata, and the required construct caveat.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import stat
import sqlite3
import tempfile
import time
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from huggingface_hub import HfApi, hf_hub_download
import pyarrow.parquet as pq

REPO_ID = "ruggsea/infini-news-corpus"
FROZEN_REVISION = "5b78199b86a838a5634b2d3267d72b98b8f71721"
SCHEMA = "publication_shift.infini_news_corpus.v1"
PUBLIC_SCHEMA = "publication_shift.infini_news_public_manifest.v1"
REQUEST_SCHEMA = "publication_shift.infini_news_request_manifest.v1"
PRIVATE_ROOT_MARKER = Path("services/data/publication_shift/infini_news_v1")
PUBLIC_SAFE_ROOT = Path("services/evals/publication_shift_model/infini_news_v1")
CAVEAT = "This score does not establish AI authorship."
SOURCE_RIGHTS_STATUS = "research_only_no_public_text_no_production_use"
DEFAULT_SEED = 20260712
DEFAULT_PER_SITENAME_MONTH_CAP = 250
PILOT_TARGET_MONTHS = ["2016-08", "2018-01", "2022-01", "2025-01", "2026-01", "2026-02", "2026-03", "2026-04"]
PARQUET_COLUMNS = [
    "url",
    "url_hostname",
    "warc_filename",
    "warc_record_id",
    "warc_target_uri",
    "warc_date",
    "warc_payload_digest",
    "http_status",
    "publish_date",
    "author",
    "sitename",
    "description",
    "text",
    "text_xxhash64",
    "language",
    "language_iso639_3",
    "language_script",
    "language_score",
    "language_short",
    "language_short_score",
    "month",
    "year",
    "iptc_topic",
    "lang",
    "lang_score",
]
PUBLIC_SAFE_KEYS = {
    "document_id",
    "source_revision",
    "source_repo_id",
    "shard_path",
    "shard_sha256",
    "row_index",
    "url_hash",
    "normalized_url_hash",
    "sitename",
    "url_hostname",
    "publication_date",
    "publication_year",
    "publication_month",
    "publication_year_month",
    "warc_date",
    "date_lag_days",
    "warc_partition_year",
    "warc_partition_month",
    "warc_filename_hash",
    "warc_record_id_hash",
    "warc_target_uri_hash",
    "warc_payload_digest_hash",
    "identity_hash",
    "normalized_text_sha256",
    "text_xxhash64",
    "near_duplicate_cluster_id",
    "author_hash",
    "topic",
    "language",
    "language_iso639_3",
    "language_script",
    "language_score",
    "lang",
    "lang_score",
    "explicit_english_validated",
    "word_count",
    "corpus_role",
    "rights_status",
    "retrieved_at",
}
PUBLIC_BANNED_KEYS = {"text", "normalized_text", "title", "description", "preview", "body", "content"}
PILOT_MONTH_SHARD_OVERRIDES = {
    # Small pinned shards keep the real pilot bounded while still touching all
    # requested eras. Other runs discover shards from the Hub manifest.
    "2016-08": ["data/year=2016/month=08/part-f48ce515d0992bd9.parquet"],
    "2018-01": ["data/year=2018/month=01/part-02a828a0473a594d.parquet"],
    "2022-01": ["data/year=2022/month=01/part-ab06ad8d8688174e.parquet"],
    "2025-01": ["data/year=2025/month=01/part-8cd18dc53a0246c9.parquet"],
    "2026-01": ["data/year=2026/month=01/part-9645bf0af99f02ce.parquet"],
    "2026-02": ["data/year=2026/month=02/part-a01e232349244987.parquet"],
    "2026-03": ["data/year=2026/month=03/part-56ae8b85ab32d3fb.parquet"],
    "2026-04": ["data/year=2026/month=04/part-d42673c58661012c.parquet"],
}


class InfiniNewsError(RuntimeError):
    pass


class InfiniNewsSchemaError(InfiniNewsError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_year_month(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError(f"invalid year-month: {value}")
    year_s, month_s = value.split("-", 1)
    year = int(year_s)
    month = int(month_s)
    if month < 1 or month > 12:
        raise ValueError(f"invalid month: {value}")
    return year, month


def assign_corpus_role(year: int, month: int) -> str | None:
    if year == 2016 and 8 <= month <= 12:
        return "historical_placebo"
    if year == 2017:
        return "historical_placebo"
    if 2018 <= year <= 2021:
        return "pre_llm_core"
    if year == 2022:
        return "transition_2022"
    if 2023 <= year <= 2025:
        return "current_core"
    if year == 2026 and 1 <= month <= 4:
        return "forward_2026"
    return None


def default_targets() -> dict[str, int]:
    targets: dict[str, int] = {}
    for month in range(8, 13):
        targets[f"2016-{month:02d}"] = 800
    # 4,000 over 12 months: eight months get 333 and four get 334.
    for month in range(1, 13):
        targets[f"2017-{month:02d}"] = 334 if month <= 4 else 333
    for year in list(range(2018, 2022)) + list(range(2023, 2026)):
        for month in range(1, 13):
            targets[f"{year}-{month:02d}"] = 3000
    # 2,000 over 12 months: eight months get 167 and four get 166.
    for month in range(1, 13):
        targets[f"2022-{month:02d}"] = 167 if month <= 8 else 166
    for month in range(1, 5):
        targets[f"2026-{month:02d}"] = 500
    return dict(sorted(targets.items()))


def pilot_targets(rows_per_month: int = 2) -> dict[str, int]:
    return {month: int(rows_per_month) for month in PILOT_TARGET_MONTHS}


def default_manifest(*, pilot: bool = False, rows_per_pilot_month: int = 2) -> dict[str, Any]:
    targets = pilot_targets(rows_per_pilot_month) if pilot else default_targets()
    manifest = {
        "schema": REQUEST_SCHEMA,
        "manifest_id": "infini_news_pilot_v1" if pilot else "infini_news_v1_264000",
        "created_at": "2026-07-12T00:00:00Z",
        "source_repo_id": REPO_ID,
        "source_revision": FROZEN_REVISION,
        "source_revision_url": f"https://huggingface.co/datasets/{REPO_ID}/tree/{FROZEN_REVISION}",
        "source_rights_status": SOURCE_RIGHTS_STATUS,
        "target_total_rows": sum(targets.values()),
        "targets_by_month": targets,
        "sample_seed": DEFAULT_SEED,
        "per_sitename_month_cap": DEFAULT_PER_SITENAME_MONTH_CAP if not pilot else 3,
        "minimum_words": 150,
        "date_axis": "publish_date_only",
        "warc_partition_usage": "candidate_shard_discovery_only_not_label_or_quota",
        "public_artifact_policy": "no_text_no_titles_no_previews_hashes_counts_metadata_only",
        "caveat": CAVEAT,
    }
    if pilot:
        manifest["preferred_shards_by_month"] = PILOT_MONTH_SHARD_OVERRIDES
    return manifest


def load_manifest(path: Path | None, *, pilot: bool, rows_per_pilot_month: int) -> dict[str, Any]:
    if path is not None and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_manifest(pilot=pilot, rows_per_pilot_month=rows_per_pilot_month)


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise InfiniNewsSchemaError("source identity url hostname is missing")
    port = f":{parsed.port}" if parsed.port else ""
    path = re.sub(r"/+$", "", parsed.path or "/")
    query_pairs = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
            continue
        query_pairs.append((key, value))
    query = urllib.parse.urlencode(sorted(query_pairs), doseq=True)
    return urllib.parse.urlunsplit((scheme, hostname + port, path, query, ""))


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b\S+\b", text))


def parse_publish_date(value: Any) -> dt.date:
    if not isinstance(value, str) or not value.strip():
        raise InfiniNewsSchemaError("publish_date is missing")
    value = value.strip()
    candidates = [value]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", value):
        candidates.append(value[:10])
    for candidate in candidates:
        try:
            return dt.date.fromisoformat(candidate[:10])
        except ValueError:
            pass
    raise InfiniNewsSchemaError("publish_date is invalid")


def parse_warc_date(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise InfiniNewsSchemaError("warc_date is missing or invalid")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0)


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def shard_partition(path: str) -> tuple[int | None, int | None]:
    match = re.search(r"year=(\d{4})/month=(\d{2})", path)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def validate_explicit_english(row: dict[str, Any]) -> tuple[str, str, str | None, float | None, float | None]:
    language = row.get("language")
    iso3 = row.get("language_iso639_3")
    lang = row.get("lang")
    language_script = row.get("language_script")
    language_score = row.get("language_score")
    lang_score = row.get("lang_score")
    short = row.get("language_short")
    short_score = row.get("language_short_score")
    explicit = [value for value in [iso3, lang] if value]
    if language:
        explicit.append(str(language).split("_", 1)[0])
    if short:
        explicit.append(str(short))
    normalized = {str(value).strip().lower() for value in explicit if str(value).strip()}
    english_codes = {"eng", "en"}
    if not normalized or not normalized <= english_codes:
        raise InfiniNewsSchemaError("language metadata is not explicit non-conflicting English")
    if language_script and str(language_script) != "Latn":
        raise InfiniNewsSchemaError("language script is not Latin")
    for score_name, score in [("language_score", language_score), ("lang_score", lang_score), ("language_short_score", short_score)]:
        if score is not None and float(score) < 0.5:
            raise InfiniNewsSchemaError(f"{score_name} is too low for English validation")
    return str(language or ""), str(iso3 or lang or "eng"), str(language_script) if language_script else None, float(language_score) if language_score is not None else None, float(lang_score) if lang_score is not None else None


def deterministic_near_duplicate_cluster(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < 5:
        source = " ".join(words)
    else:
        shingles = {" ".join(words[idx : idx + 5]) for idx in range(len(words) - 4)}
        ranked = sorted(stable_hash(shingle, 32) for shingle in shingles)[:24]
        source = "|".join(ranked)
    return "ndc_" + stable_hash(source, 20)


def require_str(row: dict[str, Any], key: str, reason: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InfiniNewsSchemaError(reason)
    return value.strip()


def normalize_row(
    row: dict[str, Any],
    *,
    shard_path: str,
    shard_sha256: str,
    row_index: int,
    retrieved_at: str,
) -> dict[str, Any]:
    publish_date = parse_publish_date(row.get("publish_date"))
    role = assign_corpus_role(publish_date.year, publish_date.month)
    if role is None:
        raise InfiniNewsSchemaError("publish_date is outside configured corpus windows")
    warc_date = parse_warc_date(row.get("warc_date"))
    # Quarantine impossible future publication dates beyond a small metadata skew.
    if publish_date > (warc_date.date() + dt.timedelta(days=7)):
        raise InfiniNewsSchemaError("publish_date is impossibly after warc_date")
    url = require_str(row, "url", "source identity url is missing")
    warc_filename = require_str(row, "warc_filename", "source identity warc_filename is missing")
    warc_record_id = require_str(row, "warc_record_id", "source identity warc_record_id is missing")
    warc_target_uri = require_str(row, "warc_target_uri", "source identity warc_target_uri is missing")
    payload_digest = str(row.get("warc_payload_digest") or "").strip()
    text = require_str(row, "text", "text is missing")
    normalized_text = normalize_text(text)
    words = word_count(normalized_text)
    if words < 150:
        raise InfiniNewsSchemaError("text has fewer than 150 words")
    language, iso3, script, language_score, lang_score = validate_explicit_english(row)
    normalized = normalize_url(url)
    hostname = str(row.get("url_hostname") or urllib.parse.urlsplit(normalized).hostname or "").lower()
    if not hostname:
        raise InfiniNewsSchemaError("source identity hostname is missing")
    sitename = str(row.get("sitename") or hostname).strip()
    if not sitename:
        raise InfiniNewsSchemaError("sitename is missing")
    partition_year, partition_month = shard_partition(shard_path)
    identity_source = "|".join([FROZEN_REVISION, shard_path, warc_filename, warc_record_id, warc_target_uri, str(row_index)])
    normalized_text_hash = sha256_text(normalized_text)
    author = str(row.get("author") or "").strip()
    return {
        "schema": SCHEMA,
        "document_id": "infini_news_" + stable_hash(identity_source, 24),
        "source_repo_id": REPO_ID,
        "source_revision": FROZEN_REVISION,
        "shard_path": shard_path,
        "shard_sha256": shard_sha256,
        "row_index": row_index,
        "url": url,
        "normalized_url": normalized,
        "url_hash": sha256_text(url.strip()),
        "normalized_url_hash": sha256_text(normalized),
        "url_hostname": hostname,
        "sitename": sitename,
        "warc_filename": warc_filename,
        "warc_record_id": warc_record_id,
        "warc_target_uri": warc_target_uri,
        "warc_payload_digest": payload_digest,
        "warc_filename_hash": sha256_text(warc_filename),
        "warc_record_id_hash": sha256_text(warc_record_id),
        "warc_target_uri_hash": sha256_text(warc_target_uri),
        "warc_payload_digest_hash": sha256_text(payload_digest) if payload_digest else None,
        "identity_hash": sha256_text(identity_source),
        "publication_date": publish_date.isoformat(),
        "publication_year": publish_date.year,
        "publication_month": publish_date.month,
        "publication_year_month": f"{publish_date.year}-{publish_date.month:02d}",
        "warc_date": iso_z(warc_date),
        "date_lag_days": (warc_date.date() - publish_date).days,
        "warc_partition_year": partition_year,
        "warc_partition_month": partition_month,
        "language": language,
        "language_iso639_3": iso3,
        "language_script": script,
        "language_score": language_score,
        "lang": str(row.get("lang") or iso3),
        "lang_score": lang_score,
        "explicit_english_validated": True,
        "author_hash": sha256_text(author.lower()) if author else None,
        "topic": row.get("iptc_topic"),
        "original_text": text,
        "normalized_text": normalized_text,
        "normalized_text_sha256": normalized_text_hash,
        "text_xxhash64": str(row.get("text_xxhash64") or ""),
        "near_duplicate_cluster_id": deterministic_near_duplicate_cluster(normalized_text),
        "word_count": words,
        "corpus_role": role,
        "retrieved_at": retrieved_at,
        "rights_status": SOURCE_RIGHTS_STATUS,
    }


def rejection_code(message: str) -> str:
    lowered = message.lower()
    if "language" in lowered:
        return "non_english_or_conflicting_language"
    if "150 words" in lowered:
        return "too_short"
    if "publish_date" in lowered:
        return "invalid_publish_date"
    if "warc_date" in lowered:
        return "invalid_warc_date"
    if "source identity" in lowered:
        return "invalid_source_identity"
    return "schema_rejected"


def dedupe_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen_warc: set[tuple[str, str, str]] = set()
    seen_payload: set[str] = set()
    seen_url: set[str] = set()
    seen_text: set[str] = set()
    seen_cluster: set[str] = set()
    counts = Counter()
    kept = []
    for record in sorted(records, key=lambda row: (row["publication_date"], row["document_id"])):
        duplicate_reasons: list[str] = []
        warc_identity = (record.get("warc_filename", ""), record.get("warc_record_id", ""), record.get("warc_target_uri", ""))
        if warc_identity in seen_warc:
            duplicate_reasons.append("warc_identity_duplicates")
        payload = record.get("warc_payload_digest")
        if payload and payload in seen_payload:
            duplicate_reasons.append("payload_digest_duplicates")
        if record["normalized_url_hash"] in seen_url:
            duplicate_reasons.append("url_duplicates")
        if record["normalized_text_sha256"] in seen_text:
            duplicate_reasons.append("text_hash_duplicates")
        if record["near_duplicate_cluster_id"] in seen_cluster:
            duplicate_reasons.append("near_duplicate_duplicates")
        if duplicate_reasons:
            counts["duplicate_count"] += 1
            counts.update(duplicate_reasons)
            continue
        kept.append(record)
        seen_warc.add(warc_identity)
        if payload:
            seen_payload.add(payload)
        seen_url.add(record["normalized_url_hash"])
        seen_text.add(record["normalized_text_sha256"])
        seen_cluster.add(record["near_duplicate_cluster_id"])
    counts["input_count"] = len(records)
    counts["kept_count"] = len(kept)
    counts.setdefault("duplicate_count", len(records) - len(kept))
    return kept, dict(sorted(counts.items()))


def connect_private_candidate_db(path: Path) -> sqlite3.Connection:
    ensure_private_path(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            document_id TEXT PRIMARY KEY,
            publication_year_month TEXT NOT NULL,
            publication_date TEXT NOT NULL,
            sitename TEXT NOT NULL,
            warc_identity TEXT NOT NULL UNIQUE,
            payload_digest TEXT,
            normalized_url_hash TEXT NOT NULL UNIQUE,
            normalized_text_sha256 TEXT NOT NULL UNIQUE,
            near_duplicate_cluster_id TEXT NOT NULL UNIQUE,
            record_json TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_payload
            ON candidates(payload_digest) WHERE payload_digest IS NOT NULL AND payload_digest != '';
        CREATE INDEX IF NOT EXISTS idx_candidates_month ON candidates(publication_year_month);
        CREATE TABLE IF NOT EXISTS duplicate_counts (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
        """
    )
    os.chmod(path, 0o600)
    return conn


def increment_db_count(conn: sqlite3.Connection, key: str, amount: int = 1) -> None:
    conn.execute(
        """
        INSERT INTO duplicate_counts(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = value + excluded.value
        """,
        (key, amount),
    )


def duplicate_counts_from_db(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {key: int(value) for key, value in conn.execute("SELECT key, value FROM duplicate_counts")}
    counts["input_count"] = counts.get("input_count", 0)
    counts["kept_count"] = int(conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0])
    counts.setdefault("duplicate_count", counts["input_count"] - counts["kept_count"])
    return dict(sorted(counts.items()))


def add_candidate_record(conn: sqlite3.Connection, record: dict[str, Any]) -> bool:
    increment_db_count(conn, "input_count")
    warc_identity = "|".join([record.get("warc_filename", ""), record.get("warc_record_id", ""), record.get("warc_target_uri", "")])
    duplicate_reasons: list[str] = []
    checks = [
        ("warc_identity_duplicates", "warc_identity", warc_identity),
        ("url_duplicates", "normalized_url_hash", record["normalized_url_hash"]),
        ("text_hash_duplicates", "normalized_text_sha256", record["normalized_text_sha256"]),
        ("near_duplicate_duplicates", "near_duplicate_cluster_id", record["near_duplicate_cluster_id"]),
    ]
    payload = record.get("warc_payload_digest")
    if payload:
        checks.append(("payload_digest_duplicates", "payload_digest", payload))
    for reason, column, value in checks:
        if conn.execute(f"SELECT 1 FROM candidates WHERE {column} = ? LIMIT 1", (value,)).fetchone():
            duplicate_reasons.append(reason)
    if duplicate_reasons:
        increment_db_count(conn, "duplicate_count")
        for reason in duplicate_reasons:
            increment_db_count(conn, reason)
        return False
    conn.execute(
        """
        INSERT INTO candidates(
            document_id, publication_year_month, publication_date, sitename,
            warc_identity, payload_digest, normalized_url_hash,
            normalized_text_sha256, near_duplicate_cluster_id, record_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["document_id"],
            record["publication_year_month"],
            record["publication_date"],
            str(record.get("sitename") or ""),
            warc_identity,
            payload or None,
            record["normalized_url_hash"],
            record["normalized_text_sha256"],
            record["near_duplicate_cluster_id"],
            json.dumps(record, sort_keys=True, ensure_ascii=False),
        ),
    )
    return True


def seed_candidate_db_from_jsonl(conn: sqlite3.Connection, path: Path) -> None:
    if not path.exists() or conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]:
        return
    for record in read_jsonl(path):
        add_candidate_record(conn, record)
    conn.commit()


def select_month_rows_from_db(
    conn: sqlite3.Connection,
    *,
    month: str,
    target: int,
    seed: int,
    per_sitename_cap: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = conn.execute(
        """
        SELECT document_id, sitename
        FROM candidates
        WHERE publication_year_month = ?
        ORDER BY document_id
        """,
        (month,),
    )
    selected_ids: list[str] = []
    site_counts = Counter()
    rejected = Counter()
    for document_id, sitename in sorted(
        rows,
        key=lambda item: (stable_hash(f"{seed}|{month}|{item[0]}", 32), item[0]),
    ):
        if site_counts[str(sitename or "")] >= per_sitename_cap:
            rejected["per_sitename_cap"] += 1
            continue
        selected_ids.append(str(document_id))
        site_counts[str(sitename or "")] += 1
        if len(selected_ids) >= target:
            break
    if len(selected_ids) < target:
        rejected["month_quota_shortfall"] = target - len(selected_ids)
    selected = []
    for document_id in selected_ids:
        row = conn.execute("SELECT record_json FROM candidates WHERE document_id = ?", (document_id,)).fetchone()
        if row:
            selected.append(json.loads(row[0]))
    return sorted(selected, key=lambda row: (row["publication_date"], row["document_id"])), dict(sorted(rejected.items()))


def month_quota_satisfied_in_db(
    conn: sqlite3.Connection,
    *,
    month: str,
    target: int,
    seed: int,
    per_sitename_cap: int,
) -> bool:
    """Return whether stored candidates can already fill a month quota."""
    del seed  # Quota sufficiency does not depend on deterministic row ordering.
    capped_total = 0
    for (site_count,) in conn.execute(
        """
        SELECT COUNT(*)
        FROM candidates
        WHERE publication_year_month = ?
        GROUP BY sitename
        """,
        (month,),
    ):
        capped_total += min(int(site_count), per_sitename_cap)
        if capped_total >= target:
            return True
    return False


def select_month_rows(
    rows: list[dict[str, Any]],
    *,
    month: str,
    target: int,
    seed: int,
    per_sitename_cap: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    candidates = [row for row in rows if row.get("publication_year_month") == month]
    def keyed(row: dict[str, Any]) -> tuple[str, str]:
        return (stable_hash(f"{seed}|{month}|{row['document_id']}", 32), row["document_id"])
    selected = []
    site_counts = Counter()
    rejected = Counter()
    for row in sorted(candidates, key=keyed):
        sitename = str(row.get("sitename") or "")
        if site_counts[sitename] >= per_sitename_cap:
            rejected["per_sitename_cap"] += 1
            continue
        selected.append(row)
        site_counts[sitename] += 1
        if len(selected) >= target:
            break
    if len(selected) < target:
        rejected["month_quota_shortfall"] = target - len(selected)
    return sorted(selected, key=lambda row: (row["publication_date"], row["document_id"])), dict(sorted(rejected.items()))


def ensure_private_path(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = path
    while root.name != PRIVATE_ROOT_MARKER.name and root.parent != root:
        root = root.parent
    current = path.parent
    while True:
        try:
            os.chmod(current, stat.S_IRWXU)
        except FileNotFoundError:
            pass
        if current == root or current.parent == current:
            break
        current = current.parent


def write_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    ensure_private_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)


def append_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    ensure_private_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_private_path(path)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"shards": {}, "stats": {"rejected_counts": {}, "duplicate_counts": {}}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("shards", {})
    payload.setdefault("stats", {})
    payload["stats"].setdefault("rejected_counts", {})
    payload["stats"].setdefault("duplicate_counts", {})
    return payload


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in sorted(PUBLIC_SAFE_KEYS) if key in record}


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key)) for row in rows).items()))


def date_lag_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    lags = sorted(int(row["date_lag_days"]) for row in records)
    divergences = [row for row in records if int(row["date_lag_days"]) != 0]
    return {
        "min_days": lags[0] if lags else None,
        "max_days": lags[-1] if lags else None,
        "divergent_count": len(divergences),
        "example_divergence": public_record(divergences[0]) if divergences else None,
    }


def build_public_safe_manifest(
    records: list[dict[str, Any]],
    *,
    request_manifest: dict[str, Any],
    rejected_counts: dict[str, int],
    duplicate_counts: dict[str, int],
    shard_identities: list[dict[str, Any]],
    include_records: bool = True,
) -> dict[str, Any]:
    records = sorted(records, key=lambda row: (row["publication_date"], row["document_id"]))
    manifest = {
        "schema": PUBLIC_SCHEMA,
        "created_at": utc_now(),
        "caveat": CAVEAT,
        "source_repo_id": REPO_ID,
        "source_revision": FROZEN_REVISION,
        "source_rights_status": SOURCE_RIGHTS_STATUS,
        "date_axis": "publish_date_only",
        "warc_date_usage": "provenance_and_lag_audit_only",
        "public_artifact_policy": "no_text_no_titles_no_previews_hashes_counts_metadata_only",
        "request_manifest_id": request_manifest.get("manifest_id"),
        "target_total_rows": request_manifest.get("target_total_rows"),
        "accepted_count": len(records),
        "rejected_counts": dict(sorted(rejected_counts.items())),
        "duplicate_counts": dict(sorted(duplicate_counts.items())),
        "counts_by_month": count_by(records, "publication_year_month"),
        "counts_by_role": count_by(records, "corpus_role"),
        "counts_by_sitename": count_by(records, "sitename"),
        "date_lag_summary": date_lag_summary(records),
        "word_count": {
            "min": min((row["word_count"] for row in records), default=0),
            "max": max((row["word_count"] for row in records), default=0),
            "mean": round(sum(row["word_count"] for row in records) / len(records), 2) if records else 0,
        },
        "shard_identities": sorted(shard_identities, key=lambda item: item["path"]),
    }
    if include_records:
        manifest["records"] = [public_record(row) for row in records]
    return manifest


def reject_public_text(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered_key = str(key).lower()
            if lowered_key in PUBLIC_BANNED_KEYS or "preview" in lowered_key:
                raise InfiniNewsSchemaError(f"public artifact would contain text-like field {path}/{key}")
            reject_public_text(value, f"{path}/{key}")
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            reject_public_text(item, f"{path}[{idx}]")


def write_public_json(path: Path, payload: dict[str, Any]) -> None:
    reject_public_text(payload)
    text = json.dumps(payload, indent=2, sort_keys=True)
    lowered = text.lower()
    if "forbidden sample body" in lowered:
        raise InfiniNewsSchemaError("public artifact would contain raw text")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def iter_json_public_records(records: Iterable[dict[str, Any]]) -> Iterable[str]:
    first = True
    for row in records:
        safe = public_record(row)
        reject_public_text(safe)
        encoded = json.dumps(safe, sort_keys=True)
        if first:
            yield encoded
            first = False
        else:
            yield ",\n" + encoded


def stream_selected_rows_from_db(
    conn: sqlite3.Connection,
    *,
    manifest: dict[str, Any],
    seed: int,
    per_sitename_cap: int,
) -> Iterable[dict[str, Any]]:
    try:
        for month, target in sorted(manifest["targets_by_month"].items()):
            month_rows, _month_rejections = select_month_rows_from_db(
                conn,
                month=month,
                target=int(target),
                seed=seed,
                per_sitename_cap=per_sitename_cap,
            )
            yield from month_rows
    finally:
        conn.close()


def write_public_manifest_streamed(path: Path, payload: dict[str, Any], records: Iterable[dict[str, Any]]) -> None:
    """Write a public manifest without holding all public records in memory."""
    reject_public_text(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("{\n")
        items = sorted(payload.items())
        for key, value in items:
            handle.write(f"  {json.dumps(key)}: {json.dumps(value, indent=2, sort_keys=True).replace(chr(10), chr(10) + '  ')},\n")
        handle.write("  \"records\": [\n")
        for encoded in iter_json_public_records(records):
            handle.write("    " + encoded)
        handle.write("\n  ]\n}\n")


def hub_file_manifest(
    *,
    targets_by_month: dict[str, int],
    max_shards_per_month: int | None = None,
    preferred_paths_by_month: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    api = HfApi()
    info = api.repo_info(repo_id=REPO_ID, repo_type="dataset", revision=FROZEN_REVISION, files_metadata=True)
    if info.sha != FROZEN_REVISION:
        raise InfiniNewsError(f"resolved revision {info.sha} did not match frozen revision {FROZEN_REVISION}")
    wanted = set(targets_by_month)
    candidates: list[dict[str, Any]] = []
    for sibling in info.siblings:
        path = sibling.rfilename
        if not path.endswith(".parquet"):
            continue
        year, month = shard_partition(path)
        ym = f"{year}-{month:02d}" if year and month else None
        if ym not in wanted:
            continue
        lfs = getattr(sibling, "lfs", None)
        candidates.append(
            {
                "path": path,
                "year_month": ym,
                "size": getattr(sibling, "size", None),
                "blob_id": getattr(sibling, "blob_id", None),
                "lfs_sha256": getattr(lfs, "sha256", None) if lfs else None,
                "lfs_size": getattr(lfs, "size", None) if lfs else None,
            }
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in sorted(candidates, key=lambda item: (item["year_month"], item["path"])):
        grouped[candidate["year_month"]].append(candidate)
    selected = []
    for month in sorted(wanted):
        shards = grouped.get(month, [])
        if preferred_paths_by_month and preferred_paths_by_month.get(month):
            preferred = set(preferred_paths_by_month[month])
            shards = [shard for shard in shards if shard["path"] in preferred]
        if max_shards_per_month is not None:
            shards = shards[:max_shards_per_month]
        selected.extend(shards)
    return selected


def read_shard_rows(shard_path: str, columns: list[str] | None = None, batch_size: int = 2048) -> Iterable[tuple[int, dict[str, Any]]]:
    local_path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", revision=FROZEN_REVISION, filename=shard_path)
    parquet_file = pq.ParquetFile(local_path)
    existing_columns = set(parquet_file.schema.names)
    selected_columns = [col for col in (columns or PARQUET_COLUMNS) if col in existing_columns]
    row_index = 0
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=selected_columns):
        for row in batch.to_pylist():
            yield row_index, row
            row_index += 1


def collect(
    manifest: dict[str, Any],
    output_root: Path,
    *,
    max_shards_per_month: int | None = None,
    max_rows_per_shard: int | None = None,
) -> dict[str, Any]:
    if manifest.get("source_revision") != FROZEN_REVISION:
        raise InfiniNewsError("manifest source_revision does not match frozen revision")
    output_root = Path(output_root)
    ensure_private_path(output_root / "normalized_rows.jsonl")
    accepted_path = output_root / "normalized_rows.jsonl"
    candidate_db_path = output_root / "candidate_records.sqlite3"
    progress_path = output_root / "progress.json"
    progress = load_progress(progress_path)
    conn = connect_private_candidate_db(candidate_db_path)
    seed_candidate_db_from_jsonl(conn, accepted_path)
    rejected = Counter(progress.get("stats", {}).get("rejected_counts", {}))
    shard_identities = hub_file_manifest(
        targets_by_month=manifest["targets_by_month"],
        max_shards_per_month=max_shards_per_month,
        preferred_paths_by_month=manifest.get("preferred_shards_by_month"),
    )
    retrieved_at = utc_now()
    scanned_shards = []
    sample_seed = int(manifest.get("sample_seed", DEFAULT_SEED))
    per_sitename_cap = int(manifest.get("per_sitename_month_cap", DEFAULT_PER_SITENAME_MONTH_CAP))
    satisfied_months: set[str] = set()
    for shard in shard_identities:
        shard_path = shard["path"]
        shard_month = str(shard["year_month"])
        shard_progress = progress["shards"].setdefault(shard_path, {"rows_seen": 0, "complete": False})
        if shard_progress.get("complete"):
            scanned_shards.append(shard)
            continue
        if shard_month in satisfied_months or month_quota_satisfied_in_db(
            conn,
            month=shard_month,
            target=int(manifest["targets_by_month"][shard_month]),
            seed=sample_seed,
            per_sitename_cap=per_sitename_cap,
        ):
            satisfied_months.add(shard_month)
            shard_progress["skipped"] = "month_quota_satisfied"
            continue
        rows_seen = 0
        accepted_in_shard = 0
        for row_index, raw_row in read_shard_rows(shard_path):
            if row_index < int(shard_progress.get("rows_seen", 0)):
                continue
            try:
                normalized = normalize_row(
                    raw_row,
                    shard_path=shard_path,
                    shard_sha256=shard.get("lfs_sha256") or "",
                    row_index=row_index,
                    retrieved_at=retrieved_at,
                )
            except InfiniNewsSchemaError as exc:
                rejected[rejection_code(str(exc))] += 1
            else:
                if add_candidate_record(conn, normalized):
                    accepted_in_shard += 1
            rows_seen = row_index + 1
            shard_progress["rows_seen"] = rows_seen
            if max_rows_per_shard is not None and rows_seen >= max_rows_per_shard:
                break
        shard_progress["complete"] = max_rows_per_shard is None
        shard_progress["accepted_candidates"] = int(shard_progress.get("accepted_candidates", 0)) + accepted_in_shard
        conn.commit()
        progress["stats"]["rejected_counts"] = dict(sorted(rejected.items()))
        progress["stats"]["duplicate_counts"] = duplicate_counts_from_db(conn)
        write_private_json(progress_path, progress)
        scanned_shards.append(shard)
    duplicate_counts = duplicate_counts_from_db(conn)
    selected = []
    selection_rejections = Counter(rejected)
    for month, target in sorted(manifest["targets_by_month"].items()):
        month_rows, month_rejections = select_month_rows_from_db(
            conn,
            month=month,
            target=int(target),
            seed=sample_seed,
            per_sitename_cap=per_sitename_cap,
        )
        selected.extend(month_rows)
        selection_rejections.update(month_rejections)
    write_private_jsonl(accepted_path, selected)
    progress["stats"]["rejected_counts"] = dict(sorted(selection_rejections.items()))
    progress["stats"]["duplicate_counts"] = duplicate_counts
    write_private_json(progress_path, progress)
    conn.close()
    return {
        "records": selected,
        "rejected_counts": dict(sorted(selection_rejections.items())),
        "duplicate_counts": duplicate_counts,
        "shard_identities": scanned_shards,
        "output_root": str(output_root),
    }


def write_default_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--write-default-manifest", type=Path)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--pilot-rows-per-month", type=int, default=2)
    parser.add_argument("--output-root", type=Path, default=PRIVATE_ROOT_MARKER)
    parser.add_argument("--report", type=Path, default=PUBLIC_SAFE_ROOT / "pilot_report.json")
    parser.add_argument("--request-manifest-output", type=Path, default=PUBLIC_SAFE_ROOT / "request_manifest.json")
    parser.add_argument("--max-shards-per-month", type=int, default=None)
    parser.add_argument("--max-rows-per-shard", type=int, default=None)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest, pilot=args.pilot, rows_per_pilot_month=args.pilot_rows_per_month)
    if args.write_default_manifest:
        write_default_manifest(args.write_default_manifest, manifest)
    if args.request_manifest_output:
        write_public_json(args.request_manifest_output, manifest)
    result = collect(
        manifest,
        args.output_root,
        max_shards_per_month=args.max_shards_per_month,
        max_rows_per_shard=args.max_rows_per_shard,
    )
    public = build_public_safe_manifest(
        result["records"],
        request_manifest=manifest,
        rejected_counts=result["rejected_counts"],
        duplicate_counts=result["duplicate_counts"],
        shard_identities=result["shard_identities"],
        include_records=False,
    )
    public["private_output_root"] = str(args.output_root)
    write_public_manifest_streamed(
        args.report,
        public,
        stream_selected_rows_from_db(
            connect_private_candidate_db(Path(result["output_root"]) / "candidate_records.sqlite3"),
            manifest=manifest,
            seed=int(manifest.get("sample_seed", DEFAULT_SEED)),
            per_sitename_cap=int(manifest.get("per_sitename_month_cap", DEFAULT_PER_SITENAME_MONTH_CAP)),
        ),
    )
    printable = public
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
