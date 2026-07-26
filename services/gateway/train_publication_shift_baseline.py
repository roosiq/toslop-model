#!/usr/bin/env python3
"""Train and evaluate the text-only publication-shift lexical baseline.

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
from typing import Any, Iterable

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import FeatureUnion

SEED = 20260712
DISCLAIMER = "This score does not establish AI authorship."
SCORE_NAME = "current_era_similarity"
MODEL_FAMILY = "publication_shift_word_char_tfidf_logistic"
CORE_ROLES = {"pre_llm_core": 0, "current_core": 1}
FORBIDDEN_OUTPUT_KEYS = {
    "original_abstract",
    "normalized_abstract",
    "abstract",
    "text",
    "preview",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_split(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {entry["document_id"]: entry for entry in payload["assignments"]}


def build_features(config: dict[str, Any]) -> FeatureUnion:
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


def default_config() -> dict[str, Any]:
    return {
        "word_ngram_range": [1, 3],
        "char_ngram_range": [3, 5],
        "min_df": 3,
        "max_df": 0.995,
        "word_max_features": 80000,
        "char_max_features": 80000,
        "class_weight": "balanced",
        "solver": "liblinear",
        "C": 1.0,
        "max_iter": 500,
        "random_seed": SEED,
    }


def fit_model(texts: list[str], labels: list[int], config: dict[str, Any]) -> tuple[FeatureUnion, LogisticRegression]:
    if len(set(labels)) != 2:
        raise ValueError("training labels must contain both eras")
    features = build_features(config)
    matrix = features.fit_transform(texts)
    classifier = LogisticRegression(
        class_weight=config["class_weight"],
        solver=config["solver"],
        C=float(config["C"]),
        max_iter=int(config["max_iter"]),
        random_state=int(config["random_seed"]),
    )
    classifier.fit(matrix, np.asarray(labels, dtype=np.int8))
    return features, classifier


def predict_scores(features: FeatureUnion, classifier: LogisticRegression, texts: list[str], batch_size: int = 2048) -> np.ndarray:
    outputs: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        matrix = features.transform(texts[start : start + batch_size])
        outputs.append(classifier.predict_proba(matrix)[:, 1])
    return np.concatenate(outputs) if outputs else np.asarray([], dtype=float)


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
        if not np.any(mask):
            continue
        value += float(np.mean(mask)) * abs(float(np.mean(labels[mask])) - float(np.mean(scores[mask])))
    return value


def binary_metrics(labels: Iterable[int], scores: Iterable[float], threshold: float) -> dict[str, Any]:
    y = np.asarray(list(labels), dtype=np.int8)
    p = np.asarray(list(scores), dtype=float)
    result: dict[str, Any] = {
        "count": int(len(y)),
        "positive_count": int(y.sum()) if len(y) else 0,
        "negative_count": int(len(y) - y.sum()) if len(y) else 0,
        "threshold": float(threshold),
    }
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


def mask_content(text: str) -> str:
    masked = re.sub(r"https?://\S+|www\.\S+", " [URL] ", text, flags=re.I)
    masked = re.sub(r"\[(?:\d+\s*[,;-]?\s*)+\]", " [CITATION] ", masked)
    masked = re.sub(r"\((?:[A-Z][A-Za-z'-]+(?:\s+(?:et al\.|and|&|[A-Z][A-Za-z'-]+))*,?\s*)?\d{4}[a-z]?\)", " [CITATION] ", masked)
    masked = re.sub(r"\b(?:19|20)\d{2}\b", " [YEAR] ", masked)
    masked = re.sub(r"\b\d+(?:[.,]\d+)?%?\b", " [NUMBER] ", masked)
    masked = re.sub(r"\b(?:chatgpt|gpt-?\d*|large language models?|generative ai|artificial intelligence)\b", " [AI_TERM] ", masked, flags=re.I)
    masked = re.sub(r"\b(?:[A-Z][a-z]{2,})(?:\s+[A-Z][a-z]{2,})+\b", " [ENTITY] ", masked)
    return re.sub(r"\s+", " ", masked).strip()


def grouped_bootstrap_auc(
    labels: np.ndarray,
    scores: np.ndarray,
    groups: list[str],
    *,
    samples: int = 300,
    seed: int = SEED,
) -> dict[str, Any]:
    group_to_indices: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        group_to_indices[str(group)].append(index)
    keys = sorted(group_to_indices)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(samples):
        chosen = rng.choice(keys, size=len(keys), replace=True)
        indices = [index for group in chosen for index in group_to_indices[str(group)]]
        y = labels[indices]
        if len(set(y.tolist())) < 2:
            continue
        values.append(float(roc_auc_score(y, scores[indices])))
    if not values:
        return {"samples_requested": samples, "samples_valid": 0, "lower": None, "median": None, "upper": None}
    return {
        "samples_requested": samples,
        "samples_valid": len(values),
        "lower": float(np.quantile(values, 0.025)),
        "median": float(np.quantile(values, 0.5)),
        "upper": float(np.quantile(values, 0.975)),
        "values": values,
    }


def score_distribution(scores: np.ndarray) -> dict[str, Any]:
    if len(scores) == 0:
        return {"count": 0}
    return {
        "count": int(len(scores)),
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "p05": float(np.quantile(scores, 0.05)),
        "p25": float(np.quantile(scores, 0.25)),
        "median": float(np.quantile(scores, 0.5)),
        "p75": float(np.quantile(scores, 0.75)),
        "p95": float(np.quantile(scores, 0.95)),
    }


def select_rows(rows: list[dict[str, Any]], assignments: dict[str, dict[str, Any]], split: str, labels_by_role: dict[str, int]) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        assignment = assignments.get(row["document_id"])
        if assignment and assignment["split"] == split and row["corpus_role"] in labels_by_role:
            selected.append(row)
    return selected


def train_protocol(
    rows: list[dict[str, Any]],
    assignments: dict[str, dict[str, Any]],
    labels_by_role: dict[str, int],
    config: dict[str, Any],
) -> dict[str, Any]:
    train_rows = select_rows(rows, assignments, "train", labels_by_role)
    validation_rows = select_rows(rows, assignments, "validation", labels_by_role)
    test_rows = select_rows(rows, assignments, "test", labels_by_role)
    features, classifier = fit_model(
        [row["normalized_abstract"] for row in train_rows],
        [labels_by_role[row["corpus_role"]] for row in train_rows],
        config,
    )
    validation_scores = predict_scores(features, classifier, [row["normalized_abstract"] for row in validation_rows])
    validation_labels = np.asarray([labels_by_role[row["corpus_role"]] for row in validation_rows], dtype=np.int8)
    threshold = choose_threshold(validation_labels, validation_scores)
    test_scores = predict_scores(features, classifier, [row["normalized_abstract"] for row in test_rows])
    test_labels = np.asarray([labels_by_role[row["corpus_role"]] for row in test_rows], dtype=np.int8)
    return {
        "features": features,
        "classifier": classifier,
        "threshold": threshold,
        "train_rows": train_rows,
        "validation_rows": validation_rows,
        "test_rows": test_rows,
        "validation_scores": validation_scores,
        "validation_labels": validation_labels,
        "test_scores": test_scores,
        "test_labels": test_labels,
        "validation_metrics": binary_metrics(validation_labels, validation_scores, threshold),
        "test_metrics": binary_metrics(test_labels, test_scores, threshold),
    }


def top_coefficients(features: FeatureUnion, classifier: LogisticRegression, limit: int = 30) -> dict[str, list[dict[str, Any]]]:
    names = features.get_feature_names_out()
    coefficients = classifier.coef_[0]
    positive = np.argsort(coefficients)[-limit:][::-1]
    negative = np.argsort(coefficients)[:limit]
    return {
        "current_era": [{"feature": str(names[i]), "coefficient": float(coefficients[i])} for i in positive],
        "pre_llm_era": [{"feature": str(names[i]), "coefficient": float(coefficients[i])} for i in negative],
    }


def no_text_prediction(row: dict[str, Any], assignment: dict[str, Any] | None, score: float, label: int | None) -> dict[str, Any]:
    return {
        "document_id": row["document_id"],
        "split": assignment.get("split") if assignment else None,
        "label": label,
        SCORE_NAME: float(score),
        "publication_year": row["publication_year"],
        "corpus_role": row["corpus_role"],
        "source_id": row["source_id"],
        "publisher_id": row["publisher_id"],
        "normalized_text_sha256": row["normalized_text_sha256"],
        "near_duplicate_cluster_id": row["near_duplicate_cluster_id"],
    }


def assert_public_safe(payload: Any) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_OUTPUT_KEYS or "preview" in key.lower() or "abstract" in key.lower():
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


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = default_config()
    rows = read_jsonl(args.corpus / "normalized_rows.jsonl")
    source_assignments = load_split(args.source_split)
    author_assignments = load_split(args.author_split)

    primary = train_protocol(rows, source_assignments, CORE_ROLES, config)
    author = train_protocol(rows, author_assignments, CORE_ROLES, config)

    placebo_specs = {
        "2014_2017_vs_2018_2021": ({"historical_placebo": 0, "pre_llm_core": 1}, None),
        "2016_2018_vs_2019_2021": (None, ({2016, 2017, 2018}, {2019, 2020, 2021})),
    }
    placebo_results: dict[str, Any] = {}
    placebo_auc_bootstraps: dict[str, list[float]] = {}
    for index, (name, (role_labels, year_sets)) in enumerate(placebo_specs.items()):
        if role_labels is not None:
            protocol = train_protocol(rows, source_assignments, role_labels, config)
        else:
            early_years, late_years = year_sets
            relabeled = []
            role_key = f"placebo_{name}"
            for row in rows:
                if row["publication_year"] in early_years:
                    relabeled.append({**row, "corpus_role": role_key + "_early"})
                elif row["publication_year"] in late_years:
                    relabeled.append({**row, "corpus_role": role_key + "_late"})
            protocol = train_protocol(relabeled, source_assignments, {role_key + "_early": 0, role_key + "_late": 1}, config)
        groups = [row["publisher_id"] for row in protocol["test_rows"]]
        bootstrap = grouped_bootstrap_auc(protocol["test_labels"], protocol["test_scores"], groups, seed=SEED + index + 10)
        placebo_auc_bootstraps[name] = bootstrap.pop("values", [])
        placebo_results[name] = {
            "validation": protocol["validation_metrics"],
            "test": protocol["test_metrics"],
            "grouped_bootstrap_roc_auc_95ci": bootstrap,
            "counts": {
                "train": len(protocol["train_rows"]),
                "validation": len(protocol["validation_rows"]),
                "test": len(protocol["test_rows"]),
            },
        }

    primary_groups = [row["publisher_id"] for row in primary["test_rows"]]
    primary_bootstrap = grouped_bootstrap_auc(primary["test_labels"], primary["test_scores"], primary_groups)
    primary_bootstrap_values = primary_bootstrap.pop("values", [])
    strongest_placebo_name = max(placebo_results, key=lambda name: placebo_results[name]["test"]["roc_auc"] or -1)
    strongest_values = placebo_auc_bootstraps[strongest_placebo_name]
    paired_count = min(len(primary_bootstrap_values), len(strongest_values))
    lift_values = [primary_bootstrap_values[i] - strongest_values[i] for i in range(paired_count)]
    lift_ci = {
        "strongest_placebo": strongest_placebo_name,
        "point_estimate": float(primary["test_metrics"]["roc_auc"] - placebo_results[strongest_placebo_name]["test"]["roc_auc"]),
        "samples_valid": paired_count,
        "lower": float(np.quantile(lift_values, 0.025)) if lift_values else None,
        "median": float(np.quantile(lift_values, 0.5)) if lift_values else None,
        "upper": float(np.quantile(lift_values, 0.975)) if lift_values else None,
    }

    masked_scores = predict_scores(
        primary["features"],
        primary["classifier"],
        [mask_content(row["normalized_abstract"]) for row in primary["test_rows"]],
    )
    masked_metrics = binary_metrics(primary["test_labels"], masked_scores, primary["threshold"])

    transition_rows = [row for row in rows if row["corpus_role"] == "transition_2022"]
    forward_rows = [row for row in rows if row["corpus_role"] == "forward_2026"]
    transition_scores = predict_scores(primary["features"], primary["classifier"], [row["normalized_abstract"] for row in transition_rows])
    forward_scores = predict_scores(primary["features"], primary["classifier"], [row["normalized_abstract"] for row in forward_rows])

    train_identity = stable_json_sha256(
        {
            "document_ids": sorted(row["document_id"] for row in primary["train_rows"]),
            "labels": CORE_ROLES,
            "config": config,
            "source_split_sha256": sha256_file(args.source_split),
        }
    )
    model_id = f"publication-shift-lexical-v1-{train_identity[:12]}"
    artifact = {
        "schema": "publication_shift.model_artifact.v1",
        "model_id": model_id,
        "model_family": MODEL_FAMILY,
        "score_name": SCORE_NAME,
        "score_description": "Similarity to matched current-era academic publication language.",
        "disclaimer": DISCLAIMER,
        "features": primary["features"],
        "classifier": primary["classifier"],
        "threshold": primary["threshold"],
        "config": config,
        "training_identity_sha256": train_identity,
    }
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.artifact, compress=3)
    artifact_sha256 = sha256_file(args.artifact)

    test_predictions = [
        no_text_prediction(row, source_assignments.get(row["document_id"]), score, int(label))
        for row, score, label in zip(primary["test_rows"], primary["test_scores"], primary["test_labels"])
    ]
    transition_predictions = [no_text_prediction(row, source_assignments.get(row["document_id"]), score, None) for row, score in zip(transition_rows, transition_scores)]
    forward_predictions = [no_text_prediction(row, source_assignments.get(row["document_id"]), score, None) for row, score in zip(forward_rows, forward_scores)]
    write_jsonl(args.output / "heldout_predictions.jsonl", test_predictions)
    write_jsonl(args.output / "transition_2022_predictions.jsonl", transition_predictions)
    write_jsonl(args.output / "forward_2026_predictions.jsonl", forward_predictions)

    per_year = {}
    for year in sorted({row["publication_year"] for row in primary["test_rows"]}):
        indices = [i for i, row in enumerate(primary["test_rows"]) if row["publication_year"] == year]
        per_year[str(year)] = {
            "count": len(indices),
            "label": int(primary["test_labels"][indices[0]]) if indices else None,
            SCORE_NAME: score_distribution(primary["test_scores"][indices]),
        }
    source_values: dict[str, list[float]] = defaultdict(list)
    for row, score in zip(primary["test_rows"], primary["test_scores"]):
        source_values[row["source_id"]].append(float(score))
    per_source = [
        {"source_id": source, "count": len(values), "mean_score": float(np.mean(values))}
        for source, values in sorted(source_values.items(), key=lambda item: (-len(item[1]), item[0]))[:100]
    ]

    metrics = {
        "schema": "publication_shift.evaluation.v1",
        "created_at": utc_now(),
        "model_id": model_id,
        "score_name": SCORE_NAME,
        "disclaimer": DISCLAIMER,
        "decision": "HOLD",
        "decision_reason": "Pilot lexical baseline; full 252k planned corpus and all preregistered candidate families are not yet complete.",
        "primary_source_publisher_heldout": {
            "counts": {
                "train": len(primary["train_rows"]),
                "validation": len(primary["validation_rows"]),
                "test": len(primary["test_rows"]),
            },
            "validation": primary["validation_metrics"],
            "test": primary["test_metrics"],
            "grouped_bootstrap_roc_auc_95ci": primary_bootstrap,
            "masked_test": masked_metrics,
            "per_year": per_year,
            "top_sources": per_source,
        },
        "author_heldout_retrained": {
            "counts": {
                "train": len(author["train_rows"]),
                "validation": len(author["validation_rows"]),
                "test": len(author["test_rows"]),
            },
            "validation": author["validation_metrics"],
            "test": author["test_metrics"],
        },
        "historical_placebos": placebo_results,
        "main_minus_strongest_placebo": lift_ci,
        "transition_2022": score_distribution(transition_scores),
        "forward_2026_partial_year_month_matched_through_july": score_distribution(forward_scores),
        "top_coefficients": top_coefficients(primary["features"], primary["classifier"]),
    }
    write_json(args.output / "metrics.json", metrics)

    metadata = {
        "schema": "publication_shift.model_metadata.v1",
        "created_at": utc_now(),
        "model_id": model_id,
        "model_family": MODEL_FAMILY,
        "score_name": SCORE_NAME,
        "score_description": artifact["score_description"],
        "disclaimer": DISCLAIMER,
        "artifact_path": str(args.artifact),
        "artifact_size_bytes": args.artifact.stat().st_size,
        "artifact_sha256": artifact_sha256,
        "training_identity_sha256": train_identity,
        "config": config,
        "threshold": primary["threshold"],
        "corpus_rows": len(rows),
        "training_roles": CORE_ROLES,
        "excluded_from_training": ["historical_placebo", "transition_2022", "forward_2026"],
        "source_split_sha256": sha256_file(args.source_split),
        "author_split_sha256": sha256_file(args.author_split),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }
    write_json(args.output / "model_metadata.json", metadata)
    checksums = {
        str(args.artifact): artifact_sha256,
        str(args.output / "metrics.json"): sha256_file(args.output / "metrics.json"),
        str(args.output / "model_metadata.json"): sha256_file(args.output / "model_metadata.json"),
        str(args.output / "heldout_predictions.jsonl"): sha256_file(args.output / "heldout_predictions.jsonl"),
        str(args.output / "transition_2022_predictions.jsonl"): sha256_file(args.output / "transition_2022_predictions.jsonl"),
        str(args.output / "forward_2026_predictions.jsonl"): sha256_file(args.output / "forward_2026_predictions.jsonl"),
    }
    model_card = args.output / "MODEL_CARD.md"
    if model_card.exists():
        checksums[str(model_card)] = sha256_file(model_card)
    write_json(args.output / "checksums.json", {"schema": "publication_shift.checksums.v1", "files": checksums})
    (args.output / "checksums.sha256").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(checksums.items())), encoding="utf-8")
    return {"metadata": metadata, "metrics": metrics}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-split", type=Path, required=True)
    parser.add_argument("--author-split", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({"metadata": result["metadata"], "metrics": result["metrics"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
