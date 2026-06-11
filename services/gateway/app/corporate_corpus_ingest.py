from __future__ import annotations

import argparse
import csv
import json
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from app.corporate_sequence_model import train_sequence_lift_model


def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        yield from csv.DictReader(handle)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _source_from_numeric_label(label: str) -> str:
    return "ai_generated" if str(label).strip() == "1" else "human_written"


def _source_from_text_label(label: str) -> str:
    lowered = str(label).strip().lower()
    return "ai_generated" if lowered in {"ai", "machine", "generated", "1"} else "human_written"


def _source_from_harsh_label(label: str) -> str:
    lowered = str(label).strip().lower()
    if not lowered:
        return "unknown"
    if lowered == "human":
        return "human_written"
    return "ai_generated"


def _limit_append(docs: list[dict[str, Any]], doc: dict[str, Any], source_counts: dict[str, int], max_docs_per_source: int | None) -> None:
    source_key = str(doc.get("dataset", "unknown"))
    if max_docs_per_source is not None and source_counts.get(source_key, 0) >= max_docs_per_source:
        return
    docs.append(doc)
    source_counts[source_key] = source_counts.get(source_key, 0) + 1


def _load_corporate_parquet_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return []
    frame = pd.read_parquet(path)
    return frame.to_dict(orient="records")


def _iter_corporate_speak_rows(local: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    csv_files = sorted(local.glob("*.csv"))
    for csv_path in csv_files:
        split = csv_path.stem
        for row in _read_csv(csv_path):
            yield split, row

    data_dir = local / "data"
    for parquet_path in sorted(data_dir.glob("*.parquet")):
        split = parquet_path.name.split("-", 1)[0]
        for row in _load_corporate_parquet_rows(parquet_path):
            yield split, row


def _iter_text_file_rows(local: Path) -> Iterable[tuple[str, str]]:
    if not local.exists():
        return
    for text_file in sorted(local.glob("*.txt")):
        split = text_file.stem
        with text_file.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in handle:
                text = _clean_text(row)
                if text:
                    yield split, text


def normalize_hf_corpora(root: Path | str, max_docs_per_source: int | None = None) -> list[dict[str, Any]]:
    root = Path(root)
    docs: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    ateeq = root / "ai_human_detection" / "Ateeqq__AI-and-Human-Generated-Text"
    for split in ("train", "test"):
        for index, row in enumerate(_read_csv(ateeq / f"{split}.csv")):
            text = _clean_text(row.get("abstract"))
            if not text:
                continue
            doc = {
                "doc_id": f"ateeqq_{split}_{index:06d}",
                "dataset": "Ateeqq/AI-and-Human-Generated-Text",
                "source_type": _source_from_numeric_label(str(row.get("label", ""))),
                "quality_label": "unknown",
                "domain": "academic",
                "doc_type": "abstract",
                "title": _clean_text(row.get("title")),
                "text": text,
            }
            _limit_append(docs, doc, source_counts, max_docs_per_source)

    harsh = root / "ai_human_detection" / "harsh4248__human_vs_llm"
    for file in sorted((harsh / "data").glob("*.parquet")):
        for index, row in enumerate(_load_corporate_parquet_rows(file)):
            text = _clean_text(row.get("title"))
            if not text:
                continue
            doc = {
                "doc_id": f"harsh_{file.stem}_{index:06d}",
                "dataset": "harsh4248/human_vs_llm",
                "source_type": _source_from_harsh_label(str(row.get("label", ""))),
                "quality_label": "unknown",
                "domain": "misc",
                "doc_type": "title",
                "title": text,
                "text": text,
            }
            _limit_append(docs, doc, source_counts, max_docs_per_source)

    silentone = root / "ai_human_detection" / "silentone0725__ai-human-text-detection-v1"
    for split in ("train", "validation", "test"):
        for index, row in enumerate(_read_csv(silentone / f"{split}.csv")):
            text = _clean_text(row.get("text"))
            if not text:
                continue
            doc = {
                "doc_id": f"silentone_{split}_{index:06d}",
                "dataset": "silentone0725/ai-human-text-detection-v1",
                "source_type": _source_from_text_label(str(row.get("label", ""))),
                "quality_label": "unknown",
                "domain": "general",
                "doc_type": "generic_text",
                "text": text,
            }
            _limit_append(docs, doc, source_counts, max_docs_per_source)

    sunorme = root / "ai_human_detection" / "sunorme__human-vs-llm-text-corpus"
    sunorme_index = 0
    for split, text in _iter_text_file_rows(sunorme):
        doc = {
            "doc_id": f"sunorme_{split}_{sunorme_index:06d}",
            "dataset": "sunorme/human-vs-llm-text-corpus",
            "source_type": "unknown",
            "quality_label": "unknown",
            "domain": "general",
            "doc_type": "generic_text",
            "text": text,
        }
        sunorme_index += 1
        _limit_append(docs, doc, source_counts, max_docs_per_source)

    corporate = root / "corporate_speak" / "phxdev__corporate-speak-dataset"
    corporate_index = 0
    for split, row in _iter_corporate_speak_rows(corporate):
        output_text = _clean_text(row.get("output"))
        text = output_text or _clean_text(row.get("text"))
        if not text:
            continue
        instruction = _clean_text(row.get("instruction"))
        doc = {
            "doc_id": f"corporate_speak_{split}_{corporate_index:06d}",
            "dataset": "phxdev/corporate-speak-dataset",
            "source_type": "ai_generated",
            "quality_label": "low",
            "domain": "corporate",
            "doc_type": "corporate_copy",
            "instruction": instruction,
            "text": text,
        }
        corporate_index += 1
        _limit_append(docs, doc, source_counts, max_docs_per_source)

    return docs


def write_normalized_corpus(docs: list[dict[str, Any]], output_path: Path | str) -> list[dict[str, Any]]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return docs


def _plan_entry(doc: dict[str, Any], index: int) -> dict[str, Any]:
    text = str(doc.get("text", ""))
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "index": index,
        "doc_id": str(doc.get("doc_id", f"doc_{index:06d}")),
        "dataset": str(doc.get("dataset", "unknown")),
        "source_type": str(doc.get("source_type", "unknown")),
        "quality_label": str(doc.get("quality_label", "unknown")),
        "text_length": len(text),
        "text_hash": text_hash,
        "grounding_status": "pending",
        "grounding_schema": "corporate.sumo_plan.v1",
    }


