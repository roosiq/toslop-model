#!/usr/bin/env python3
"""Train INFINI-NEWS publication-shift lexical and stylometric candidates.

The score estimates similarity to matched current-era publication language.
This score does not establish AI authorship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import joblib
import lightgbm as lgb
import numpy as np
import scipy
import sklearn
from build_publication_shift_splits import build_infini_news_protocols, protocol_summary, stable_json_sha256
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, f1_score, roc_auc_score
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import StandardScaler

SEED = 20260712
DISCLAIMER = "This score does not establish AI authorship."
SCORE_NAME = "current_era_similarity"
CORE_ROLES = {"pre_llm_core": 0, "current_core": 1}
TEXT_FIELD = "normalized_text"
FORBIDDEN_OUTPUT_KEYS = {
    "original_text",
    "normalized_text",
    "text",
    "title",
    "description",
    "preview",
    "body",
    "content",
    "url",
    "normalized_url",
    "warc_target_uri",
}
FUNCTION_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "any", "as", "at", "be", "because", "been", "but", "by", "can", "could", "do", "for", "from", "had", "has", "have", "he", "her", "his", "if", "in", "into", "is", "it", "its", "may", "more", "not", "of", "on", "or", "our", "she", "should", "so", "such", "than", "that", "the", "their", "there", "these", "they", "this", "to", "was", "we", "were", "which", "who", "will", "with", "would", "you",
}
PUBLIC_METADATA_FIELDS = ["url_hostname", "sitename", "topic", "author_hash", "publication_year", "publication_month"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit is not None and len(rows) >= limit:
                    break
    return rows


def read_jsonl_balanced_by_role(path: Path, *, limit_per_role: int | None = None) -> list[dict[str, Any]]:
    if limit_per_role is None:
        return read_jsonl(path)
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            role = str(row.get("corpus_role"))
            if counts[role] >= limit_per_role:
                continue
            rows.append(row)
            counts[role] += 1
    return rows


def default_lexical_config() -> dict[str, Any]:
    return {
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
        "random_seed": SEED,
    }


def default_stylometric_config() -> dict[str, Any]:
    return {
        "boosting_type": "gbdt",
        "objective": "binary",
        "n_estimators": 450,
        "learning_rate": 0.035,
        "num_leaves": 31,
        "max_depth": -1,
        "min_child_samples": 80,
        "subsample": 0.85,
        "subsample_freq": 1,
        "colsample_bytree": 0.9,
        "reg_alpha": 0.05,
        "reg_lambda": 0.1,
        "class_weight": "balanced",
        "random_state": SEED,
        "n_jobs": max(1, min(8, os.cpu_count() or 1)),
        "deterministic": True,
        "force_col_wise": True,
        "verbosity": -1,
    }


def build_lexical_features(config: dict[str, Any]) -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=tuple(config["word_ngram_range"]),
                    min_df=config["min_df"],
                    max_df=config["max_df"],
                    max_features=config["word_max_features"],
                    sublinear_tf=True,
                    strip_accents="unicode",
                    dtype=np.float32,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=tuple(config["char_ngram_range"]),
                    min_df=config["min_df"],
                    max_df=config["max_df"],
                    max_features=config["char_max_features"],
                    sublinear_tf=True,
                    dtype=np.float32,
                ),
            ),
        ]
    )


def fit_lexical(texts: list[str], labels: list[int], config: dict[str, Any]) -> dict[str, Any]:
    features = build_lexical_features(config)
    matrix = features.fit_transform(texts)
    classifier = LogisticRegression(
        class_weight=config["class_weight"],
        solver=config["solver"],
        C=float(config["C"]),
        max_iter=int(config["max_iter"]),
        random_state=int(config["random_seed"]),
    )
    classifier.fit(matrix, np.asarray(labels, dtype=np.int8))
    return {"features": features, "classifier": classifier}


def lexical_scores(model: dict[str, Any], texts: list[str], batch_size: int = 2048) -> np.ndarray:
    outputs: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        matrix = model["features"].transform(texts[start : start + batch_size])
        outputs.append(model["classifier"].predict_proba(matrix)[:, 1])
    return np.concatenate(outputs) if outputs else np.asarray([], dtype=float)


def stylometric_feature_names() -> list[str]:
    names = [
        "char_count", "word_count", "unique_word_ratio", "mean_word_len", "std_word_len", "sentence_count", "mean_sentence_words", "std_sentence_words", "paragraph_count", "mean_paragraph_words", "comma_per_1k", "semicolon_per_1k", "colon_per_1k", "dash_per_1k", "quote_per_1k", "paren_per_1k", "question_per_1k", "exclamation_per_1k", "digit_char_ratio", "uppercase_token_ratio", "titlecase_token_ratio", "function_word_ratio", "first_person_ratio", "third_person_ratio", "numeric_token_ratio", "long_word_ratio", "short_word_ratio", "repeated_bigram_ratio",
    ]
    return names


def stylometric_vector(text: str) -> list[float]:
    words = re.findall(r"[A-Za-z0-9']+", text)
    lower = [word.lower() for word in words]
    lengths = np.asarray([len(word) for word in words], dtype=float) if words else np.asarray([0.0])
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_lengths = np.asarray([len(re.findall(r"[A-Za-z0-9']+", s)) for s in sentences], dtype=float) if sentences else np.asarray([0.0])
    paragraphs = [p for p in re.split(r"\n\s*\n+", text) if p.strip()]
    paragraph_lengths = np.asarray([len(re.findall(r"[A-Za-z0-9']+", p)) for p in paragraphs], dtype=float) if paragraphs else np.asarray([0.0])
    word_count = max(1, len(words))
    char_count = max(1, len(text))
    bigrams = list(zip(lower, lower[1:]))
    repeated_bigram_ratio = 0.0 if not bigrams else 1.0 - (len(set(bigrams)) / len(bigrams))
    first_person = {"i", "me", "my", "mine", "we", "us", "our", "ours"}
    third_person = {"he", "him", "his", "she", "her", "hers", "they", "them", "their", "theirs"}
    return [
        float(len(text)),
        float(len(words)),
        float(len(set(lower)) / word_count),
        float(np.mean(lengths)),
        float(np.std(lengths)),
        float(len(sentences)),
        float(np.mean(sentence_lengths)),
        float(np.std(sentence_lengths)),
        float(len(paragraphs)),
        float(np.mean(paragraph_lengths)),
        1000.0 * text.count(",") / char_count,
        1000.0 * text.count(";") / char_count,
        1000.0 * text.count(":") / char_count,
        1000.0 * (text.count("-") + text.count("—")) / char_count,
        1000.0 * (text.count('"') + text.count("“") + text.count("”") + text.count("'")) / char_count,
        1000.0 * (text.count("(") + text.count(")")) / char_count,
        1000.0 * text.count("?") / char_count,
        1000.0 * text.count("!") / char_count,
        float(sum(ch.isdigit() for ch in text) / char_count),
        float(sum(1 for word in words if len(word) > 1 and word.isupper()) / word_count),
        float(sum(1 for word in words if word[:1].isupper()) / word_count),
        float(sum(1 for word in lower if word in FUNCTION_WORDS) / word_count),
        float(sum(1 for word in lower if word in first_person) / word_count),
        float(sum(1 for word in lower if word in third_person) / word_count),
        float(sum(1 for word in words if any(ch.isdigit() for ch in word)) / word_count),
        float(sum(1 for word in words if len(word) >= 10) / word_count),
        float(sum(1 for word in words if len(word) <= 3) / word_count),
        float(repeated_bigram_ratio),
    ]


def stylometric_matrix(rows: Sequence[dict[str, Any]]) -> np.ndarray:
    return np.asarray([stylometric_vector(str(row.get(TEXT_FIELD) or "")) for row in rows], dtype=np.float32)


def fit_stylometric(rows: list[dict[str, Any]], labels: list[int], config: dict[str, Any]) -> dict[str, Any]:
    scaler = StandardScaler()
    x_train = scaler.fit_transform(stylometric_matrix(rows))
    classifier = lgb.LGBMClassifier(**config)
    classifier.fit(x_train, np.asarray(labels, dtype=np.int8), feature_name=stylometric_feature_names())
    return {"scaler": scaler, "classifier": classifier, "feature_names": stylometric_feature_names()}


def stylometric_scores(model: dict[str, Any], rows: list[dict[str, Any]]) -> np.ndarray:
    if not rows:
        return np.asarray([], dtype=float)
    matrix = model["scaler"].transform(stylometric_matrix(rows))
    return model["classifier"].predict_proba(matrix)[:, 1]


def metadata_dict(row: dict[str, Any], fields: Sequence[str]) -> dict[str, str]:
    return {field: str(row.get(field) if row.get(field) is not None else "missing") for field in fields}


def fit_metadata_shortcut(rows: list[dict[str, Any]], labels: list[int], fields: Sequence[str]) -> dict[str, Any]:
    vectorizer = DictVectorizer(sparse=True)
    matrix = vectorizer.fit_transform([metadata_dict(row, fields) for row in rows])
    matrix.indices = matrix.indices.astype(np.int32, copy=False)
    matrix.indptr = matrix.indptr.astype(np.int32, copy=False)
    if len(set(labels)) < 2:
        classifier: Any = DummyClassifier(strategy="prior")
    else:
        classifier = LogisticRegression(class_weight="balanced", solver="liblinear", random_state=SEED, max_iter=300)
    classifier.fit(matrix, np.asarray(labels, dtype=np.int8))
    return {"vectorizer": vectorizer, "classifier": classifier, "fields": list(fields)}


def metadata_scores(model: dict[str, Any], rows: list[dict[str, Any]]) -> np.ndarray:
    if not rows:
        return np.asarray([], dtype=float)
    matrix = model["vectorizer"].transform([metadata_dict(row, model["fields"]) for row in rows])
    matrix.indices = matrix.indices.astype(np.int32, copy=False)
    matrix.indptr = matrix.indptr.astype(np.int32, copy=False)
    return model["classifier"].predict_proba(matrix)[:, 1]


def choose_threshold(labels: np.ndarray, scores: np.ndarray) -> float:
    if len(labels) == 0 or len(set(labels.tolist())) != 2:
        return 0.5
    candidates = np.unique(np.quantile(scores, np.linspace(0.02, 0.98, 193)))
    best = (float("-inf"), 0.5)
    for threshold in candidates:
        value = balanced_accuracy_score(labels, scores >= threshold)
        candidate = (float(value), -abs(float(threshold) - 0.5))
        incumbent = (best[0], -abs(best[1] - 0.5))
        if candidate > incumbent:
            best = (float(value), float(threshold))
    return best[1]


def expected_calibration_error(labels: np.ndarray, scores: np.ndarray, bins: int = 10) -> float:
    if len(labels) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    value = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (scores >= lower) & (scores < upper if index < bins - 1 else scores <= upper)
        if np.any(mask):
            value += float(np.mean(mask)) * abs(float(np.mean(labels[mask])) - float(np.mean(scores[mask])))
    return value


def binary_metrics(labels: Iterable[int], scores: Iterable[float], threshold: float) -> dict[str, Any]:
    y = np.asarray(list(labels), dtype=np.int8)
    p = np.asarray(list(scores), dtype=float)
    result: dict[str, Any] = {"count": int(len(y)), "positive_count": int(y.sum()) if len(y) else 0, "negative_count": int(len(y) - y.sum()) if len(y) else 0, "threshold": float(threshold)}
    if len(y) == 0 or len(set(y.tolist())) < 2:
        result.update({"roc_auc": None, "pr_auc": None, "balanced_accuracy": None, "f1": None, "brier": None, "ece": None})
        return result
    predictions = p >= threshold
    result.update(
        {
            "roc_auc": float(roc_auc_score(y, p)),
            "pr_auc": float(average_precision_score(y, p)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
            "f1": float(f1_score(y, predictions)),
            "brier": float(brier_score_loss(y, p)),
            "ece": float(expected_calibration_error(y, p)),
        }
    )
    return result


def score_distribution(scores: np.ndarray) -> dict[str, Any]:
    if len(scores) == 0:
        return {"count": 0}
    return {"count": int(len(scores)), "mean": float(np.mean(scores)), "std": float(np.std(scores)), "p05": float(np.quantile(scores, 0.05)), "p25": float(np.quantile(scores, 0.25)), "median": float(np.quantile(scores, 0.5)), "p75": float(np.quantile(scores, 0.75)), "p95": float(np.quantile(scores, 0.95))}


def mask_content(text: str) -> str:
    masked = re.sub(r"https?://\S+|www\.\S+", " [URL] ", text, flags=re.I)
    masked = re.sub(r"\b(?:19|20)\d{2}\b", " [YEAR] ", masked)
    masked = re.sub(r"\b\d+(?:[.,]\d+)?%?\b", " [NUMBER] ", masked)
    masked = re.sub(r"\b(?:chatgpt|gpt-?\d*|large language models?|generative ai|artificial intelligence)\b", " [AI_TERM] ", masked, flags=re.I)
    masked = re.sub(r"\b(?:[A-Z][a-z]{2,})(?:\s+[A-Z][a-z]{2,})+\b", " [ENTITY] ", masked)
    return re.sub(r"\s+", " ", masked).strip()


def rows_for_split(rows_by_id: dict[str, dict[str, Any]], manifest: dict[str, Any], split: str, labels_by_role: dict[str, int]) -> list[dict[str, Any]]:
    output = []
    for assignment in manifest.get("assignments") or []:
        if assignment.get("split") != split or assignment.get("corpus_role") not in labels_by_role:
            continue
        row = rows_by_id.get(assignment["document_id"])
        if row is not None:
            output.append(row)
    return output


def labels_for(rows: Sequence[dict[str, Any]], labels_by_role: dict[str, int]) -> np.ndarray:
    return np.asarray([labels_by_role[row["corpus_role"]] for row in rows], dtype=np.int8)


def no_text_prediction(row: dict[str, Any], score: float, label: int | None, model_family: str, lane: str, split: str | None = None) -> dict[str, Any]:
    return {
        "document_id": row["document_id"],
        "model_family": model_family,
        "lane": lane,
        "split": split,
        "label": label,
        SCORE_NAME: float(score),
        "publication_year": row.get("publication_year"),
        "publication_month": row.get("publication_month"),
        "publication_year_month": row.get("publication_year_month"),
        "corpus_role": row.get("corpus_role"),
        "url_hostname_hash": _hash_public_value(row.get("url_hostname")),
        "sitename_hash": _hash_public_value(row.get("sitename")),
        "topic": row.get("topic"),
        "author_hash": row.get("author_hash"),
        "identity_hash": row.get("identity_hash"),
        "normalized_text_sha256": row.get("normalized_text_sha256"),
        "near_duplicate_cluster_id": row.get("near_duplicate_cluster_id"),
        "word_count": row.get("word_count"),
    }


def _hash_public_value(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:24]


def assert_public_safe(payload: Any) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = key.lower()
                if lowered in FORBIDDEN_OUTPUT_KEYS or "preview" in lowered or lowered.endswith("text") or "abstract" in lowered:
                    raise ValueError(f"public artifact contains forbidden text key: {key}")
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(payload)


def write_json(path: Path, payload: Any) -> None:
    assert_public_safe(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            assert_public_safe(row)
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def feature_audit_lexical(model: dict[str, Any], limit: int = 50) -> dict[str, Any]:
    names = model["features"].get_feature_names_out()
    coefficients = model["classifier"].coef_[0]
    positive = np.argsort(coefficients)[-limit:][::-1]
    negative = np.argsort(coefficients)[:limit]
    return {"current_era": [{"feature_hash": hashlib.sha256(str(names[i]).encode()).hexdigest()[:24], "coefficient": float(coefficients[i])} for i in positive], "pre_llm_era": [{"feature_hash": hashlib.sha256(str(names[i]).encode()).hexdigest()[:24], "coefficient": float(coefficients[i])} for i in negative]}


def feature_audit_stylometric(model: dict[str, Any]) -> dict[str, Any]:
    importances = model["classifier"].feature_importances_
    rows = [{"feature": name, "importance": float(value)} for name, value in zip(model["feature_names"], importances)]
    return {"feature_importances": sorted(rows, key=lambda item: (-item["importance"], item["feature"]))}


def length_lanes(rows: list[dict[str, Any]], labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    if not rows:
        return {}
    lengths = np.asarray([float(row.get("word_count") or len(str(row.get(TEXT_FIELD) or "").split())) for row in rows])
    bins = np.quantile(lengths, [0, 0.25, 0.5, 0.75, 1.0])
    result = {}
    for i, name in enumerate(["q1_shortest", "q2", "q3", "q4_longest"]):
        lo, hi = bins[i], bins[i + 1]
        mask = (lengths >= lo) & (lengths <= hi if i == 3 else lengths < hi)
        result[name] = {"word_count_range": [float(lo), float(hi)], **binary_metrics(labels[mask], scores[mask], threshold)}
    return result


def evaluate_candidate(model_family: str, model: dict[str, Any], score_fn: Any, rows: list[dict[str, Any]], threshold: float, labels_by_role: dict[str, int], lane: str, split: str | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, np.ndarray]:
    labels = labels_for(rows, labels_by_role)
    scores = score_fn(model, rows)
    predictions = [no_text_prediction(row, score, int(label), model_family, lane, split) for row, score, label in zip(rows, scores, labels)]
    return binary_metrics(labels, scores, threshold), predictions, labels, scores


def train_protocol_candidate(kind: str, train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    y_train = labels_for(train_rows, CORE_ROLES).tolist()
    y_validation = labels_for(validation_rows, CORE_ROLES)
    if kind == "lexical":
        model = fit_lexical([row[TEXT_FIELD] for row in train_rows], y_train, config)
        validation_scores = lexical_scores(model, [row[TEXT_FIELD] for row in validation_rows])
        score_fn = lambda fitted, rows: lexical_scores(fitted, [row[TEXT_FIELD] for row in rows])
    elif kind == "stylometric":
        model = fit_stylometric(train_rows, y_train, config)
        validation_scores = stylometric_scores(model, validation_rows)
        score_fn = stylometric_scores
    else:
        raise ValueError(kind)
    threshold = choose_threshold(y_validation, validation_scores)
    return {"model": model, "threshold": threshold, "validation_metrics": binary_metrics(y_validation, validation_scores, threshold), "score_fn": score_fn}


def run(args: argparse.Namespace) -> dict[str, Any]:
    rows = read_jsonl_balanced_by_role(args.corpus / "normalized_rows.jsonl", limit_per_role=args.limit_per_role)
    rows_by_id = {row["document_id"]: row for row in rows}
    package = build_infini_news_protocols(rows, seed=args.seed)
    summary = protocol_summary(package)
    primary_manifest = package["protocols"]["publisher_domain_heldout_primary"]
    primary_train = rows_for_split(rows_by_id, primary_manifest, "train", CORE_ROLES)
    primary_validation = rows_for_split(rows_by_id, primary_manifest, "validation", CORE_ROLES)
    primary_test = rows_for_split(rows_by_id, primary_manifest, "test", CORE_ROLES)

    lexical_config = default_lexical_config()
    stylometric_config = default_stylometric_config()
    if args.fast:
        lexical_config.update({"min_df": 1, "word_max_features": 3000, "char_max_features": 3000, "max_iter": 100})
        stylometric_config.update({"n_estimators": 30, "n_jobs": 1})

    candidate_specs = {
        "lexical_tfidf_logistic": {
            "kind": "lexical",
            "model_family": "infini_news_word_char_tfidf_logistic",
            "config": lexical_config,
            "artifact_name": "infini_news_word_char_tfidf_logistic.joblib",
        },
        "stylometric_lightgbm": {
            "kind": "stylometric",
            "model_family": "infini_news_stylometric_lightgbm",
            "config": stylometric_config,
            "artifact_name": "infini_news_stylometric_lightgbm.joblib",
        },
    }
    output: dict[str, Any] = {"candidates": {}, "summary": summary}
    args.output.mkdir(parents=True, exist_ok=True)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    all_checksum_paths: list[Path] = []

    train_identity_base = {
        "primary_assignment_sha256": summary["protocols"]["publisher_domain_heldout_primary"]["assignment_sha256"],
        "fit_roles": CORE_ROLES,
        "train_document_ids": sorted(row["document_id"] for row in primary_train),
        "corpus_row_count": len(rows),
        "seed": args.seed,
    }

    for candidate_name, spec in candidate_specs.items():
        candidate_dir = args.output / candidate_name
        candidate_dir.mkdir(parents=True, exist_ok=True)
        protocol = train_protocol_candidate(spec["kind"], primary_train, primary_validation, spec["config"])
        model = protocol["model"]
        score_fn = protocol["score_fn"]
        threshold = protocol["threshold"]
        train_identity = stable_json_sha256({**train_identity_base, "candidate": candidate_name, "config": spec["config"]})
        model_id = f"infini-news-{candidate_name}-v1-{train_identity[:12]}"
        artifact_path = args.artifact_dir / spec["artifact_name"]
        artifact = {"schema": "publication_shift.infini_news_model_artifact.v1", "model_id": model_id, "model_family": spec["model_family"], "score_name": SCORE_NAME, "disclaimer": DISCLAIMER, "candidate_name": candidate_name, "model": model, "threshold": threshold, "config": spec["config"], "training_identity_sha256": train_identity, "training_protocol": "publisher_domain_heldout_primary"}
        joblib.dump(artifact, artifact_path, compress=3)

        lanes: dict[str, Any] = {"primary_validation": protocol["validation_metrics"]}
        prediction_files: dict[str, str] = {}
        primary_metrics, primary_predictions, primary_labels, primary_scores = evaluate_candidate(spec["model_family"], model, score_fn, primary_test, threshold, CORE_ROLES, "publisher_domain_heldout_primary", "test")
        lanes["publisher_domain_heldout_primary"] = primary_metrics
        lanes["length_quartiles_primary"] = length_lanes(primary_test, primary_labels, primary_scores, threshold)
        masked_scores = score_fn(model, [{**row, TEXT_FIELD: mask_content(str(row.get(TEXT_FIELD) or ""))} for row in primary_test])
        lanes["masked_primary_test"] = binary_metrics(primary_labels, masked_scores, threshold)
        pred_path = candidate_dir / "publisher_domain_heldout_primary_predictions.jsonl"
        write_jsonl(pred_path, primary_predictions)
        prediction_files["publisher_domain_heldout_primary"] = str(pred_path)
        all_checksum_paths.append(pred_path)

        for lane_name in ["source_sitename_heldout", "topic_heldout", "author_heldout", "random_diagnostic"]:
            manifest = package["protocols"][lane_name]
            lane_rows = rows_for_split(rows_by_id, manifest, "test", CORE_ROLES)
            metrics, predictions, _labels, _scores = evaluate_candidate(spec["model_family"], model, score_fn, lane_rows, threshold, CORE_ROLES, lane_name, "test")
            lanes[lane_name] = metrics
            pred_path = candidate_dir / f"{lane_name}_predictions.jsonl"
            write_jsonl(pred_path, predictions)
            prediction_files[lane_name] = str(pred_path)
            all_checksum_paths.append(pred_path)

        for role, lane_name in [("transition_2022", "transition_2022"), ("forward_2026", "forward_2026_jan_apr")]:
            eval_rows = [row for row in rows if row.get("corpus_role") == role]
            scores = score_fn(model, eval_rows)
            lanes[lane_name] = score_distribution(scores)
            pred_path = candidate_dir / f"{lane_name}_predictions.jsonl"
            write_jsonl(pred_path, [no_text_prediction(row, score, None, spec["model_family"], lane_name, "evaluation_only") for row, score in zip(eval_rows, scores)])
            prediction_files[lane_name] = str(pred_path)
            all_checksum_paths.append(pred_path)

        placebo_rows = [row for row in rows if row.get("corpus_role") == "historical_placebo"]
        matched_placebo_lanes = {}
        for early, late in [((2016, 2017), (2020, 2021)), ((2016, 2017, 2018), (2019, 2020, 2021))]:
            lane_rows = []
            labels = []
            for row in placebo_rows:
                if row.get("publication_year") in early:
                    lane_rows.append(row); labels.append(0)
                elif row.get("publication_year") in late:
                    lane_rows.append(row); labels.append(1)
            scores = score_fn(model, lane_rows)
            name = f"placebo_{min(early)}_{max(early)}_vs_{min(late)}_{max(late)}"
            matched_placebo_lanes[name] = binary_metrics(labels, scores, threshold)
            pred_path = candidate_dir / f"{name}_predictions.jsonl"
            write_jsonl(pred_path, [no_text_prediction(row, score, label, spec["model_family"], name, "evaluation_only") for row, score, label in zip(lane_rows, scores, labels)])
            prediction_files[name] = str(pred_path)
            all_checksum_paths.append(pred_path)
        lanes["matched_2016_2021_placebos"] = matched_placebo_lanes

        if spec["kind"] == "lexical":
            audit = feature_audit_lexical(model)
        else:
            audit = feature_audit_stylometric(model)

        metadata_model = fit_metadata_shortcut(primary_train, labels_for(primary_train, CORE_ROLES).tolist(), PUBLIC_METADATA_FIELDS)
        source_model = fit_metadata_shortcut(primary_train, labels_for(primary_train, CORE_ROLES).tolist(), ["sitename"])
        shortcut_diagnostics = {
            "metadata_only_primary_test": binary_metrics(primary_labels, metadata_scores(metadata_model, primary_test), 0.5),
            "source_only_primary_test": binary_metrics(primary_labels, metadata_scores(source_model, primary_test), 0.5),
            "fields": {"metadata_only": PUBLIC_METADATA_FIELDS, "source_only": ["sitename"]},
        }

        metrics = {
            "schema": "publication_shift.infini_news_candidate_metrics.v1",
            "created_at": utc_now(),
            "model_id": model_id,
            "candidate_name": candidate_name,
            "model_family": spec["model_family"],
            "score_name": SCORE_NAME,
            "disclaimer": DISCLAIMER,
            "decision": "PASS-HOLD",
            "decision_reason": "Candidate artifacts and frozen-lane diagnostics produced; held for downstream review/no production wiring and this score does not establish AI authorship.",
            "training_protocol": "publisher_domain_heldout_primary",
            "counts": {"train": len(primary_train), "validation": len(primary_validation), "test": len(primary_test), "corpus_rows": len(rows)},
            "lanes": lanes,
            "shortcut_diagnostics": shortcut_diagnostics,
            "feature_audit": audit,
            "prediction_files": prediction_files,
        }
        write_json(candidate_dir / "metrics.json", metrics)
        all_checksum_paths.append(candidate_dir / "metrics.json")
        metadata = {
            "schema": "publication_shift.infini_news_candidate_metadata.v1",
            "created_at": utc_now(),
            "model_id": model_id,
            "candidate_name": candidate_name,
            "model_family": spec["model_family"],
            "score_name": SCORE_NAME,
            "disclaimer": DISCLAIMER,
            "artifact_path": str(artifact_path),
            "artifact_size_bytes": artifact_path.stat().st_size,
            "artifact_sha256": sha256_file(artifact_path),
            "training_identity_sha256": train_identity,
            "config": spec["config"],
            "threshold": threshold,
            "corpus_rows": len(rows),
            "training_roles": CORE_ROLES,
            "excluded_from_training": ["historical_placebo", "transition_2022", "forward_2026"],
            "split_summary_sha256": stable_json_sha256(summary),
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__, "lightgbm": lgb.__version__, "joblib": joblib.__version__},
        }
        write_json(candidate_dir / "model_metadata.json", metadata)
        all_checksum_paths.extend([candidate_dir / "model_metadata.json", artifact_path])
        card = render_model_card(candidate_name, metadata, metrics)
        (candidate_dir / "MODEL_CARD.md").write_text(card, encoding="utf-8")
        all_checksum_paths.append(candidate_dir / "MODEL_CARD.md")
        output["candidates"][candidate_name] = {"metadata": metadata, "metrics": metrics}

    checksums = {str(path): sha256_file(path) for path in sorted(set(all_checksum_paths), key=str)}
    write_json(args.output / "checksums.json", {"schema": "publication_shift.infini_news_candidate_checksums.v1", "files": checksums})
    (args.output / "checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(checksums.items())), encoding="utf-8")
    return output


def render_model_card(candidate_name: str, metadata: dict[str, Any], metrics: dict[str, Any]) -> str:
    primary_auc = metrics["lanes"]["publisher_domain_heldout_primary"].get("roc_auc")
    masked_auc = metrics["lanes"].get("masked_primary_test", {}).get("roc_auc")
    return "\n".join([
        f"# INFINI-NEWS {candidate_name} candidate",
        "",
        DISCLAIMER,
        "",
        f"- Model ID: `{metadata['model_id']}`",
        f"- Model family: `{metadata['model_family']}`",
        "- Training protocol: `publisher_domain_heldout_primary` training rows only",
        "- Production wiring: none",
        "- Decision: `PASS-HOLD`",
        f"- Primary held-out ROC-AUC: `{primary_auc}`",
        f"- Masked primary ROC-AUC: `{masked_auc}`",
        f"- Artifact SHA256: `{metadata['artifact_sha256']}`",
        "",
        "Public artifacts contain IDs, hashes, metrics, and feature audits only; article text, titles, descriptions, URLs, and previews are excluded.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("services/data/publication_shift/infini_news_v1"))
    parser.add_argument("--output", type=Path, default=Path("services/evals/publication_shift_model/infini_news_v1/candidates"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("services/gateway/model_artifacts/publication_shift/infini_news_v1"))
    parser.add_argument("--seed", default="infini_news_v1_protocols")
    parser.add_argument("--limit-per-role", type=int, default=None, help="Test-only per-role row cap; do not use for frozen artifacts.")
    parser.add_argument("--fast", action="store_true", help="Use tiny model settings for tests only.")
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({name: {"model_id": data["metadata"]["model_id"], "decision": data["metrics"]["decision"], "primary_auc": data["metrics"]["lanes"]["publisher_domain_heldout_primary"].get("roc_auc")} for name, data in result["candidates"].items()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
