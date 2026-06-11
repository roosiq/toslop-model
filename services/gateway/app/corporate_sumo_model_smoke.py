from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

LABEL_TO_INT = {"human_written": 0, "ai_generated": 1}
INT_TO_LABEL = {value: key for key, value in LABEL_TO_INT.items()}
LEAKAGE_FEATURES = {"source_is_ai_generated", "source_is_human_written"}
SEQUENCE_FIELDS = (
    "sumo_term_sequence",
    "sumo_class_sequence",
    "proposition_kind_sequence",
    "proposition_source_sequence",
    "unresolved_surface_sequence",
    "unresolved_type_sequence",
    "wordnet_token_sequence",
    "wordnet_lemma_sequence",
    "wordnet_pos_sequence",
    "wordnet_lexname_sequence",
    "wordnet_synset_sequence",
    "wordnet_category_sequence",
    "wordnet_synonym_match_sequence",
    "wordnet_antonym_match_sequence",
    "wordnet_sumo_term_sequence",
    "wordnet_sumo_relation_sequence",
)


def read_feature_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                if not (stripped := line.strip()):
                    continue
                payload = json.loads(stripped)
                if isinstance(payload, dict) and payload.get("source_type") in LABEL_TO_INT:
                    rows.append(payload)
    return rows


def _numeric_features(row: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    features = row.get("features") if isinstance(row.get("features"), dict) else {}
    if not isinstance(features, dict):
        return values
    for key, value in features.items():
        if key in LEAKAGE_FEATURES or key == "document_type":
            continue
        if isinstance(value, bool):
            values[f"num::{key}"] = float(int(value))
        elif isinstance(value, (int, float)) and math.isfinite(float(value)):
            values[f"num::{key}"] = float(value)
    return values


def _sequence_features(row: dict[str, Any]) -> dict[str, float]:
    values: defaultdict[str, float] = defaultdict(float)
    for field in SEQUENCE_FIELDS:
        items = row.get(field)
        if not isinstance(items, list):
            continue
        for item in items:
            text = str(item or "").strip().lower()
            if text:
                values[f"seq::{field}::{text}"] += 1.0
    return dict(values)


def vectorize_row(row: dict[str, Any]) -> dict[str, float]:
    values = _numeric_features(row)
    values.update(_sequence_features(row))
    return values


def _train_centroids(rows: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    sums: dict[int, defaultdict[str, float]] = {0: defaultdict(float), 1: defaultdict(float)}
    counts: Counter[int] = Counter()
    for row in rows:
        label = LABEL_TO_INT[str(row["source_type"])]
        counts[label] += 1
        for key, value in vectorize_row(row).items():
            sums[label][key] += value
    centroids: dict[int, dict[str, float]] = {}
    for label, counter in sums.items():
        if counts[label] == 0:
            centroids[label] = {}
        else:
            centroids[label] = {key: value / counts[label] for key, value in counter.items()}
    return centroids


def _distance(vector: dict[str, float], centroid: dict[str, float]) -> float:
    keys = set(vector) | set(centroid)
    return sum((vector.get(key, 0.0) - centroid.get(key, 0.0)) ** 2 for key in keys)


def predict_nearest_centroid(train_rows: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any]:
    centroids = _train_centroids(train_rows)
    vector = vectorize_row(row)
    distances = {label: _distance(vector, centroid) for label, centroid in centroids.items()}
    predicted = min(distances, key=lambda label: distances[label])
    return {
        "predicted_source_type": INT_TO_LABEL[predicted],
        "distance_to_human_written": distances.get(0, 0.0),
        "distance_to_ai_generated": distances.get(1, 0.0),
        "feature_count": len(vector),
    }


def leave_one_out(rows: list[dict[str, Any]]) -> dict[str, Any]:
    predictions: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        train_rows = rows[:index] + rows[index + 1 :]
        if not train_rows or len({item["source_type"] for item in train_rows}) < 2:
            continue
        result = predict_nearest_centroid(train_rows, row)
        actual = str(row["source_type"])
        predictions.append(
            {
                "doc_id": row.get("doc_id"),
                "dataset": row.get("dataset"),
                "domain": row.get("domain"),
                "actual_source_type": actual,
                **result,
                "correct": result["predicted_source_type"] == actual,
            }
        )

    total = len(predictions)
    correct = sum(1 for item in predictions if item["correct"])
    by_actual: dict[str, dict[str, int]] = {}
    for item in predictions:
        actual = str(item["actual_source_type"])
        bucket = by_actual.setdefault(actual, {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += int(bool(item["correct"]))
    return {
        "schema": "corporate.sumo_model_smoke_test.v1",
        "model": "nearest_centroid_leave_one_out",
        "feature_policy": "numeric SUMO features plus sequence bag counts; excludes source_is_* leakage flags",
        "row_count": len(rows),
        "evaluated_count": total,
        "correct_count": correct,
        "accuracy": correct / total if total else 0.0,
        "by_actual_source_type": by_actual,
        "predictions": predictions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a tiny leave-one-out smoke test over Corporate Slop SUMO feature rows.")
    parser.add_argument("--input", type=Path, action="append", required=True, help="Feature JSONL input. Repeat for multiple files.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = leave_one_out(read_feature_rows(args.input))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