def write_sumo_corpus_plan(docs: list[dict[str, Any]], output_path: Path | str) -> dict[str, Any]:
    output = Path(output_path)
    plan = {
        "artifact_version": "corporate.sumo_corpus_plan.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "grounding_status": "pending",
        "documents": [_plan_entry(doc, index) for index, doc in enumerate(docs)],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    return plan


def read_normalized_corpus(path: Path | str) -> list[dict[str, Any]]:
    corpus_path = Path(path)
    if not corpus_path.exists():
        return []
    docs: list[dict[str, Any]] = []
    with corpus_path.open(encoding="utf-8") as handle:
        for line in handle:
            if stripped := line.strip():
                docs.append(json.loads(stripped))
    return docs


def mine_corpus_sequence_model(corpus: list[dict[str, Any]], min_lift: float = 1.25, top_n: int = 100) -> dict[str, Any]:
    model = train_sequence_lift_model(corpus)
    feature_lift = model.get("featureLift", {})
    feature_counts = model.get("featureCounts", {})
    ai_counts = feature_counts.get("ai", {})
    human_counts = feature_counts.get("human", {})

    top_features = []
    for feature, lift in feature_lift.items():
        lift_value = float(lift)
        if lift_value < min_lift:
            continue
        top_features.append(
            {
                "feature": feature,
                "lift": round(lift_value, 4),
                "aiCount": int(ai_counts.get(feature, 0)),
                "humanCount": int(human_counts.get(feature, 0)),
            }
        )
    top_features.sort(key=lambda item: (item["lift"], item["aiCount"]), reverse=True)

    model["topFeatures"] = top_features[:top_n]
    model["recommendedMotifs"] = [
        {
            "id": "hf_mined_" + item["feature"].replace(":", "_").replace("|", "_").replace(" ", "_")[:96],
            "feature": item["feature"],
            "lift": item["lift"],
            "aiCount": item["aiCount"],
            "humanCount": item["humanCount"],
        }
        for item in top_features[: min(30, top_n)]
    ]
    return model


def write_sequence_model(model: dict[str, Any], output_path: Path | str) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, indent=2, ensure_ascii=False))
    return model


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize HF corpora and write a pending SUMO grounding plan for Corporate Slop.")
    parser.add_argument("--hf-root", type=Path, default=Path("services/data/hf-corpora"))
    parser.add_argument("--normalized-output", type=Path, default=Path("services/evals/corporate_sequence_model/hf_normalized_corpus.jsonl"))
    parser.add_argument("--plan-output", type=Path, default=Path("services/evals/corporate_sequence_model/hf_corpus_plan.json"))
    parser.add_argument("--model-output", type=Path, default=Path("services/evals/corporate_sequence_model/hf_sequence_lift_model.json"))
    parser.add_argument("--max-docs-per-source", type=int, default=5000)
    parser.add_argument("--min-lift", type=float, default=1.25)
    parser.add_argument("--top-n", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    docs = normalize_hf_corpora(args.hf_root, max_docs_per_source=args.max_docs_per_source)
    write_normalized_corpus(docs, args.normalized_output)
    plan = write_sumo_corpus_plan(docs, args.plan_output)
    model = mine_corpus_sequence_model(docs, min_lift=args.min_lift, top_n=args.top_n)
    write_sequence_model(model, args.model_output)
    print(
        json.dumps(
            {
                "plan_output": str(args.plan_output),
                "normalized_output": str(args.normalized_output),
                "model_output": str(args.model_output),
                "plan_documents": len(plan.get("documents", [])),
                "documents": len(docs),
                "ai_documents": model.get("aiDocumentCount"),
                "human_documents": model.get("documentCount", 0) - model.get("aiDocumentCount", 0),
                "top_features": len(model.get("topFeatures", [])),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
