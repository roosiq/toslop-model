#!/usr/bin/env python3
"""Build a local OpenAlex corpus for the publication-shift model.

Raw and normalized text written by this script is private local research data and
must remain below ignored services/data/publication_shift paths. Reports emitted
under services/evals are intentionally public-safe and contain no text previews.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
SCHEMA = "publication_shift.openalex_corpus.v1"
DEFAULT_CONTACT = "publication-shift-pilot@slopslingers.local"
ALLOWED_TYPES = {"article", "review", "preprint", "letter"}
PRIVATE_ROOT_MARKER = Path("services/data/publication_shift")
PUBLIC_SAFE_KEYS = {
    "document_id",
    "work_id",
    "doi",
    "normalized_text_sha256",
    "near_duplicate_cluster_id",
    "publication_date",
    "publication_year",
    "publication_month",
    "corpus_role",
    "source_id",
    "publisher_id",
    "topic_id",
    "domain_id",
    "field_id",
    "subfield_id",
    "author_ids",
    "word_count",
    "retrieval_manifest_id",
    "split_assignment",
}


class OpenAlexError(RuntimeError):
    pass


class OpenAlexQuotaError(OpenAlexError):
    @classmethod
    def from_status(cls, status: int, body: str) -> "OpenAlexQuotaError":
        raise cls(f"OpenAlex quota/rate-limit error {status}: {body[:240]}")


class OpenAlexSchemaError(OpenAlexError):
    pass


class OpenAlexHTTPError(OpenAlexError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def normalize_doi(doi: Any) -> str | None:
    if not doi:
        return None
    value = str(doi).strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = value.removeprefix("doi:").strip()
    return value or None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def reconstruct_abstract(index: dict[str, list[int]]) -> str:
    if not isinstance(index, dict) or not index:
        raise OpenAlexSchemaError("abstract_inverted_index is missing or invalid")
    positions: dict[int, str] = {}
    for token, token_positions in index.items():
        if not isinstance(token, str) or not isinstance(token_positions, list):
            raise OpenAlexSchemaError("abstract_inverted_index has invalid token entries")
        for position in token_positions:
            if not isinstance(position, int) or position < 0:
                raise OpenAlexSchemaError("abstract_inverted_index has invalid positions")
            if position in positions:
                raise OpenAlexSchemaError("abstract_inverted_index has duplicate positions")
            positions[position] = token
    if sorted(positions) != list(range(len(positions))):
        raise OpenAlexSchemaError("abstract_inverted_index positions are not contiguous")
    return normalize_text(" ".join(positions[idx] for idx in range(len(positions))))


def assign_corpus_role(year: int, month: int, max_forward_month: int = 12) -> str | None:
    if 2014 <= year <= 2017:
        return "historical_placebo"
    if 2018 <= year <= 2021:
        return "pre_llm_core"
    if year == 2022:
        return "transition_2022"
    if 2023 <= year <= 2025:
        return "current_core"
    if year == 2026 and month <= max_forward_month:
        return "forward_2026"
    return None


def _id_at(path: Iterable[str], obj: dict[str, Any]) -> str | None:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return str(cur) if cur else None


def deterministic_near_duplicate_cluster(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < 5:
        source = " ".join(words)
    else:
        shingles = {" ".join(words[idx : idx + 5]) for idx in range(len(words) - 4)}
        # A stable lightweight MinHash-style signature. This intentionally groups
        # exact and very-near duplicates without pulling in non-stdlib deps.
        ranked = sorted(stable_hash(shingle, 32) for shingle in shingles)[:24]
        source = "|".join(ranked)
    return "ndc_" + stable_hash(source, 20)


def normalize_work(work: dict[str, Any], *, manifest_id: str, retrieved_at: str, max_forward_month: int = 12) -> dict[str, Any]:
    work_id = work.get("id")
    if not isinstance(work_id, str) or not work_id:
        raise OpenAlexSchemaError("work id is missing")
    publication_date = work.get("publication_date")
    if not isinstance(publication_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date):
        raise OpenAlexSchemaError("publication_date is missing or invalid")
    try:
        parsed_date = dt.date.fromisoformat(publication_date)
    except ValueError as exc:
        raise OpenAlexSchemaError("publication_date is invalid") from exc
    year = work.get("publication_year")
    if year != parsed_date.year:
        raise OpenAlexSchemaError("publication_year does not match publication_date")
    if work.get("language") != "en":
        raise OpenAlexSchemaError("language is not English")
    work_type = work.get("type") or work.get("type_crossref")
    if work_type not in ALLOWED_TYPES:
        raise OpenAlexSchemaError("work type is not an abstract-bearing article/review/preprint/letter")
    original_text = reconstruct_abstract(work.get("abstract_inverted_index"))
    normalized = normalize_text(original_text)
    words = re.findall(r"\b\S+\b", normalized)
    if len(words) < 150:
        raise OpenAlexSchemaError("abstract has fewer than 150 words")
    role = assign_corpus_role(parsed_date.year, parsed_date.month, max_forward_month=max_forward_month)
    if role is None:
        raise OpenAlexSchemaError("publication date is outside configured corpus roles")

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") if isinstance(primary_location, dict) else None
    source_id = source.get("id") if isinstance(source, dict) else None
    publisher_id = None
    if isinstance(source, dict):
        publisher_id = source.get("host_organization") or _id_at(["host_organization_lineage", "0"], source)
    primary_topic = work.get("primary_topic") or {}
    if not isinstance(primary_topic, dict):
        primary_topic = {}
    author_ids = []
    for authorship in work.get("authorships") or []:
        if isinstance(authorship, dict):
            author_id = _id_at(["author", "id"], authorship)
            if author_id:
                author_ids.append(author_id)
    if not source_id or not publisher_id or not primary_topic.get("id") or not author_ids:
        raise OpenAlexSchemaError("required stable metadata ids are missing")

    text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    doi = normalize_doi(work.get("doi"))
    return {
        "schema": SCHEMA,
        "document_id": "openalex_" + stable_hash(work_id + "|" + publication_date, 24),
        "work_id": work_id,
        "doi": doi,
        "original_abstract": original_text,
        "normalized_abstract": normalized,
        "normalized_text_sha256": text_hash,
        "near_duplicate_cluster_id": deterministic_near_duplicate_cluster(normalized),
        "publication_date": publication_date,
        "publication_year": parsed_date.year,
        "publication_month": parsed_date.month,
        "corpus_role": role,
        "source_id": source_id,
        "publisher_id": publisher_id,
        "topic_id": primary_topic.get("id"),
        "domain_id": _id_at(["domain", "id"], primary_topic),
        "field_id": _id_at(["field", "id"], primary_topic),
        "subfield_id": _id_at(["subfield", "id"], primary_topic),
        "author_ids": sorted(set(author_ids)),
        "word_count": len(words),
        "retrieval_manifest_id": manifest_id,
        "retrieved_at": retrieved_at,
        "split_assignment": None,
    }


def ensure_private_path(path: Path) -> None:
    resolved = path.resolve()
    marker = (Path.cwd() / PRIVATE_ROOT_MARKER).resolve()
    try:
        resolved.relative_to(marker)
    except ValueError as exc:
        raise ValueError(f"private text output must live below {marker}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.parent.resolve()
    while current == marker or marker in current.parents:
        try:
            os.chmod(current, stat.S_IRWXU)
        except FileNotFoundError:
            pass
        if current == marker:
            break
        current = current.parent
    os.chmod(marker, stat.S_IRWXU)


def write_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, stat.S_IRWXU)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)


def append_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Append a completed API page without rewriting the full private corpus."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, stat.S_IRWXU)
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
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"cursors": {}, "stats": {"request_count": 0, "rejected_counts": {}}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Backward-compatible reader for the original cursor-only progress shape.
    if "cursors" not in payload:
        payload = {"cursors": payload, "stats": {"request_count": 0, "rejected_counts": {}}}
    payload.setdefault("cursors", {})
    payload.setdefault("stats", {})
    payload["stats"].setdefault("request_count", 0)
    payload["stats"].setdefault("rejected_counts", {})
    payload["stats"].setdefault("duplicate_counts", {})
    return payload


def write_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(progress, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def dedupe_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen_work: set[str] = set()
    seen_doi: set[str] = set()
    seen_hash: set[str] = set()
    seen_cluster: set[str] = set()
    counts = Counter()
    kept = []
    for record in sorted(records, key=lambda row: (row["publication_date"], row["work_id"])):
        duplicate = False
        if record["work_id"] in seen_work:
            counts["work_id_duplicates"] += 1
            duplicate = True
        doi = record.get("doi")
        if doi and doi in seen_doi:
            counts["doi_duplicates"] += 1
            duplicate = True
        if record["normalized_text_sha256"] in seen_hash:
            counts["text_hash_duplicates"] += 1
            duplicate = True
        if record["near_duplicate_cluster_id"] in seen_cluster:
            counts["near_duplicate_duplicates"] += 1
            duplicate = True
        if duplicate:
            continue
        kept.append(record)
        seen_work.add(record["work_id"])
        if doi:
            seen_doi.add(doi)
        seen_hash.add(record["normalized_text_sha256"])
        seen_cluster.add(record["near_duplicate_cluster_id"])
    counts["input_count"] = len(records)
    counts["kept_count"] = len(kept)
    counts["duplicate_count"] = len(records) - len(kept)
    return kept, dict(counts)


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in sorted(PUBLIC_SAFE_KEYS) if key in record}


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key)) for row in rows).items()))


def build_public_safe_manifest(
    records: list[dict[str, Any]],
    *,
    request_count: int,
    rejected_counts: dict[str, int],
    duplicate_counts: dict[str, int],
    request_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "publication_shift.openalex_public_manifest.v1",
        "created_at": utc_now(),
        "request_manifest_id": (request_manifest or {}).get("manifest_id"),
        "request_count": request_count,
        "accepted_count": len(records),
        "rejected_counts": dict(sorted(rejected_counts.items())),
        "duplicate_counts": dict(sorted(duplicate_counts.items())),
        "counts_by_year": _count_by(records, "publication_year"),
        "counts_by_month": _count_by(records, "publication_month"),
        "counts_by_role": _count_by(records, "corpus_role"),
        "counts_by_source": _count_by(records, "source_id"),
        "counts_by_topic": _count_by(records, "topic_id"),
        "word_count": {
            "min": min((row["word_count"] for row in records), default=0),
            "max": max((row["word_count"] for row in records), default=0),
            "mean": round(sum(row["word_count"] for row in records) / len(records), 2) if records else 0,
        },
        "records": [public_record(row) for row in records],
    }


def write_public_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    lowered = text.lower()
    if "abstract" in lowered or "preview" in lowered:
        raise OpenAlexSchemaError("public artifact would contain raw text/preview fields")
    path.write_text(text + "\n", encoding="utf-8")


def default_manifest(pilot: bool = False) -> dict[str, Any]:
    if pilot:
        targets = {str(year): 5 for year in list(range(2014, 2027))}
    else:
        targets = {
            **{str(year): 2000 for year in range(2014, 2018)},
            **{str(year): 5000 for year in range(2018, 2022)},
            "2022": 2000,
            **{str(year): 5000 for year in range(2023, 2026)},
            "2026": 2000,
        }
    manifest = {
        "schema": "publication_shift.openalex_request_manifest.v1",
        "manifest_id": "openalex_pilot_v1" if pilot else "openalex_v1",
        "created_at": "2026-07-12T00:00:00Z",
        "source": "OpenAlex Works API",
        "works_url": OPENALEX_WORKS_URL,
        "mailto": os.environ.get("OPENALEX_CONTACT_EMAIL", DEFAULT_CONTACT),
        "per_page": 200,
        "max_retries": 4,
        "retry_backoff_seconds": 2.0,
        "sample_seed": 20260712,
        "max_forward_month": 7,
        "targets_by_year": targets,
        "filters": {
            "language": "en",
            "type": "article|review|preprint|letter",
            "has_abstract": True,
        },
    }
    return manifest


def load_manifest(path: Path | None, pilot: bool) -> dict[str, Any]:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_manifest(pilot=pilot)


def openalex_headers() -> dict[str, str]:
    return {
        "User-Agent": f"SlopSlingersPublicationShift/0.1 (mailto:{os.environ.get('OPENALEX_CONTACT_EMAIL', DEFAULT_CONTACT)})",
        "Accept": "application/json",
    }


def build_openalex_url(year: int, cursor: str, per_page: int, mailto: str) -> str:
    filters = [
        f"from_publication_date:{year}-01-01",
        f"to_publication_date:{year}-12-31",
        "language:en",
        "has_abstract:true",
        "type:article|review|preprint|letter",
    ]
    params = {
        "filter": ",".join(filters),
        "sort": "publication_date:asc",
        "per-page": str(per_page),
        "cursor": cursor,
        "mailto": mailto,
    }
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS_URL + "?" + urllib.parse.urlencode(params, safe=",:|")


def rejection_code(message: str) -> str:
    lowered = message.lower()
    if "fewer than 150" in lowered:
        return "too_short"
    if "language" in lowered:
        return "non_english"
    if "work type" in lowered:
        return "invalid_type"
    if "publication_date" in lowered or "publication_year" in lowered:
        return "invalid_date"
    if "metadata" in lowered:
        return "missing_metadata"
    if "inverted_index" in lowered:
        return "text_reconstruction_failed"
    return "schema_rejected"


def fetch_json(url: str, max_retries: int, backoff: float) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, headers=openalex_headers())
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                body = response.read().decode("utf-8")
            if status in {401, 403, 429}:
                OpenAlexQuotaError.from_status(status, body)
            if status >= 500 and attempt < max_retries:
                time.sleep(backoff * (2**attempt))
                continue
            if status >= 400:
                raise OpenAlexHTTPError(f"OpenAlex HTTP {status}: {body[:240]}")
            return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {401, 403, 429}:
                OpenAlexQuotaError.from_status(exc.code, body)
            if exc.code >= 500 and attempt < max_retries:
                time.sleep(backoff * (2**attempt))
                continue
            raise OpenAlexHTTPError(f"OpenAlex HTTP {exc.code}: {body[:240]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < max_retries:
                time.sleep(backoff * (2**attempt))
                continue
            raise OpenAlexHTTPError(f"OpenAlex request failed after retries: {exc}") from exc
    raise OpenAlexHTTPError("OpenAlex request failed")


def collect(manifest: dict[str, Any], output_root: Path, *, max_requests: int | None = None) -> dict[str, Any]:
    ensure_private_path(output_root / "normalized_rows.jsonl")
    accepted_path = output_root / "normalized_rows.jsonl"
    raw_path = output_root / "raw_works.jsonl"
    progress_path = output_root / "progress.json"

    existing, startup_dedup = dedupe_records(read_jsonl(accepted_path))
    if startup_dedup.get("duplicate_count", 0):
        write_private_jsonl(accepted_path, existing)
    accepted_by_year = Counter(str(row["publication_year"]) for row in existing)
    accepted = list(existing)

    progress = load_progress(progress_path)
    stats = progress.setdefault("stats", {})
    cursors = progress.setdefault("cursors", {})
    rejected = Counter(stats.get("rejected_counts", {}))
    duplicate_counts = Counter(stats.get("duplicate_counts", {}))
    duplicate_counts.update(
        {
            key: value
            for key, value in startup_dedup.items()
            if key.endswith("_duplicates") or key == "duplicate_count"
        }
    )
    request_count = 0
    total_request_count = int(stats.get("request_count", 0))
    targets = {str(k): int(v) for k, v in manifest["targets_by_year"].items()}

    seen_work = {row["work_id"] for row in accepted}
    seen_doi = {row["doi"] for row in accepted if row.get("doi")}
    seen_hash = {row["normalized_text_sha256"] for row in accepted}
    seen_cluster = {row["near_duplicate_cluster_id"] for row in accepted}

    for year_s in sorted(targets):
        target = targets[year_s]
        year = int(year_s)
        cursor = cursors.get(year_s, "*")
        while accepted_by_year[year_s] < target:
            if max_requests is not None and request_count >= max_requests:
                break
            url = build_openalex_url(year, cursor, int(manifest.get("per_page", 200)), manifest.get("mailto", DEFAULT_CONTACT))
            requested_at = utc_now()
            payload = fetch_json(url, int(manifest.get("max_retries", 4)), float(manifest.get("retry_backoff_seconds", 2.0)))
            request_count += 1
            total_request_count += 1
            if "results" not in payload or "meta" not in payload:
                raise OpenAlexSchemaError("OpenAlex response missing results/meta")
            next_cursor = payload.get("meta", {}).get("next_cursor")
            if not next_cursor:
                raise OpenAlexSchemaError("OpenAlex cursor response missing next_cursor")

            page_raw: list[dict[str, Any]] = []
            page_accepted: list[dict[str, Any]] = []
            for work in payload["results"]:
                page_raw.append({"retrieved_at": requested_at, "work": work})
                try:
                    row = normalize_work(
                        work,
                        manifest_id=manifest["manifest_id"],
                        retrieved_at=requested_at,
                        max_forward_month=int(manifest.get("max_forward_month", 12)),
                    )
                except OpenAlexSchemaError as exc:
                    rejected[rejection_code(str(exc))] += 1
                    continue
                if row["publication_year"] != year:
                    rejected["publication_year_filter_mismatch"] += 1
                    continue

                duplicate_reasons = []
                if row["work_id"] in seen_work:
                    duplicate_reasons.append("work_id_duplicates")
                if row.get("doi") and row["doi"] in seen_doi:
                    duplicate_reasons.append("doi_duplicates")
                if row["normalized_text_sha256"] in seen_hash:
                    duplicate_reasons.append("text_hash_duplicates")
                if row["near_duplicate_cluster_id"] in seen_cluster:
                    duplicate_reasons.append("near_duplicate_duplicates")
                if duplicate_reasons:
                    duplicate_counts["duplicate_count"] += 1
                    duplicate_counts.update(duplicate_reasons)
                    continue

                accepted.append(row)
                page_accepted.append(row)
                accepted_by_year[year_s] += 1
                seen_work.add(row["work_id"])
                if row.get("doi"):
                    seen_doi.add(row["doi"])
                seen_hash.add(row["normalized_text_sha256"])
                seen_cluster.add(row["near_duplicate_cluster_id"])
                if accepted_by_year[year_s] >= target:
                    break

            cursor = next_cursor
            cursors[year_s] = cursor
            stats["request_count"] = total_request_count
            stats["rejected_counts"] = dict(sorted(rejected.items()))
            stats["duplicate_counts"] = dict(sorted(duplicate_counts.items()))
            # Data is fsynced before the cursor advances. A crash may replay one
            # page, which the online dedupe sets safely discard on resume.
            append_private_jsonl(accepted_path, page_accepted)
            append_private_jsonl(raw_path, page_raw)
            write_progress(progress_path, progress)
        if max_requests is not None and request_count >= max_requests:
            break

    deduped, final_dedup = dedupe_records(accepted)
    duplicate_counts.update(
        {
            key: value
            for key, value in final_dedup.items()
            if key.endswith("_duplicates") or key == "duplicate_count"
        }
    )
    write_private_jsonl(accepted_path, deduped)
    stats["duplicate_counts"] = dict(sorted(duplicate_counts.items()))
    write_progress(progress_path, progress)
    return {
        "records": deduped,
        "request_count": total_request_count,
        "requests_this_run": request_count,
        "rejected_counts": dict(rejected),
        "duplicate_counts": dict(sorted(duplicate_counts.items())),
        "accepted_by_year": dict(sorted(Counter(str(r["publication_year"]) for r in deduped).items())),
        "output_root": str(output_root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--write-default-manifest", type=Path)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--output-root", type=Path, required=False, default=Path("services/data/publication_shift/openalex_v1"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=None)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest, args.pilot)
    if args.write_default_manifest:
        args.write_default_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_default_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = collect(manifest, args.output_root, max_requests=args.max_requests)
    public = build_public_safe_manifest(
        result["records"],
        request_count=result["request_count"],
        rejected_counts=result["rejected_counts"],
        duplicate_counts=result["duplicate_counts"],
        request_manifest=manifest,
    )
    public["private_output_root"] = str(args.output_root)
    public["accepted_by_year"] = result["accepted_by_year"]
    write_public_json(args.report, public)
    print(json.dumps({k: v for k, v in public.items() if k != "records"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
