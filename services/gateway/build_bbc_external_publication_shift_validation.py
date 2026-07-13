#!/usr/bin/env python3
"""Build and score the sealed BBC external publication-shift challenge.

BBC raw text is local/private only. Public artifacts contain hashes, IDs,
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
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss, f1_score, roc_auc_score

from train_infini_news_publication_shift_candidates import assert_public_safe, mask_content

SOURCE_REPO_ID = "RealTimeData/bbc_news_alltime"
SOURCE_REVISION = "8dd1ecdc92ac43f9c04a3da3e945537dbb08179b"
SOURCE_REVISION_URL = f"https://huggingface.co/datasets/{SOURCE_REPO_ID}/tree/{SOURCE_REVISION}"
SOURCE_SCHEMA_FIELDS = ["content", "published_date", "link", "section", "authors"]
SOURCE_RIGHTS_STATUS = "HOLD_no_explicit_license_public_no_text_only"
REQUEST_SCHEMA = "publication_shift.bbc_external_request_manifest.v1"
CORPUS_SCHEMA = "publication_shift.bbc_external_corpus.v1"
PUBLIC_CORPUS_SCHEMA = "publication_shift.bbc_external_public_manifest.v1"
REPORT_SCHEMA = "publication_shift.bbc_external_report.v1"
JAN_DIAGNOSTIC_SCHEMA = "publication_shift.infini_news_january_2024_diagnostic.v1"
CHECKSUM_SCHEMA = "publication_shift.bbc_external_checksums.v1"
DISCLAIMER = "This score does not establish AI authorship."
PRIVATE_ROOT = Path("services/data/publication_shift/bbc_external_v1")
PUBLIC_ROOT = Path("services/evals/publication_shift_model/bbc_external_v1")
FROZEN_ARTIFACT_PATH = Path("services/gateway/model_artifacts/publication_shift/infini_news_v1/infini_news_word_char_tfidf_logistic.joblib")
FROZEN_METADATA_PATH = Path("services/evals/publication_shift_model/infini_news_v1/candidates/lexical_tfidf_logistic/model_metadata.json")
FROZEN_PREDICTIONS_PATH = Path("services/evals/publication_shift_model/infini_news_v1/candidates/lexical_tfidf_logistic/publisher_domain_heldout_primary_predictions.jsonl")
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
PUBLIC_BANNED_KEYS = {"content", "normalized_text", "original_text", "text", "body", "title", "description", "preview", "url", "link", "top_image", "normalized_url"}
SCORE_NAME = "current_era_similarity"
SEED = 20260713


class BbcExternalValidationError(RuntimeError):
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


def year_months(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    output = []
    while (year, month) <= (end_year, end_month):
        output.append(f"{year}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return output


def default_request_manifest(*, include_2022: bool = True) -> dict[str, Any]:
    targets: dict[str, int] = {}
    for month in year_months("2018-01", "2021-12"):
        targets[month] = 250
    for month in year_months("2023-01", "2025-06"):
        targets[month] = 400
    transition = {month: 250 for month in year_months("2022-01", "2022-12")} if include_2022 else {}
    return {
        "schema": REQUEST_SCHEMA,
        "manifest_id": "bbc_external_v1_24000_plus_2022" if include_2022 else "bbc_external_v1_24000",
        "created_at": "2026-07-13T00:00:00Z",
        "source_repo_id": SOURCE_REPO_ID,
        "source_revision": SOURCE_REVISION,
        "source_revision_url": SOURCE_REVISION_URL,
        "source_schema_fields": SOURCE_SCHEMA_FIELDS,
        "source_rights_status": SOURCE_RIGHTS_STATUS,
        "source_license": None,
        "source_license_note": "Dataset card has no explicit license; raw BBC text remains local/private and redistribution rights are HOLD.",
        "date_axis": "published_date_only",
        "partition_date_policy": "reject_partition_mismatch_do_not_substitute",
        "minimum_words": 150,
        "target_core_rows": sum(targets.values()),
        "targets_by_month": targets,
        "evaluation_only_targets_by_month": transition,
        "targets_by_role": {"pre_llm_core": 12_000, "current_core": 12_000, "transition_2022": sum(transition.values())},
        "sample_seed": SEED,
        "public_artifact_policy": "no_text_no_titles_no_descriptions_no_urls_hashes_counts_metadata_only",
        "external_source_note": "BBC alltime monthly article dataset, independent of INFINI and OpenAlex; one publisher only.",
        "disclaimer": DISCLAIMER,
    }


def load_request_manifest(path: Path | None, *, include_2022: bool) -> dict[str, Any]:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_request_manifest(include_2022=include_2022)


def parse_date(value: Any) -> dt.date:
    if not isinstance(value, str) or not value.strip():
        raise BbcExternalValidationError("published_date is missing")
    try:
        return dt.date.fromisoformat(value.strip()[:10])
    except ValueError as exc:
        raise BbcExternalValidationError("published_date is invalid") from exc


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def word_count(value: str) -> int:
    return len(re.findall(r"\b\S+\b", value))


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        raise BbcExternalValidationError("link hostname is missing")
    path = re.sub(r"/+$", "", parsed.path or "/")
    query_pairs = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
            continue
        query_pairs.append((key, value))
    query = urllib.parse.urlencode(sorted(query_pairs), doseq=True)
    return urllib.parse.urlunsplit((scheme, host, path, query, ""))


def source_domain(normalized_url: str) -> str:
    host = urllib.parse.urlsplit(normalized_url).hostname or ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2:] == ["co", "uk"]:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def role_and_label(year: int, month: int) -> tuple[str, int | None] | None:
    ym = f"{year}-{month:02d}"
    if "2018-01" <= ym <= "2021-12":
        return "pre_llm_core", 0
    if "2022-01" <= ym <= "2022-12":
        return "transition_2022", None
    if "2023-01" <= ym <= "2025-06":
        return "current_core", 1
    return None


def near_duplicate_cluster(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    shingles = {" ".join(words[index : index + 5]) for index in range(max(0, len(words) - 4))}
    if not shingles:
        shingles = {" ".join(words)}
    source = "|".join(sorted(stable_hash(shingle, 32) for shingle in shingles)[:24])
    return "ndc_" + stable_hash(source, 20)


def require_str(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BbcExternalValidationError(f"{key} is missing")
    return value.strip()


def normalize_bbc_row(row: dict[str, Any], *, config_month: str, row_index: int, retrieved_at: str) -> dict[str, Any]:
    published = parse_date(row.get("published_date"))
    published_ym = f"{published.year}-{published.month:02d}"
    if published_ym != config_month:
        raise BbcExternalValidationError(f"partition mismatch: config {config_month} row published_date {published_ym}")
    assigned = role_and_label(published.year, published.month)
    if assigned is None:
        raise BbcExternalValidationError("published_date is outside requested windows")
    content = normalize_text(require_str(row, "content"))
    words = word_count(content)
    if words < 150:
        raise BbcExternalValidationError("content has fewer than 150 words")
    link = require_str(row, "link")
    normalized_url = normalize_url(link)
    domain = source_domain(normalized_url)
    role, label = assigned
    text_hash = sha256_text(content)
    identity = "|".join([SOURCE_REVISION, config_month, link, str(row_index), text_hash])
    authors = str(row.get("authors") or "").strip()
    section = str(row.get("section") or "missing").strip() or "missing"
    return {
        "schema": CORPUS_SCHEMA,
        "document_id": "bbc_external_" + stable_hash(identity, 24),
        "source_repo_id": SOURCE_REPO_ID,
        "source_revision": SOURCE_REVISION,
        "source_config_month": config_month,
        "source_row_index": row_index,
        "source_domain": domain,
        "source_domain_hash": sha256_text(domain),
        "source_publisher": "BBC",
        "source_publisher_hash": sha256_text("BBC"),
        "link_hash": sha256_text(link),
        "normalized_url_hash": sha256_text(normalized_url),
        "identity_hash": sha256_text(identity),
        "published_date": published.isoformat(),
        "publication_date": published.isoformat(),
        "publication_year": published.year,
        "publication_month": published.month,
        "publication_year_month": published_ym,
        "section": section,
        "section_hash": sha256_text(section.lower()),
        "author_hash": sha256_text(authors.lower()) if authors else None,
        "missing_author": not bool(authors),
        "normalized_text": content,
        "normalized_text_sha256": text_hash,
        "near_duplicate_cluster_id": near_duplicate_cluster(content),
        "word_count": words,
        "corpus_role": role,
        "label": label,
        "retrieved_at": retrieved_at,
        "rights_status": SOURCE_RIGHTS_STATUS,
    }


def public_record(row: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "document_id", "source_repo_id", "source_revision", "source_config_month", "source_row_index",
        "source_domain_hash", "source_publisher_hash", "link_hash", "normalized_url_hash", "identity_hash",
        "published_date", "publication_date", "publication_year", "publication_month", "publication_year_month",
        "section", "section_hash", "author_hash", "missing_author", "normalized_text_sha256",
        "near_duplicate_cluster_id", "word_count", "corpus_role", "label", "retrieved_at", "rights_status",
    }
    return {key: row.get(key) for key in sorted(allowed) if key in row}


def reject_public_text(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        data_value_paths = {"/counts_by_section", "/counts_by_month", "/counts_by_role"}
        for key, value in payload.items():
            lowered = str(key).lower()
            if path not in data_value_paths and (lowered in PUBLIC_BANNED_KEYS or "preview" in lowered or lowered.endswith("text")):
                raise BbcExternalValidationError(f"public artifact contains forbidden text key {path}/{key}")
            reject_public_text(value, f"{path}/{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            reject_public_text(item, f"{path}[{index}]")


def write_public_json(path: Path, payload: Any) -> None:
    reject_public_text(payload)
    assert_public_safe(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    for row in sorted(records, key=lambda item: (item["publication_date"], item["document_id"])):
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


def select_month(rows: Sequence[dict[str, Any]], month: str, target: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    candidates = [row for row in rows if row["publication_year_month"] == month]
    ordered = sorted(candidates, key=lambda row: (stable_hash(f"{seed}|{month}|{row['document_id']}", 32), row["document_id"]))
    selected = sorted(ordered[:target], key=lambda row: (row["publication_date"], row["document_id"]))
    rejected = {"month_quota_shortfall": target - len(selected)} if len(selected) < target else {}
    return selected, rejected


def hub_source_files(months: Iterable[str]) -> list[dict[str, Any]]:
    api = HfApi()
    info = api.repo_info(repo_id=SOURCE_REPO_ID, repo_type="dataset", revision=SOURCE_REVISION, files_metadata=True)
    if info.sha != SOURCE_REVISION:
        raise BbcExternalValidationError(f"resolved revision {info.sha} did not match {SOURCE_REVISION}")
    wanted = set(months)
    files = []
    for sibling in info.siblings:
        path = sibling.rfilename
        config = path.split("/", 1)[0]
        if config not in wanted or not path.endswith(".parquet"):
            continue
        lfs = getattr(sibling, "lfs", None)
        files.append({"path": path, "config_month": config, "size": getattr(sibling, "size", None), "lfs_sha256": getattr(lfs, "sha256", None) if lfs else None})
    return sorted(files, key=lambda item: item["path"])


def iter_source_rows(source_file: dict[str, Any]) -> Iterable[tuple[int, dict[str, Any]]]:
    local = hf_hub_download(repo_id=SOURCE_REPO_ID, repo_type="dataset", revision=SOURCE_REVISION, filename=source_file["path"])
    parquet = pq.ParquetFile(local)
    row_index = 0
    columns = [col for col in SOURCE_SCHEMA_FIELDS if col in parquet.schema.names]
    for batch in parquet.iter_batches(batch_size=2048, columns=columns):
        for row in batch.to_pylist():
            yield row_index, row
            row_index += 1


def collect_bbc_corpus(manifest: dict[str, Any], output_root: Path, *, cross_dedupe_path: Path | None = None, max_rows_per_month: int | None = None) -> dict[str, Any]:
    if manifest.get("source_revision") != SOURCE_REVISION:
        raise BbcExternalValidationError("manifest source_revision mismatch")
    targets = dict(manifest["targets_by_month"])
    eval_targets = dict(manifest.get("evaluation_only_targets_by_month") or {})
    all_targets = {**targets, **eval_targets}
    source_files = hub_source_files(all_targets)
    by_month_files = {item["config_month"]: item for item in source_files}
    retrieved_at = utc_now()
    rejected = Counter()
    normalized: list[dict[str, Any]] = []
    for month, target in sorted(all_targets.items()):
        source_file = by_month_files.get(month)
        if source_file is None:
            rejected["missing_source_config"] += int(target)
            continue
        month_rows = []
        rows_seen = 0
        for row_index, raw in iter_source_rows(source_file):
            rows_seen += 1
            try:
                month_rows.append(normalize_bbc_row(raw, config_month=month, row_index=row_index, retrieved_at=retrieved_at))
            except BbcExternalValidationError as exc:
                rejected[rejection_code(str(exc))] += 1
            if max_rows_per_month is not None and rows_seen >= max_rows_per_month:
                break
        selected, month_rejections = select_month(month_rows, month, int(target), int(manifest.get("sample_seed", SEED)))
        rejected.update(month_rejections)
        normalized.extend(selected)
    cross = load_cross_dedupe(cross_dedupe_path)
    deduped, duplicate_counts = dedupe_records(normalized, cross)
    write_private_jsonl(output_root / "normalized_rows.jsonl", deduped)
    return {"records": deduped, "rejected_counts": dict(sorted(rejected.items())), "duplicate_counts": duplicate_counts, "source_files": source_files, "output_root": str(output_root)}


def rejection_code(message: str) -> str:
    lowered = message.lower()
    if "partition mismatch" in lowered:
        return "partition_mismatch"
    if "150 words" in lowered:
        return "too_short"
    if "published_date" in lowered:
        return "invalid_published_date"
    if "link" in lowered:
        return "invalid_link"
    if "content" in lowered:
        return "invalid_content"
    return "schema_rejected"


def count_by(rows: Sequence[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key)) for row in rows).items()))


def build_public_corpus_manifest(records: Sequence[dict[str, Any]], *, request_manifest: dict[str, Any], rejected_counts: dict[str, int], duplicate_counts: dict[str, int], source_files: Sequence[dict[str, Any]], cross_dedupe_path: str | None) -> dict[str, Any]:
    public = {
        "schema": PUBLIC_CORPUS_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "source_repo_id": SOURCE_REPO_ID,
        "source_revision": SOURCE_REVISION,
        "source_revision_url": SOURCE_REVISION_URL,
        "source_schema_fields": SOURCE_SCHEMA_FIELDS,
        "source_rights_status": SOURCE_RIGHTS_STATUS,
        "source_license": None,
        "date_axis": "published_date_only",
        "partition_date_policy": "reject_partition_mismatch_do_not_substitute",
        "request_manifest_id": request_manifest.get("manifest_id"),
        "target_core_rows": request_manifest.get("target_core_rows"),
        "accepted_count": len(records),
        "counts_by_month": count_by(records, "publication_year_month"),
        "counts_by_role": count_by(records, "corpus_role"),
        "counts_by_section": count_by(records, "section"),
        "rejected_counts": dict(sorted(rejected_counts.items())),
        "duplicate_counts": dict(sorted(duplicate_counts.items())),
        "cross_dedupe_private_path": cross_dedupe_path,
        "source_files": sorted(source_files, key=lambda item: item["path"]),
        "records": [public_record(row) for row in sorted(records, key=lambda item: (item["publication_date"], item["document_id"]))],
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
            raise BbcExternalValidationError(f"frozen {name} mismatch: {actual!r} != {expected!r}")


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


def source_only_auc_status(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    publishers = {row.get("source_publisher_hash") for row in rows if row.get("source_publisher_hash")}
    if len(publishers) <= 1:
        return {"status": "N/A", "reason": "BBC external challenge has one publisher; source-only shortcut is not statistically supported."}
    domains = {row.get("source_domain_hash") for row in rows}
    if len(domains) <= 1:
        return {"status": "N/A", "reason": "BBC external challenge has one publisher/domain; source-only shortcut is not statistically supported."}
    labelled = [row for row in rows if row.get("label") is not None]
    labels = [int(row["label"]) for row in labelled]
    if len(set(labels)) < 2:
        return {"status": "N/A", "reason": "label support is insufficient"}
    vectorizer = DictVectorizer()
    x = vectorizer.fit_transform([{"source_domain_hash": str(row.get("source_domain_hash"))} for row in labelled])
    x.indices = x.indices.astype(np.int32, copy=False)
    x.indptr = x.indptr.astype(np.int32, copy=False)
    clf = LogisticRegression(class_weight="balanced", solver="liblinear", random_state=SEED)
    clf.fit(x, labels)
    scores = clf.predict_proba(x)[:, 1]
    return {"status": "reported", "roc_auc": float(roc_auc_score(labels, scores))}


def build_external_report(predictions: Sequence[dict[str, Any]], *, masked_rows: Sequence[dict[str, Any]], request_manifest: dict[str, Any], model_metadata: dict[str, Any], corpus_manifest: dict[str, Any]) -> dict[str, Any]:
    labelled = [row for row in predictions if row.get("label") is not None]
    masked_labelled = [row for row in masked_rows if row.get("label") is not None]
    overall = binary_metrics(labelled)
    masked = binary_metrics(masked_labelled)
    source_only = source_only_auc_status(labelled)
    gates = {
        "roc_auc_minimum": {"status": "PASS" if (overall.get("roc_auc") or 0) >= 0.85 else "FAIL", "threshold": 0.85, "value": overall.get("roc_auc")},
        "balanced_accuracy_minimum": {"status": "PASS" if (overall.get("balanced_accuracy") or 0) >= 0.80 else "FAIL", "threshold": 0.80, "value": overall.get("balanced_accuracy")},
        "masked_roc_auc_minimum": {"status": "PASS" if (masked.get("roc_auc") or 0) >= 0.75 else "FAIL", "threshold": 0.75, "value": masked.get("roc_auc")},
        "pre_llm_fpr_maximum": {"status": "PASS" if (overall.get("false_positive_rate") or 1) <= 0.15 else "FAIL", "threshold": 0.15, "value": overall.get("false_positive_rate")},
        "source_only_shortcut": source_only,
        "source_diversity": {"status": "N/A", "reason": "BBC is one publisher; do not call this a multisource PASS."},
        "rights_privacy_public_safe": {"status": "PASS", "source_rights_status": SOURCE_RIGHTS_STATUS, "public_text_policy": "no raw article text, titles, descriptions, URLs, or previews"},
    }
    passable = all(value.get("status") in {"PASS", "N/A"} for value in gates.values()) and gates["source_diversity"]["status"] != "N/A"
    report = {
        "schema": REPORT_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "decision": "PASS" if passable else "HOLD",
        "decision_reason": "Single-publisher BBC external validation cannot satisfy source-diversity/source-only PASS gates; report as HOLD even if metric thresholds pass.",
        "model": {"model_id": FROZEN_MODEL_ID, "artifact_sha256": FROZEN_ARTIFACT_SHA256, "threshold": FROZEN_THRESHOLD, "metadata_model_id": model_metadata.get("model_id")},
        "source": {"repo_id": SOURCE_REPO_ID, "revision": SOURCE_REVISION, "rights_status": SOURCE_RIGHTS_STATUS, "schema_fields": SOURCE_SCHEMA_FIELDS},
        "corpus": {"accepted_count": corpus_manifest.get("accepted_count"), "counts_by_month": corpus_manifest.get("counts_by_month"), "counts_by_role": corpus_manifest.get("counts_by_role")},
        "metrics": {"overall": overall, "masked": masked, "by_month": slice_metrics(labelled, "publication_year_month"), "by_role": slice_metrics(labelled, "corpus_role"), "by_section": slice_metrics(labelled, "section"), "missing_author": slice_metrics(labelled, "missing_author"), "length_quartiles": length_slices(labelled), "grouped_bootstrap_source_domain_roc_auc_95ci": grouped_bootstrap_auc(labelled)},
        "evaluation_only": {"transition_2022": score_distribution([row for row in predictions if row.get("corpus_role") == "transition_2022"])},
        "gates": gates,
        "request_manifest_id": request_manifest.get("manifest_id"),
    }
    reject_public_text(report)
    assert_public_safe(report)
    return report


def score_distribution(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    scores = np.asarray([float(row[SCORE_NAME]) for row in rows], dtype=float)
    if len(scores) == 0:
        return {"count": 0}
    return {"count": int(len(scores)), "mean": float(np.mean(scores)), "std": float(np.std(scores)), "p05": float(np.quantile(scores, 0.05)), "p25": float(np.quantile(scores, 0.25)), "median": float(np.quantile(scores, 0.5)), "p75": float(np.quantile(scores, 0.75)), "p95": float(np.quantile(scores, 0.95))}


def january_2024_diagnostic(predictions_path: Path, *, threshold: float = FROZEN_THRESHOLD) -> dict[str, Any]:
    rows = read_jsonl(predictions_path)
    def in_window(row: dict[str, Any], name: str) -> bool:
        y, m = row.get("publication_year"), row.get("publication_month")
        if name == "december_2023":
            return y == 2023 and m == 12
        if name == "january_2024":
            return y == 2024 and m == 1
        if name == "february_2024":
            return y == 2024 and m == 2
        if name == "remainder_2024":
            return y == 2024 and m != 1
        if name == "overall_test":
            return True
        return False
    def window_summary(name: str) -> dict[str, Any]:
        bucket = [row for row in rows if in_window(row, name)]
        out = diagnostic_metrics(bucket, threshold)
        out["error_concentration"] = error_concentration(bucket, threshold)
        return out
    diagnostic = {
        "schema": JAN_DIAGNOSTIC_SCHEMA,
        "created_at": utc_now(),
        "disclaimer": DISCLAIMER,
        "model_id": FROZEN_MODEL_ID,
        "threshold": threshold,
        "source_predictions": str(predictions_path),
        "interpretation": "diagnostic_only_no_model_selection_or_tuning",
        "windows": {name: window_summary(name) for name in ["december_2023", "january_2024", "february_2024", "remainder_2024", "overall_test"]},
    }
    reject_public_text(diagnostic)
    assert_public_safe(diagnostic)
    return diagnostic


def diagnostic_metrics(rows: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    labelled = [row for row in rows if row.get("label") is not None]
    if not labelled:
        return {"count": 0, "accuracy": None, "error_count": 0}
    correct = [((float(row[SCORE_NAME]) >= threshold) == bool(row["label"])) for row in labelled]
    return {"count": len(labelled), "accuracy": float(sum(correct) / len(correct)), "error_count": int(len(correct) - sum(correct)), "score_distribution": score_distribution(labelled)}


def error_concentration(rows: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    errors = [row for row in rows if row.get("label") is not None and ((float(row[SCORE_NAME]) >= threshold) != bool(row["label"]))]
    return {
        "by_source_hash": top_counts(errors, "url_hostname_hash"),
        "by_topic": top_counts(errors, "topic"),
        "by_missing_author": top_counts(errors, "author_hash", missing_label="missing_author"),
        "by_duplicate_cluster": top_counts(errors, "near_duplicate_cluster_id"),
        "by_length_band": top_length_counts(errors),
    }


def top_counts(rows: Sequence[dict[str, Any]], key: str, *, missing_label: str = "missing") -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or missing_label) for row in rows)
    return [{"value_hash": stable_hash(value, 24), "count": count} for value, count in counts.most_common(20)]


def top_length_counts(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    def band(row: dict[str, Any]) -> str:
        wc = int(row.get("word_count") or 0)
        if wc < 300:
            return "150_299"
        if wc < 600:
            return "300_599"
        return "600_plus"
    counts = Counter(band(row) for row in rows)
    return [{"band": value, "count": count} for value, count in counts.most_common()]


def checksum_manifest(paths: Sequence[Path], output_root: Path) -> dict[str, str]:
    files = {}
    for path in sorted({p for p in paths if p.exists() and p.is_file()}, key=str):
        files[str(path)] = sha256_file(path)
    payload = {"schema": CHECKSUM_SCHEMA, "created_at": utc_now(), "files": files}
    write_public_json(output_root / "checksums.json", payload)
    (output_root / "checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(files.items())), encoding="utf-8")
    return files


def run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_request_manifest(args.manifest, include_2022=not args.no_2022)
    if args.write_default_manifest:
        write_public_json(args.write_default_manifest, manifest)
    result = collect_bbc_corpus(manifest, args.output_root, cross_dedupe_path=args.cross_dedupe, max_rows_per_month=args.max_rows_per_month)
    corpus_manifest = build_public_corpus_manifest(result["records"], request_manifest=manifest, rejected_counts=result["rejected_counts"], duplicate_counts=result["duplicate_counts"], source_files=result["source_files"], cross_dedupe_path=str(args.cross_dedupe) if args.cross_dedupe else None)
    write_public_json(args.request_manifest_output, manifest)
    write_public_json(args.corpus_manifest_output, corpus_manifest)
    artifact_sha = sha256_file(args.model_artifact)
    artifact = joblib.load(args.model_artifact)
    metadata = read_json(args.model_metadata)
    verify_frozen_model_identity(artifact, metadata, artifact_sha256=artifact_sha)
    model = artifact["model"]
    predictions = score_rows(model, result["records"], masked=False)
    masked_predictions = score_rows(model, result["records"], masked=True)
    write_jsonl_public(args.predictions_output, predictions)
    write_jsonl_public(args.masked_predictions_output, masked_predictions)
    report = build_external_report(predictions, masked_rows=masked_predictions, request_manifest=manifest, model_metadata=metadata, corpus_manifest=corpus_manifest)
    write_public_json(args.report_output, report)
    jan = january_2024_diagnostic(args.infini_predictions, threshold=FROZEN_THRESHOLD)
    write_public_json(args.january_diagnostic_output, jan)
    checksums = checksum_manifest([args.request_manifest_output, args.corpus_manifest_output, args.predictions_output, args.masked_predictions_output, args.report_output, args.january_diagnostic_output], args.public_root)
    return {"corpus_manifest": corpus_manifest, "report": report, "january_2024_diagnostic": jan, "checksums": checksums}


def write_jsonl_public(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            reject_public_text(row)
            assert_public_safe(row)
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--write-default-manifest", type=Path)
    parser.add_argument("--no-2022", action="store_true")
    parser.add_argument("--output-root", type=Path, default=PRIVATE_ROOT)
    parser.add_argument("--public-root", type=Path, default=PUBLIC_ROOT)
    parser.add_argument("--request-manifest-output", type=Path, default=PUBLIC_ROOT / "request_manifest.json")
    parser.add_argument("--corpus-manifest-output", type=Path, default=PUBLIC_ROOT / "corpus_manifest.json")
    parser.add_argument("--predictions-output", type=Path, default=PUBLIC_ROOT / "predictions.jsonl")
    parser.add_argument("--masked-predictions-output", type=Path, default=PUBLIC_ROOT / "masked_predictions.jsonl")
    parser.add_argument("--report-output", type=Path, default=PUBLIC_ROOT / "report.json")
    parser.add_argument("--january-diagnostic-output", type=Path, default=PUBLIC_ROOT / "january_2024_diagnostic.json")
    parser.add_argument("--cross-dedupe", type=Path, default=Path("/home/ryan/toslop-model/.worktrees/temporal-publication-shift/services/data/publication_shift/infini_news_v1/normalized_rows.jsonl"))
    parser.add_argument("--model-artifact", type=Path, default=FROZEN_ARTIFACT_PATH)
    parser.add_argument("--model-metadata", type=Path, default=FROZEN_METADATA_PATH)
    parser.add_argument("--infini-predictions", type=Path, default=FROZEN_PREDICTIONS_PATH)
    parser.add_argument("--max-rows-per-month", type=int, default=None, help="Test/pilot throttle; omit for sealed full collection.")
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({"decision": result["report"]["decision"], "accepted_count": result["corpus_manifest"]["accepted_count"], "january_2024_accuracy": result["january_2024_diagnostic"]["windows"]["january_2024"]["accuracy"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
