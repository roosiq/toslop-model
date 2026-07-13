#!/usr/bin/env python3
"""Build and score the sealed matched multi-source external publication-shift challenge.

Raw article text is local/private only. Public artifacts contain hashes, IDs,
provenance, metrics, and diagnostics only.

This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import stat
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import joblib
import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss, f1_score, roc_auc_score

from train_infini_news_publication_shift_candidates import assert_public_safe, mask_content

DISCLAIMER = "This score does not establish AI authorship."
SEED = 20260713
SCORE_NAME = "current_era_similarity"
REQUEST_SCHEMA = "publication_shift.multisource_external_request_manifest.v1"
CORPUS_SCHEMA = "publication_shift.multisource_external_corpus.v1"
PUBLIC_CORPUS_SCHEMA = "publication_shift.multisource_external_public_manifest.v1"
REPORT_SCHEMA = "publication_shift.multisource_external_report.v1"
CHECKSUM_SCHEMA = "publication_shift.multisource_external_checksums.v1"
PRIVATE_ROOT = Path("services/data/publication_shift/multisource_external_v1")
PUBLIC_ROOT = Path("services/evals/publication_shift_model/multisource_external_v1")
CROSS_DEDUPE_ENV_VAR = "PUBLICATION_SHIFT_CROSS_DEDUPE_PATH"
CROSS_DEDUPE_RELATIVE_PATH = Path("services/data/publication_shift/infini_news_v1/normalized_rows.jsonl")
CROSS_DEDUPE_LOGICAL_REFERENCE = "infini_news_v1_normalized_rows"
FROZEN_ARTIFACT_PATH = Path("services/gateway/model_artifacts/publication_shift/infini_news_v1/infini_news_word_char_tfidf_logistic.joblib")
FROZEN_METADATA_PATH = Path("services/evals/publication_shift_model/infini_news_v1/candidates/lexical_tfidf_logistic/model_metadata.json")
FROZEN_MODEL_ID = "infini-news-lexical_tfidf_logistic-v1-cca5838ac34f"
FROZEN_ARTIFACT_SHA256 = "0ca8956726b101fd585ff663caf4119e4911d3ec2789cf25fab415669691d403"
FROZEN_THRESHOLD = 0.49690983649044096
FROZEN_CONFIG = {
    "word_ngram_range": [1, 3],
    "char_ngram_range": [3, 5],
    "min_df": 3,
    "max_df": 0.995,
    "word_max_features": 100000,
    "char_max_features": 100000,
    "class_weight": "balanced",
    "solver": "liblinear",
    "C": 1.0,
    "max_iter": 500,
    "random_seed": 20260712,
}
SOURCE_RIGHTS_STATUS = "HOLD_combined_cc_and_unspecified_public_no_text_only"
SOURCE_SCHEMA_FIELDS = ["date_publish", "date_download", "date_modify", "maintext", "source_domain", "url"]
SOURCES = {
    "pre_llm_2021": {
        "repo_id": "RealTimeData/News_Seq_2021",
        "revision": "b703213f35f4b604a15ffa92d3bb4090dba25ad5",
        "filename": "data/train-00000-of-00001-347d4b994ed4dc71.parquet",
        "expected_lfs_sha256": "252b4f93c4123053a2e32b85d8b5c4df247f5d7704a62cc7baecfca03f6eac48",
        "role": "pre_llm_core",
        "label": 0,
        "date_start": "2021-08-01",
        "date_end": "2021-08-31",
        "license": None,
        "license_note": "Dataset card has no explicit license; redistribution remains HOLD.",
    },
    "current_2023": {
        "repo_id": "RealTimeData/News_August_2023",
        "revision": "eedb055bf0b5583f22854c347e51a0b5a5d76f49",
        "filename": "data/train-00000-of-00001-4ad0fe9bc38de63f.parquet",
        "expected_lfs_sha256": "54edee87f3492d01a4921e5571b81d3c3297deff30fb4d8ec55d5780218aeff7",
        "role": "current_core",
        "label": 1,
        "date_start": "2023-07-01",
        "date_end": "2023-08-31",
        "license": "cc",
        "license_note": "Dataset declares license cc; combined challenge remains HOLD because the 2021 source has no explicit license.",
    },
}
PUBLIC_BANNED_KEYS = {"content", "maintext", "normalized_text", "original_text", "text", "body", "title", "description", "preview", "url", "link", "top_image", "normalized_url"}


class MultisourceExternalValidationError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: str, length: int = 24) -> str:
    return sha256_text(value)[:length]


def default_cross_dedupe_path() -> Path:
    """Resolve a private input from an environment override or repository-relative default."""
    return Path(os.environ.get(CROSS_DEDUPE_ENV_VAR, CROSS_DEDUPE_RELATIVE_PATH.as_posix()))


def default_request_manifest() -> dict[str, Any]:
    return {
        "schema": REQUEST_SCHEMA,
        "manifest_id": "multisource_external_v1_all_and_domain_matched",
        "created_at": "2026-07-13T00:00:00Z",
        "sources": SOURCES,
        "source_schema_fields": SOURCE_SCHEMA_FIELDS,
        "date_axis": "date_publish_only",
        "date_policy": "reject_missing_or_out_of_window_date_publish_do_not_substitute_dataset_names_download_or_modify_dates",
        "minimum_words": 150,
        "language_policy": "english_heuristic_ascii_function_word_screen",
        "lanes": ["all_valid_source_diverse", "domain_matched_balanced"],
        "sample_seed": SEED,
        "source_rights_status": SOURCE_RIGHTS_STATUS,
        "source_license_note": "News_August_2023 declares license cc; News_Seq_2021 has no explicit license, so combined rights/redistribution remain HOLD.",
        "public_artifact_policy": "no_text_no_titles_no_descriptions_no_urls_hashes_counts_metadata_predictions_only",
        "external_source_note": "Two independent RealTimeData news snapshots with actual date_publish values mostly in 2021-08 and 2023-07/08.",
        "disclaimer": DISCLAIMER,
    }


def parse_date_publish(value: Any) -> dt.date:
    if not isinstance(value, str) or not value.strip():
        raise MultisourceExternalValidationError("date_publish is missing")
    raw = value.strip().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value.strip()[:10])
        except ValueError as exc:
            raise MultisourceExternalValidationError("date_publish is invalid") from exc


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def word_count(value: str) -> int:
    return len(re.findall(r"\b\S+\b", value))


def require_str(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MultisourceExternalValidationError(f"{key} is missing")
    return value.strip()


def normalize_domain(value: str) -> str:
    host = value.strip().lower()
    if "://" in host:
        host = urllib.parse.urlsplit(host).hostname or ""
    host = host.split("/", 1)[0].split(":", 1)[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        raise MultisourceExternalValidationError("source_domain is missing")
    return host


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    scheme = (parsed.scheme or "https").lower()
    host = normalize_domain(parsed.hostname or parsed.netloc)
    if not host:
        raise MultisourceExternalValidationError("url hostname is missing")
    path = re.sub(r"/+$", "", parsed.path or "/")
    query_pairs = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
            continue
        query_pairs.append((key, value))
    query = urllib.parse.urlencode(sorted(query_pairs), doseq=True)
    return urllib.parse.urlunsplit((scheme, host, path, query, ""))


def english_like(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text)
    if len(letters) < 100:
        return False
    ascii_ratio = sum(ord(ch) < 128 for ch in text) / max(1, len(text))
    tokens = re.findall(r"[A-Za-z']+", text)
    if len(tokens) >= 150:
        return ascii_ratio >= 0.82
    words = {word.lower() for word in tokens}
    common = {"the", "and", "of", "to", "in", "a", "is", "for", "on", "with", "as", "by", "that", "from"}
    return ascii_ratio >= 0.82 and len(words & common) >= 3


def near_duplicate_cluster(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    shingles = {" ".join(words[index : index + 5]) for index in range(max(0, len(words) - 4))}
    if not shingles:
        shingles = {" ".join(words)}
    source = "|".join(sorted(stable_hash(shingle, 32) for shingle in shingles)[:24])
    return "ndc_" + stable_hash(source, 20)


def _authors_hash(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        text = ";".join(str(item).strip() for item in value if str(item).strip())
    else:
        text = str(value).strip()
    return sha256_text(text.lower()) if text else None


def normalize_source_row(row: dict[str, Any], *, source_key: str, source: dict[str, Any], row_index: int, retrieved_at: str) -> dict[str, Any]:
    published = parse_date_publish(row.get("date_publish"))
    start = dt.date.fromisoformat(source["date_start"])
    end = dt.date.fromisoformat(source["date_end"])
    if not start <= published <= end:
        raise MultisourceExternalValidationError(f"date_publish outside source window: {published.isoformat()}")
    text = normalize_text(require_str(row, "maintext"))
    words = word_count(text)
    if words < 150:
        raise MultisourceExternalValidationError("maintext has fewer than 150 words")
    raw_domain = require_str(row, "source_domain")
    raw_url = require_str(row, "url")
    if not english_like(text):
        raise MultisourceExternalValidationError("maintext is not English-like")
    domain = normalize_domain(raw_domain)
    normalized_url = normalize_url(raw_url)
    text_hash = sha256_text(text)
    identity = "|".join([source["repo_id"], source["revision"], source["filename"], raw_url, str(row_index), text_hash])
    return {
        "schema": CORPUS_SCHEMA,
        "document_id": "multisource_external_" + stable_hash(identity, 24),
        "source_key": source_key,
        "source_repo_id": source["repo_id"],
        "source_revision": source["revision"],
        "source_file": source["filename"],
        "source_row_index": row_index,
        "source_domain": domain,
        "source_domain_hash": sha256_text(domain),
        "url_hash": sha256_text(raw_url),
        "normalized_url_hash": sha256_text(normalized_url),
        "identity_hash": sha256_text(identity),
        "date_publish": published.isoformat(),
        "publication_date": published.isoformat(),
        "publication_year": published.year,
        "publication_month": published.month,
        "publication_year_month": f"{published.year}-{published.month:02d}",
        "author_hash": _authors_hash(row.get("authors")),
        "missing_author": _authors_hash(row.get("authors")) is None,
        "normalized_text": text,
        "normalized_text_sha256": text_hash,
        "near_duplicate_cluster_id": near_duplicate_cluster(text),
        "word_count": words,
        "corpus_role": source["role"],
        "label": int(source["label"]),
        "retrieved_at": retrieved_at,
        "rights_status": SOURCE_RIGHTS_STATUS,
    }


def public_record(row: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "document_id", "source_key", "source_repo_id", "source_revision", "source_file", "source_row_index",
        "source_domain_hash", "url_hash", "normalized_url_hash", "identity_hash", "date_publish",
        "publication_date", "publication_year", "publication_month", "publication_year_month", "author_hash",
        "missing_author", "normalized_text_sha256", "near_duplicate_cluster_id", "word_count", "corpus_role",
        "label", "retrieved_at", "rights_status",
    }
    return {key: row.get(key) for key in sorted(allowed) if key in row}


def reject_public_text(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        data_value_paths = {"/counts_by_month", "/counts_by_role", "/counts_by_source_key"}
        for key, value in payload.items():
            lowered = str(key).lower()
            if path not in data_value_paths and (lowered in PUBLIC_BANNED_KEYS or "preview" in lowered or lowered.endswith("text")):
                raise MultisourceExternalValidationError(f"public artifact contains forbidden text key {path}/{key}")
            reject_public_text(value, f"{path}/{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            reject_public_text(item, f"{path}[{index}]")
    elif isinstance(payload, str) and re.search(r"(?:^|\s)(?:/home/|/Users/|[A-Za-z]:[\\/]+Users[\\/]+)", payload):
        raise MultisourceExternalValidationError(f"public artifact contains an absolute local path at {path}")


def write_public_json(path: Path, payload: Any) -> None:
    reject_public_text(payload)
    assert_public_safe(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl_public(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            reject_public_text(row)
            assert_public_safe(row)
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def ensure_private(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.parent
    while current != current.parent:
        try:
            os.chmod(current, stat.S_IRWXU)
        except OSError:
            pass
        if current.name == PRIVATE_ROOT.name:
            break
        current = current.parent


def write_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_private(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_cross_dedupe(path: Path | None) -> dict[str, set[str]]:
    values = {"normalized_url_hash": set(), "normalized_text_sha256": set(), "near_duplicate_cluster_id": set()}
    if not path or not path.exists():
        return values
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            for key in values:
                if row.get(key):
                    values[key].add(str(row[key]))
    return values


def dedupe_records(records: Sequence[dict[str, Any]], cross: dict[str, set[str]] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen_url: set[str] = set()
    seen_text: set[str] = set()
    seen_near: set[str] = set()
    counts = Counter()
    kept = []
    cross = cross or {"normalized_url_hash": set(), "normalized_text_sha256": set(), "near_duplicate_cluster_id": set()}
    for row in sorted(records, key=lambda item: (item["publication_date"], item["source_domain"], item["document_id"])):
        reasons = []
        if row["normalized_url_hash"] in seen_url or row["normalized_url_hash"] in cross.get("normalized_url_hash", set()):
            reasons.append("url_duplicates")
        if row["normalized_text_sha256"] in seen_text or row["normalized_text_sha256"] in cross.get("normalized_text_sha256", set()):
            reasons.append("text_hash_duplicates")
        if row["near_duplicate_cluster_id"] in seen_near or row["near_duplicate_cluster_id"] in cross.get("near_duplicate_cluster_id", set()):
            reasons.append("near_duplicate_duplicates")
        if reasons:
            counts["duplicate_count"] += 1
            counts.update(reasons)
            continue
        kept.append(row)
        seen_url.add(row["normalized_url_hash"])
        seen_text.add(row["normalized_text_sha256"])
        seen_near.add(row["near_duplicate_cluster_id"])
    counts["input_count"] = len(records)
    counts["kept_count"] = len(kept)
    counts.setdefault("duplicate_count", len(records) - len(kept))
    return kept, dict(sorted(counts.items()))


def select_domain_matched_lane(rows: Sequence[dict[str, Any]], seed: int = SEED) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_domain: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: {0: [], 1: []})
    for row in rows:
        by_domain[str(row["source_domain"])][int(row["label"])].append(row)
    selected: list[dict[str, Any]] = []
    per_domain = {}
    for domain in sorted(by_domain):
        pre = sorted(by_domain[domain][0], key=lambda row: (stable_hash(f"{seed}|{domain}|0|{row['document_id']}", 32), row["document_id"]))
        current = sorted(by_domain[domain][1], key=lambda row: (stable_hash(f"{seed}|{domain}|1|{row['document_id']}", 32), row["document_id"]))
        take = min(len(pre), len(current))
        if take <= 0:
            continue
        chosen_pre = sorted(pre[:take], key=lambda row: (row.get("publication_date"), row["document_id"]))
        chosen_current = sorted(current[:take], key=lambda row: (row.get("publication_date"), row["document_id"]))
        selected.extend(chosen_pre)
        selected.extend(chosen_current)
        per_domain[sha256_text(domain)] = {
            "available_pre_llm_core": len(pre),
            "available_current_core": len(current),
            "selected_pre_llm_core": take,
            "selected_current_core": take,
        }
    selected = sorted(selected, key=lambda row: (row["source_domain"], row["label"], row.get("publication_date"), row["document_id"]))
    totals = Counter(str(row.get("corpus_role") or ("current_core" if int(row.get("label", 0)) == 1 else "pre_llm_core")) for row in selected)
    proof = {
        "exact_per_domain_era_balance": all(item["selected_pre_llm_core"] == item["selected_current_core"] for item in per_domain.values()),
        "overlapping_domain_count": len(per_domain),
        "total_per_era": {"pre_llm_core": int(totals.get("pre_llm_core", 0)), "current_core": int(totals.get("current_core", 0))},
        "per_domain": dict(sorted(per_domain.items())),
    }
    return selected, proof


def hub_source_file(source: dict[str, Any]) -> dict[str, Any]:
    api = HfApi()
    info = api.repo_info(repo_id=source["repo_id"], repo_type="dataset", revision=source["revision"], files_metadata=True)
    if info.sha != source["revision"]:
        raise MultisourceExternalValidationError(f"resolved revision {info.sha} did not match {source['revision']}")
    for sibling in info.siblings:
        if sibling.rfilename == source["filename"]:
            lfs = getattr(sibling, "lfs", None)
            lfs_sha = getattr(lfs, "sha256", None) if lfs else None
            if source.get("expected_lfs_sha256") and lfs_sha and lfs_sha != source["expected_lfs_sha256"]:
                raise MultisourceExternalValidationError(f"LFS sha mismatch for {source['repo_id']} {source['filename']}")
            return {"repo_id": source["repo_id"], "revision": source["revision"], "path": sibling.rfilename, "size": getattr(sibling, "size", None), "lfs_sha256": lfs_sha}
    raise MultisourceExternalValidationError(f"missing source file {source['filename']} in {source['repo_id']}")


def iter_source_rows(source: dict[str, Any]) -> Iterable[tuple[int, dict[str, Any]]]:
    local = hf_hub_download(repo_id=source["repo_id"], repo_type="dataset", revision=source["revision"], filename=source["filename"])
    parquet = pq.ParquetFile(local)
    columns = [col for col in SOURCE_SCHEMA_FIELDS if col in parquet.schema.names]
    row_index = 0
    for batch in parquet.iter_batches(batch_size=2048, columns=columns):
        for row in batch.to_pylist():
            yield row_index, row
            row_index += 1


def rejection_code(message: str) -> str:
    lowered = message.lower()
    if "150 words" in lowered:
        return "too_short"
    if "date_publish" in lowered:
        return "invalid_or_out_of_window_date_publish"
    if "english" in lowered:
        return "non_english"
    if "url" in lowered:
        return "invalid_url"
    if "source_domain" in lowered:
        return "invalid_source_domain"
    if "maintext" in lowered:
        return "invalid_maintext"
    return "schema_rejected"


def collect_multisource_corpus(manifest: dict[str, Any], output_root: Path, *, cross_dedupe_path: Path | None = None, max_rows_per_source: int | None = None) -> dict[str, Any]:
    retrieved_at = utc_now()
    rejected = Counter()
    normalized: list[dict[str, Any]] = []
    source_files = []
    for source_key, source in sorted(manifest["sources"].items()):
        source_files.append(hub_source_file(source))
        seen = 0
        for row_index, raw in iter_source_rows(source):
            seen += 1
            try:
                normalized.append(normalize_source_row(raw, source_key=source_key, source=source, row_index=row_index, retrieved_at=retrieved_at))
            except MultisourceExternalValidationError as exc:
                rejected[f"{source_key}:{rejection_code(str(exc))}"] += 1
            if max_rows_per_source is not None and seen >= max_rows_per_source:
                break
    cross = load_cross_dedupe(cross_dedupe_path)
    all_valid, duplicate_counts = dedupe_records(normalized, cross)
    matched, proof = select_domain_matched_lane(all_valid, seed=int(manifest.get("sample_seed", SEED)))
    write_private_jsonl(output_root / "all_valid_source_diverse_normalized_rows.jsonl", all_valid)
    write_private_jsonl(output_root / "domain_matched_balanced_normalized_rows.jsonl", matched)
    return {"all_valid_source_diverse": all_valid, "domain_matched_balanced": matched, "domain_balance_proof": proof, "rejected_counts": dict(sorted(rejected.items())), "duplicate_counts": duplicate_counts, "source_files": source_files}


def count_by(rows: Sequence[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key)) for row in rows).items()))


def build_public_corpus_manifest(*, lanes: dict[str, Sequence[dict[str, Any]]], request_manifest: dict[str, Any], rejected_counts: dict[str, int], duplicate_counts: dict[str, int], source_files: Sequence[dict[str, Any]], cross_dedupe_reference: str | None, domain_balance_proof: dict[str, Any]) -> dict[str, Any]:
    lane_payload = {}
    for lane_name, rows in lanes.items():
        lane_payload[lane_name] = {
            "accepted_count": len(rows),
            "counts_by_month": count_by(rows, "publication_year_month"),
            "counts_by_role": count_by(rows, "corpus_role"),
            "counts_by_source_key": count_by(rows, "source_key"),
            "source_domain_hash_count": len({row.get("source_domain_hash") for row in rows}),
            "records": [public_record(row) for row in sorted(rows, key=lambda item: (item["publication_date"], item["document_id"]))],
        }
    public = {
        "schema": PUBLIC_CORPUS_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "sources": {key: {k: v for k, v in source.items() if k != "expected_lfs_sha256"} for key, source in request_manifest["sources"].items()},
        "source_schema_fields": SOURCE_SCHEMA_FIELDS,
        "source_rights_status": SOURCE_RIGHTS_STATUS,
        "date_axis": "date_publish_only",
        "request_manifest_id": request_manifest.get("manifest_id"),
        "rejected_counts": dict(sorted(rejected_counts.items())),
        "duplicate_counts": dict(sorted(duplicate_counts.items())),
        "cross_dedupe_reference": cross_dedupe_reference,
        "source_files": sorted(source_files, key=lambda item: (item["repo_id"], item["path"])),
        "lanes": lane_payload,
        "domain_matched_balance_proof": domain_balance_proof,
    }
    reject_public_text(public)
    assert_public_safe(public)
    return public


def verify_frozen_model_identity(artifact: dict[str, Any], metadata: dict[str, Any], *, artifact_sha256: str) -> None:
    checks = [
        (artifact.get("model_id"), FROZEN_MODEL_ID, "model_id"),
        (metadata.get("model_id"), FROZEN_MODEL_ID, "metadata model_id"),
        (artifact_sha256, FROZEN_ARTIFACT_SHA256, "artifact sha256"),
        (metadata.get("artifact_sha256"), FROZEN_ARTIFACT_SHA256, "metadata artifact_sha256"),
        (float(artifact.get("threshold")), FROZEN_THRESHOLD, "threshold"),
        (float(metadata.get("threshold")), FROZEN_THRESHOLD, "metadata threshold"),
        (artifact.get("config"), FROZEN_CONFIG, "config"),
        (metadata.get("config"), FROZEN_CONFIG, "metadata config"),
    ]
    for actual, expected, name in checks:
        if actual != expected:
            raise MultisourceExternalValidationError(f"frozen {name} mismatch: {actual!r} != {expected!r}")


def score_rows(model: dict[str, Any], rows: Sequence[dict[str, Any]], *, masked: bool = False) -> list[dict[str, Any]]:
    texts = [mask_content(row["normalized_text"]) if masked else row["normalized_text"] for row in rows]
    matrix = model["features"].transform(texts)
    scores = model["classifier"].predict_proba(matrix)[:, 1]
    predictions = []
    for row, score in zip(rows, scores):
        out = public_record(row)
        out.update({"model_id": FROZEN_MODEL_ID, "score_name": SCORE_NAME, SCORE_NAME: float(score), "threshold": FROZEN_THRESHOLD, "predicted_label": int(float(score) >= FROZEN_THRESHOLD), "masked": masked})
        predictions.append(out)
    return predictions


def expected_calibration_error(labels: np.ndarray, scores: np.ndarray, bins: int = 10) -> float | None:
    if len(labels) == 0:
        return None
    edges = np.linspace(0.0, 1.0, bins + 1)
    value = 0.0
    for index in range(bins):
        mask = (scores >= edges[index]) & (scores < edges[index + 1] if index < bins - 1 else scores <= edges[index + 1])
        if np.any(mask):
            value += float(np.mean(mask)) * abs(float(np.mean(labels[mask])) - float(np.mean(scores[mask])))
    return float(value)


def binary_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    labelled = [row for row in rows if row.get("label") is not None]
    y = np.asarray([int(row["label"]) for row in labelled], dtype=np.int8)
    p = np.asarray([float(row[SCORE_NAME]) for row in labelled], dtype=float)
    result: dict[str, Any] = {"count": len(labelled), "positive_count": int(y.sum()) if len(y) else 0, "negative_count": int(len(y) - y.sum()) if len(y) else 0, "threshold": FROZEN_THRESHOLD}
    if len(y) == 0:
        return result
    pred = p >= FROZEN_THRESHOLD
    result["accuracy"] = float(accuracy_score(y, pred))
    if len(set(y.tolist())) < 2:
        result.update({"roc_auc": None, "pr_auc": None, "balanced_accuracy": None, "f1": None, "brier": None, "ece": None})
    else:
        result.update({"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "balanced_accuracy": float(balanced_accuracy_score(y, pred)), "f1": float(f1_score(y, pred)), "brier": float(brier_score_loss(y, p)), "ece": expected_calibration_error(y, p)})
    if result["negative_count"]:
        result["specificity"] = float(np.mean(~pred[y == 0]))
        result["false_positive_rate"] = float(np.mean(pred[y == 0]))
    if result["positive_count"]:
        result["sensitivity"] = float(np.mean(pred[y == 1]))
        result["false_negative_rate"] = float(np.mean(~pred[y == 1]))
    return result


def grouped_bootstrap_auc(rows: Sequence[dict[str, Any]], *, group_key: str = "source_domain_hash", samples: int = 300, seed: int = SEED) -> dict[str, Any]:
    labelled = [row for row in rows if row.get("label") is not None]
    if len({row["label"] for row in labelled}) < 2:
        return {"samples_requested": samples, "samples_valid": 0, "lower": None, "median": None, "upper": None}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(labelled):
        groups[str(row.get(group_key) or f"missing-{index}")].append(row)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(samples):
        chosen = rng.choice(keys, size=len(keys), replace=True)
        sample = [row for key in chosen for row in groups[str(key)]]
        if len({row["label"] for row in sample}) < 2:
            continue
        values.append(binary_metrics(sample)["roc_auc"])
    if not values:
        return {"samples_requested": samples, "samples_valid": 0, "lower": None, "median": None, "upper": None}
    return {"samples_requested": samples, "samples_valid": len(values), "lower": float(np.quantile(values, 0.025)), "median": float(np.quantile(values, 0.5)), "upper": float(np.quantile(values, 0.975))}


def slice_metrics(rows: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    output = {}
    for value in sorted({str(row.get(key)) for row in rows}):
        bucket = [row for row in rows if str(row.get(key)) == value]
        output[value] = binary_metrics(bucket)
    return output


def length_slices(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    values = np.asarray([float(row.get("word_count") or 0) for row in rows], dtype=float)
    cuts = np.quantile(values, [0, 0.25, 0.5, 0.75, 1.0])
    output = {}
    for idx, name in enumerate(["q1_shortest", "q2", "q3", "q4_longest"]):
        lo, hi = cuts[idx], cuts[idx + 1]
        bucket = [row for row in rows if float(row.get("word_count") or 0) >= lo and (float(row.get("word_count") or 0) <= hi if idx == 3 else float(row.get("word_count") or 0) < hi)]
        output[name] = {"word_count_range": [float(lo), float(hi)], **binary_metrics(bucket)}
    return output


def score_distribution(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    scores = np.asarray([float(row[SCORE_NAME]) for row in rows], dtype=float)
    if len(scores) == 0:
        return {"count": 0}
    return {"count": int(len(scores)), "mean": float(np.mean(scores)), "std": float(np.std(scores)), "p05": float(np.quantile(scores, 0.05)), "p25": float(np.quantile(scores, 0.25)), "median": float(np.quantile(scores, 0.5)), "p75": float(np.quantile(scores, 0.75)), "p95": float(np.quantile(scores, 0.95))}


def domain_only_diagnostic(rows: Sequence[dict[str, Any]], domain_balance_proof: dict[str, Any] | None) -> dict[str, Any]:
    if domain_balance_proof and domain_balance_proof.get("exact_per_domain_era_balance"):
        return {"status": "STRUCTURAL_CHANCE", "roc_auc": 0.5, "reason": "Exact per-domain era balance means a domain-only lookup has chance ranking by construction; learned shortcut diagnostic is unnecessary."}
    labelled = [row for row in rows if row.get("label") is not None]
    labels = [int(row["label"]) for row in labelled]
    if len(set(labels)) < 2:
        return {"status": "N/A", "reason": "label support is insufficient"}
    vectorizer = DictVectorizer()
    x = vectorizer.fit_transform([{"source_domain_hash": str(row.get("source_domain_hash"))} for row in labelled])
    x.indices = x.indices.astype(np.int32, copy=False)
    x.indptr = x.indptr.astype(np.int32, copy=False)
    if len({row.get("source_domain_hash") for row in labelled}) < 2:
        clf: Any = DummyClassifier(strategy="prior")
    else:
        clf = LogisticRegression(class_weight="balanced", solver="liblinear", random_state=SEED)
    clf.fit(x, labels)
    scores = clf.predict_proba(x)[:, 1]
    return {"status": "reported", "roc_auc": float(roc_auc_score(labels, scores))}


def source_only_diagnostic(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    labelled = [row for row in rows if row.get("label") is not None]
    labels = [int(row["label"]) for row in labelled]
    source_keys = {row.get("source_key") for row in labelled if row.get("source_key")}
    if len(set(labels)) < 2:
        return {"status": "N/A", "reason": "label support is insufficient"}
    if len(source_keys) < 2:
        return {"status": "N/A", "reason": "source support is insufficient"}
    vectorizer = DictVectorizer()
    x = vectorizer.fit_transform([{"source_key": str(row.get("source_key"))} for row in labelled])
    x.indices = x.indices.astype(np.int32, copy=False)
    x.indptr = x.indptr.astype(np.int32, copy=False)
    clf = LogisticRegression(class_weight="balanced", solver="liblinear", random_state=SEED)
    clf.fit(x, labels)
    scores = clf.predict_proba(x)[:, 1]
    return {
        "status": "reported",
        "roc_auc": float(roc_auc_score(labels, scores)),
        "reason": "Source snapshot identity is era-linked in this external challenge; this diagnostic is reported as confound risk, not used as a runtime input.",
    }


def build_external_report(predictions: Sequence[dict[str, Any]], *, masked_rows: Sequence[dict[str, Any]], lane_name: str, request_manifest: dict[str, Any], model_metadata: dict[str, Any], corpus_manifest: dict[str, Any], domain_balance_proof: dict[str, Any] | None = None) -> dict[str, Any]:
    labelled = [row for row in predictions if row.get("label") is not None]
    masked_labelled = [row for row in masked_rows if row.get("label") is not None]
    overall = binary_metrics(labelled)
    masked = binary_metrics(masked_labelled)
    domain_only = domain_only_diagnostic(labelled, domain_balance_proof)
    source_only = source_only_diagnostic(labelled)
    counts = (corpus_manifest.get("lanes") or {}).get(lane_name, {}) if corpus_manifest else {}
    gates = {
        "balanced_accuracy_minimum": {"status": "PASS" if (overall.get("balanced_accuracy") or 0) >= 0.80 else "FAIL", "threshold": 0.80, "value": overall.get("balanced_accuracy")},
        "masked_roc_auc_minimum": {"status": "PASS" if (masked.get("roc_auc") or 0) >= 0.75 else "FAIL", "threshold": 0.75, "value": masked.get("roc_auc")},
        "date_axis": {"status": "PASS", "value": request_manifest.get("date_axis"), "policy": request_manifest.get("date_policy")},
        "source_diversity": {"status": "PASS" if len({row.get("source_key") for row in labelled if row.get("source_key")}) >= 2 or lane_name == "domain_matched_balanced" else "FAIL", "source_count": len({row.get("source_key") for row in labelled if row.get("source_key")})},
        "source_only_shortcut": source_only,
        "domain_only_shortcut": domain_only,
        "rights_privacy_public_safe": {"status": "PASS", "source_rights_status": SOURCE_RIGHTS_STATUS, "public_text_policy": "no raw article text, titles, descriptions, URLs, or previews"},
    }
    passable = all(value.get("status") in {"PASS", "N/A", "STRUCTURAL_CHANCE"} for value in gates.values()) and (overall.get("balanced_accuracy") or 0) >= 0.80
    report = {
        "schema": REPORT_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "lane_name": lane_name,
        "decision": "PASS" if passable else "HOLD",
        "decision_reason": "Frozen external lane passes thresholds and date/source/privacy gates." if passable else "Report held because one or more frozen external gates failed; do not call PASS below balanced accuracy 0.80 or failed date/source/privacy gates.",
        "model": {"model_id": FROZEN_MODEL_ID, "artifact_sha256": FROZEN_ARTIFACT_SHA256, "threshold": FROZEN_THRESHOLD, "metadata_model_id": model_metadata.get("model_id")},
        "source": {"sources": {key: {"repo_id": value["repo_id"], "revision": value["revision"], "filename": value["filename"], "license": value.get("license")} for key, value in SOURCES.items()}, "rights_status": SOURCE_RIGHTS_STATUS, "schema_fields": SOURCE_SCHEMA_FIELDS},
        "corpus": {"accepted_count": counts.get("accepted_count"), "counts_by_month": counts.get("counts_by_month"), "counts_by_role": counts.get("counts_by_role"), "source_domain_hash_count": counts.get("source_domain_hash_count")},
        "metrics": {"overall": overall, "masked": masked, "by_month": slice_metrics(labelled, "publication_year_month"), "by_role": slice_metrics(labelled, "corpus_role"), "missing_author": slice_metrics(labelled, "missing_author"), "length_quartiles": length_slices(labelled), "grouped_bootstrap_source_domain_roc_auc_95ci": grouped_bootstrap_auc(labelled)},
        "score_distribution": score_distribution(labelled),
        "domain_matched_balance_proof": domain_balance_proof,
        "gates": gates,
        "request_manifest_id": request_manifest.get("manifest_id"),
    }
    reject_public_text(report)
    assert_public_safe(report)
    return report


def checksum_manifest(paths: Sequence[Path], output_root: Path) -> dict[str, str]:
    files = {}
    resolved_root = output_root.resolve()
    for path in sorted({p for p in paths if p.exists() and p.is_file()}, key=str):
        try:
            relative = path.resolve().relative_to(resolved_root)
        except ValueError as exc:
            raise MultisourceExternalValidationError(f"checksum artifact is outside public root: {path}") from exc
        logical_path = (PUBLIC_ROOT / relative).as_posix()
        files[logical_path] = sha256_file(path)
    payload = {"schema": CHECKSUM_SCHEMA, "created_at": utc_now(), "files": files}
    write_public_json(output_root / "checksums.json", payload)
    (output_root / "checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(files.items())), encoding="utf-8")
    return files


def run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = read_json(args.manifest) if args.manifest and args.manifest.exists() else default_request_manifest()
    if args.write_default_manifest:
        write_public_json(args.write_default_manifest, manifest)
    result = collect_multisource_corpus(manifest, args.output_root, cross_dedupe_path=args.cross_dedupe, max_rows_per_source=args.max_rows_per_source)
    lanes = {"all_valid_source_diverse": result["all_valid_source_diverse"], "domain_matched_balanced": result["domain_matched_balanced"]}
    corpus_manifest = build_public_corpus_manifest(lanes=lanes, request_manifest=manifest, rejected_counts=result["rejected_counts"], duplicate_counts=result["duplicate_counts"], source_files=result["source_files"], cross_dedupe_reference=CROSS_DEDUPE_LOGICAL_REFERENCE if args.cross_dedupe else None, domain_balance_proof=result["domain_balance_proof"])
    write_public_json(args.request_manifest_output, manifest)
    write_public_json(args.corpus_manifest_output, corpus_manifest)
    artifact_sha = sha256_file(args.model_artifact)
    artifact = joblib.load(args.model_artifact)
    metadata = read_json(args.model_metadata)
    verify_frozen_model_identity(artifact, metadata, artifact_sha256=artifact_sha)
    model = artifact["model"]
    outputs: dict[str, Any] = {"corpus_manifest": corpus_manifest, "reports": {}}
    checksum_paths = [args.request_manifest_output, args.corpus_manifest_output]
    for lane_name, rows in lanes.items():
        predictions = score_rows(model, rows, masked=False)
        masked_predictions = score_rows(model, rows, masked=True)
        lane_dir = args.public_root / lane_name
        pred_path = lane_dir / "predictions.jsonl"
        masked_path = lane_dir / "masked_predictions.jsonl"
        report_path = lane_dir / "report.json"
        write_jsonl_public(pred_path, predictions)
        write_jsonl_public(masked_path, masked_predictions)
        proof = result["domain_balance_proof"] if lane_name == "domain_matched_balanced" else None
        report = build_external_report(predictions, masked_rows=masked_predictions, lane_name=lane_name, request_manifest=manifest, model_metadata=metadata, corpus_manifest=corpus_manifest, domain_balance_proof=proof)
        write_public_json(report_path, report)
        outputs["reports"][lane_name] = report
        checksum_paths.extend([pred_path, masked_path, report_path])
    outputs["checksums"] = checksum_manifest(checksum_paths, args.public_root)
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--write-default-manifest", type=Path)
    parser.add_argument("--output-root", type=Path, default=PRIVATE_ROOT)
    parser.add_argument("--public-root", type=Path, default=PUBLIC_ROOT)
    parser.add_argument("--request-manifest-output", type=Path, default=PUBLIC_ROOT / "request_manifest.json")
    parser.add_argument("--corpus-manifest-output", type=Path, default=PUBLIC_ROOT / "corpus_manifest.json")
    parser.add_argument("--cross-dedupe", type=Path, default=default_cross_dedupe_path(), help=f"Private INFINI rows; override with ${CROSS_DEDUPE_ENV_VAR}.")
    parser.add_argument("--model-artifact", type=Path, default=FROZEN_ARTIFACT_PATH)
    parser.add_argument("--model-metadata", type=Path, default=FROZEN_METADATA_PATH)
    parser.add_argument("--max-rows-per-source", type=int, default=None, help="Test/pilot throttle; omit for sealed full collection.")
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({"lanes": {name: report["decision"] for name, report in result["reports"].items()}, "accepted": {name: lane["accepted_count"] for name, lane in result["corpus_manifest"]["lanes"].items()}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
