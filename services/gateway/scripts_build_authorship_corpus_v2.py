from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+")
URL_RE = re.compile(r"https?://|www\.|URL_\d+", re.I)
ASSISTANT_RE = re.compile(
    r"\b(Sure!|Certainly!|I'd be happy to|I apologize|As an AI|I do not have personal|Does that make sense\??|I can't help|I cannot help)\b",
    re.I,
)
LOW_LETTER_RE = re.compile(r"\b(i\w*|the|and|to|it|you|we|they|he|she|a|an)\b", re.I)

BASE = Path(__file__).resolve().parent
DATA_ROOT = BASE.parent / "data" / "hf-corpora" / "ai_human_detection"
EVAL_DIR = BASE.parent / "evals" / "corporate_sequence_model"
OUT_DIR = EVAL_DIR / "authorship_corpus_v2"
DEFAULT_ANDY_PATH = DATA_ROOT / "andythetechnerd03__AI-human-text"
DEFAULT_HC3_WIKI_PATH = DATA_ROOT / "rajendrabaskota__hc3-wiki-intro-dataset" / "data"
DEFAULT_HC3_QA_PATH = DATA_ROOT / "pszemraj__HC3-textgen-qa"
DEFAULT_EXISTING_CLEAN = EVAL_DIR / "hf_normalized_authorship_clean_v1.jsonl"

ANDY_DATASET = "andythetechnerd03/AI-human-text"
ANDY_LICENSE = "apache-2.0"
HC3_WIKI_DATASET = "rajendrabaskota/hc3-wiki-intro-dataset"
HC3_QA_DATASET = "pszemraj/HC3-textgen-qa"
ALLOWED_EXISTING_DATASETS = {
    "Ateeqq/AI-and-Human-Generated-Text",
    "silentone0725/ai-human-text-detection-v1",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def strip_answer_markup(text: str) -> str:
    text = text.replace("<answer>", " ").replace("<end_answer>", " ")
    return " ".join(text.split())


def text_hash(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def stable_split(hash_value: str, test_ratio: float) -> str:
    bucket = int(hash_value[:8], 16) / 0xFFFFFFFF
    return "test" if bucket < test_ratio else "train"


def quality_flags(text: str) -> dict[str, bool]:
    words = WORD_RE.findall(text)
    chars = len(text)
    letters = sum(ch.isalpha() for ch in text)
    digits = sum(ch.isdigit() for ch in text)
    punct = sum((not ch.isalnum() and not ch.isspace()) for ch in text)

    lower_words = [w.lower() for w in words]
    repeats = sum(1 for i in range(2, len(lower_words)) if lower_words[i] == lower_words[i - 1] == lower_words[i - 2])

    uppercase_words = sum(w.isupper() for w in lower_words)
    letter_ratio = letters / max(chars, 1)
    punct_ratio = punct / max(chars, 1)
    digit_ratio = digits / max(chars, 1)

    return {
        "assistant_artifact": bool(ASSISTANT_RE.search(text)),
        "url_heavy": len(URL_RE.findall(text)) >= 2,
        "placeholder_url": bool(URL_RE.search(text)),
        "low_letter_ratio": chars > 40 and letter_ratio < 0.45,
        "high_digit_ratio": chars > 80 and digit_ratio > 0.2,
        "high_punct_ratio": chars > 80 and punct_ratio > 0.18,
        "mostly_upper": len(words) > 20 and uppercase_words / max(len(words), 1) > 0.5,
        "repeated_tokens": repeats >= 3,
        "basic_junk": len(words) > 0 and len(LOW_LETTER_RE.findall(text)) < max(2, len(words) // 20),
    }


def collect_parquet_sources(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".parquet":
            raise ValueError(f"Expected a parquet file, found {path.suffix}: {path}")
        return [path]
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    return sorted(p for p in path.rglob("*.parquet"))


def collect_csv_sources(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".csv":
            raise ValueError(f"Expected a csv file, found {path.suffix}: {path}")
        return [path]
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    return sorted(p for p in path.rglob("*.csv"))


def parse_source_type(value: Any) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return "ai_generated" if value else "human_written"
    try:
        int_value = int(value)
        if int_value == 1:
            return "ai_generated"
        if int_value == 0:
            return "human_written"
    except (TypeError, ValueError):
        pass
    lowered = str(value).strip().lower()
    if lowered in {"ai", "ai_generated", "generated", "1"}:
        return "ai_generated"
    if lowered in {"human", "human_written", "0"}:
        return "human_written"
    return None


def parse_hc3_label(value: Any) -> str | None:
    return parse_source_type(value)


def build_rejected(candidate: dict[str, Any], reasons: list[str], row_hash: str, txt: str, wc: int) -> dict[str, Any]:
    return {
        "doc_id": candidate.get("doc_id"),
        "dataset": candidate.get("dataset"),
        "source_type": candidate.get("source_type"),
        "word_count": wc,
        "text_hash": row_hash,
        "reasons": reasons,
        "corpus_role": candidate.get("corpus_role"),
        "source_file": candidate.get("source_file"),
        "text_preview": txt[:300],
    }


def validate_and_normalize(
    candidate: dict[str, Any],
    *,
    min_words: int,
    max_words: int,
    seen_hashes: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    text = clean_text(candidate.get("text"))
    row_hash = text_hash(text) if text else text_hash("")
    wc = word_count(text)
    flags = quality_flags(text)
    reasons: list[str] = []

    if not text.strip():
        reasons.append("empty_text")
    if wc < min_words:
        reasons.append("too_short")
    if wc > max_words:
        reasons.append("too_long")

    if flags["assistant_artifact"]:
        reasons.append("assistant_artifact")
    if flags["url_heavy"]:
        reasons.append("url_heavy")
    if flags["placeholder_url"]:
        reasons.append("placeholder_url")
    if flags["low_letter_ratio"]:
        reasons.append("low_letter_ratio")
    if flags["high_digit_ratio"]:
        reasons.append("high_digit_ratio")
    if flags["high_punct_ratio"]:
        reasons.append("high_punct_ratio")
    if flags["repeated_tokens"]:
        reasons.append("repeated_tokens")
    if flags["mostly_upper"]:
        reasons.append("mostly_upper")
    if flags["basic_junk"]:
        reasons.append("basic_junk")

    if row_hash in seen_hashes:
        reasons.append("exact_duplicate")

    if reasons:
        if text and row_hash not in seen_hashes:
            seen_hashes.add(row_hash)
        return None, build_rejected(
            candidate,
            reasons,
            row_hash,
            text,
            wc,
        )

    seen_hashes.add(row_hash)

    aux = dict(candidate.get("aux_labels") or {})
    aux["source_set"] = candidate.get("source_set")
    aux["source_file"] = candidate.get("source_file")
    aux["source_row_id"] = candidate.get("source_row_id")

    normalized = {
        "doc_id": candidate["doc_id"],
        "dataset": candidate["dataset"],
        "license": candidate.get("license", "unknown"),
        "source_type": candidate["source_type"],
        "ai_generated_label": candidate["source_type"] == "ai_generated",
        "label_confidence": float(candidate.get("label_confidence", 1.0)),
        "quality_label": candidate.get("quality_label", "unknown"),
        "domain": candidate.get("domain", "unknown"),
        "doc_type": candidate.get("doc_type", "unknown"),
        "text": text,
        "text_hash": row_hash,
        "word_count": wc,
        "split": candidate.get("split") or "train",
        "corpus_role": candidate.get("corpus_role", "unknown"),
        "generator_family": candidate.get("generator_family", "unknown"),
        "cleaning_flags": flags,
        "aux_labels": aux,
        "source_priority": candidate.get("source_priority", 0),
    }
    return normalized, None


def load_andy_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file in collect_parquet_sources(path):
        frame = pd.read_parquet(file)
        file_name = file.stem
        for idx, row in frame.iterrows():
            source_type = parse_source_type(row.get("generated"))
            if source_type is None:
                continue
            source_name = file.parent.name
            rows.append(
                {
                    "doc_id": f"andy_{file_name}_{idx:06d}",
                    "dataset": ANDY_DATASET,
                    "license": ANDY_LICENSE,
                    "source_type": source_type,
                    "text": row.get("text", ""),
                    "domain": "mixed",
                    "doc_type": "long_form_text",
                    "quality_label": "unknown",
                    "generator_family": "unknown",
                    "label_confidence": 1.0,
                    "aux_labels": {"source_dataset_split": source_name},
                    "source_set": "andy_primary",
                    "source_file": str(file),
                    "source_row_id": f"{source_name}:{idx}",
                    "source_priority": 0,
                    "corpus_role": "supervised_candidate",
                }
            )
    return rows


def load_existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Missing input file: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if not line.strip():
                continue
            raw = json.loads(line)
            dataset = str(raw.get("dataset"))
            if dataset not in ALLOWED_EXISTING_DATASETS:
                continue
            source_type = str(raw.get("source_type", ""))
            if source_type not in {"ai_generated", "human_written"}:
                continue
            rows.append(
                {
                    "doc_id": raw.get("doc_id", f"existing_{idx:06d}"),
                    "dataset": dataset,
                    "license": raw.get("license", "unknown"),
                    "source_type": source_type,
                    "text": raw.get("text", ""),
                    "domain": raw.get("domain", "unknown"),
                    "doc_type": raw.get("doc_type", "unknown"),
                    "quality_label": raw.get("quality_label", "unknown"),
                    "generator_family": raw.get("generator_family", "legacy"),
                    "label_confidence": float(raw.get("label_confidence", raw.get("ai_label_confidence", 1.0))),
                    "aux_labels": dict(raw.get("aux_labels", {})),
                    "source_set": "existing_clean",
                    "source_file": str(path),
                    "source_row_id": str(idx),
                    "source_priority": 1,
                    "corpus_role": "supervised_candidate",
                }
            )
    return rows


def load_hc3_wiki_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file in collect_parquet_sources(path):
        frame = pd.read_parquet(file)
        for idx, row in frame.iterrows():
            source_type = parse_hc3_label(row.get("label"))
            if source_type is None:
                continue
            rows.append(
                {
                    "doc_id": f"hc3_wiki_{idx:06d}",
                    "dataset": HC3_WIKI_DATASET,
                    "license": "unknown",
                    "source_type": source_type,
                    "text": row.get("text", ""),
                    "domain": str(row.get("source", "wiki")),
                    "doc_type": "wiki_intro",
                    "quality_label": "unknown",
                    "generator_family": str(row.get("source", "wiki")),
                    "label_confidence": 1.0,
                    "aux_labels": {
                        "hc3_source": str(row.get("source", "")),
                        "prompt_preview": str(clean_text(row.get("prompt", "")))[:180],
                    },
                    "source_set": "hc3_wiki",
                    "source_file": str(file),
                    "source_row_id": f"{file.name}:{idx}",
                    "source_priority": 3,
                    "corpus_role": "calibration_hc3_wiki",
                }
            )
    return rows


def load_hc3_textgen_qa_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file in collect_csv_sources(path):
        frame = pd.read_csv(file)
        for idx, row in frame.iterrows():
            question = clean_text(row.get("question", ""))
            question_hash = text_hash(question) if question else "empty"
            ai_text = strip_answer_markup(clean_text(row.get("text", "")))
            human_text = strip_answer_markup(clean_text(row.get("human_response", "")))

            if ai_text:
                rows.append(
                    {
                        "doc_id": f"hc3_qa_ai_{idx:06d}",
                        "dataset": HC3_QA_DATASET,
                        "license": "apache-2.0",
                        "source_type": "ai_generated",
                        "text": ai_text,
                        "domain": "qa",
                        "doc_type": "qa_response",
                        "quality_label": "unknown",
                        "generator_family": "unknown",
                        "label_confidence": 1.0,
                        "aux_labels": {
                            "question_hash": question_hash,
                            "question_preview": question[:180],
                            "response_kind": "model",
                        },
                        "source_set": "hc3_qa",
                        "source_file": str(file),
                        "source_row_id": f"{file.name}:{idx}",
                        "source_priority": 3,
                        "corpus_role": "calibration_hc3_qa",
                    }
                )

            if human_text:
                rows.append(
                    {
                        "doc_id": f"hc3_qa_human_{idx:06d}",
                        "dataset": HC3_QA_DATASET,
                        "license": "apache-2.0",
                        "source_type": "human_written",
                        "text": human_text,
                        "domain": "qa",
                        "doc_type": "qa_response",
                        "quality_label": "unknown",
                        "generator_family": "human",
                        "label_confidence": 1.0,
                        "aux_labels": {
                            "question_hash": question_hash,
                            "question_preview": question[:180],
                            "response_kind": "human",
                        },
                        "source_set": "hc3_qa",
                        "source_file": str(file),
                        "source_row_id": f"{file.name}:{idx}:human",
                        "source_priority": 3,
                        "corpus_role": "calibration_hc3_qa",
                    }
                )
    return rows


def normalize_rows(
    candidates: list[dict[str, Any]],
    *,
    min_words: int,
    max_words: int,
    seen_hashes: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter, Counter]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    ordered = sorted(candidates, key=lambda item: (item.get("source_set", ""), str(item.get("source_row_id")), str(item.get("doc_id"))))

    for candidate in ordered:
        normalized, rejected_row = validate_and_normalize(
            candidate,
            min_words=min_words,
            max_words=max_words,
            seen_hashes=seen_hashes,
        )
        if normalized is None and rejected_row is not None:
            reason_counts.update(rejected_row["reasons"])
            rejected.append(rejected_row)
            continue
        if normalized is None:
            continue
        kept.append(normalized)
        source_counts[candidate["source_set"]] += 1

    return kept, rejected, reason_counts, source_counts


def split_leakage(rows: list[dict[str, Any]]) -> int:
    seen: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        seen[str(row.get("text_hash"))].add(str(row.get("split")))
    return sum(1 for splits in seen.values() if len(splits) > 1)


def apply_source_ratio(
    andy_rows: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    ratio: float,
) -> list[dict[str, Any]]:
    if ratio <= 0 or not andy_rows or not existing_rows:
        return andy_rows + existing_rows

    andy_sorted = sorted(andy_rows, key=lambda row: row["text_hash"])
    existing_sorted = sorted(existing_rows, key=lambda row: row["text_hash"])

    a_total = len(andy_sorted)
    e_total = len(existing_sorted)

    if a_total > int(e_total * ratio):
        andy_sorted = andy_sorted[: max(1, int(e_total * ratio))]
    if e_total > int(a_total / ratio):
        existing_sorted = existing_sorted[: max(1, int(a_total / ratio))]
    return andy_sorted + existing_sorted


def balance_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = defaultdict(list)
    for row in rows:
        by_label[row["source_type"]].append(row)

    if len(by_label) < 2:
        return rows
    human_count = len(by_label["human_written"])
    ai_count = len(by_label["ai_generated"])
    if human_count == 0 or ai_count == 0:
        return rows

    target = min(human_count, ai_count)
    if target == 0:
        return rows

    balanced: list[dict[str, Any]] = []
    for label_rows in by_label.values():
        balanced.extend(sorted(label_rows, key=lambda row: row["text_hash"])[:target])
    return balanced


def set_splits(rows: list[dict[str, Any]], test_ratio: float) -> None:
    for row in rows:
        row["split"] = stable_split(str(row["text_hash"]), test_ratio)


def set_corpus_roles(rows: list[dict[str, Any]], role: str) -> None:
    for row in rows:
        row["corpus_role"] = role


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    def row_key(item: dict[str, Any]) -> tuple[str, str, str]:
        return (str(item.get("source_set")), str(item.get("text_hash", "")), str(item.get("doc_id")))

    with path.open("w", encoding="utf-8") as handle:
        for row in sorted(rows, key=row_key):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_sample(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count <= 0 or not rows:
        return []

    by_label = defaultdict(list)
    for row in rows:
        by_label[row["source_type"]].append(row)

    ai_rows = sorted(by_label.get("ai_generated", []), key=lambda item: item["text_hash"])
    human_rows = sorted(by_label.get("human_written", []), key=lambda item: item["text_hash"])
    ai_target = count // 2
    human_target = count // 2 + (count % 2)

    selected: list[dict[str, Any]] = []
    selected.extend(ai_rows[:ai_target])
    selected.extend(human_rows[:human_target])
    if len(selected) < count:
        selected_hashes = {row["text_hash"] for row in selected}
        fallback = [row for row in sorted(rows, key=lambda item: item["text_hash"]) if row["text_hash"] not in selected_hashes]
        selected.extend(fallback[: count - len(selected)])

    # Copy selected rows so marking sample100 does not mutate rows already destined
    # for supervised_train_mix.jsonl / supervised_test_mix.jsonl.
    return [dict(row) for row in selected[:count]]


def counts_by_field(field: str, rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get(field)) for row in rows).most_common())


def build_report(
    *,
    inputs: dict[str, int],
    accepted: dict[str, int],
    rejected_count: int,
    rejected_reason_counts: Counter[str],
    source_counts: dict[str, int],
    supervised_ratio_target: float,
    balanced_labels: bool,
    test_ratio: float,
    split_leakage_count: int,
    output_paths: dict[str, str],
    sample_size: int,
) -> dict[str, Any]:
    return {
        "schema": "corporate.authorship_corpus_v2_report.v1",
        "inputs": inputs,
        "accepted": accepted,
        "rejected": {
            "rows": rejected_count,
            "reasons": dict(rejected_reason_counts.most_common()),
        },
        "source_counts": source_counts,
        "supervised": {
            "target_andy_existing_ratio": supervised_ratio_target,
            "labels_balanced": balanced_labels,
            "test_ratio": test_ratio,
            "supervised_split_hash_leakage_groups": split_leakage_count,
            "sample100_target": sample_size,
        },
        "output_files": output_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Corporate Slop authorship_corpus_v2 artifacts.")
    parser.add_argument("--andy-path", type=Path, default=DEFAULT_ANDY_PATH)
    parser.add_argument("--hc3-wiki-path", type=Path, default=DEFAULT_HC3_WIKI_PATH)
    parser.add_argument("--hc3-qa-path", type=Path, default=DEFAULT_HC3_QA_PATH)
    parser.add_argument("--existing-clean-input", type=Path, default=DEFAULT_EXISTING_CLEAN)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--supervised-train-output", type=Path, default=OUT_DIR / "supervised_train_mix.jsonl")
    parser.add_argument("--supervised-test-output", type=Path, default=OUT_DIR / "supervised_test_mix.jsonl")
    parser.add_argument("--calibration-wiki-output", type=Path, default=OUT_DIR / "calibration_hc3_wiki.jsonl")
    parser.add_argument("--calibration-qa-output", type=Path, default=OUT_DIR / "calibration_hc3_qa.jsonl")
    parser.add_argument("--sample-output", type=Path, default=OUT_DIR / "sample100.jsonl")
    parser.add_argument("--rejected-output", type=Path, default=OUT_DIR / "rejected.jsonl")
    parser.add_argument("--report-output", type=Path, default=OUT_DIR / "report.json")
    parser.add_argument("--min-words", type=int, default=80)
    parser.add_argument("--max-words", type=int, default=900)
    parser.add_argument("--supervised-test-ratio", type=float, default=0.25)
    parser.add_argument("--andy-existing-ratio", type=float, default=3.0, help="Supervised composition target as andy:existing ratio.")
    parser.add_argument("--disable-label-balance", action="store_true", help="Disable source-label balancing in supervised mix.")
    parser.add_argument("--sample-size", type=int, default=100)
    args = parser.parse_args()

    if "--output-dir" in sys.argv:
        output_dir = args.output_dir
        args.supervised_train_output = output_dir / "supervised_train_mix.jsonl"
        args.supervised_test_output = output_dir / "supervised_test_mix.jsonl"
        args.calibration_wiki_output = output_dir / "calibration_hc3_wiki.jsonl"
        args.calibration_qa_output = output_dir / "calibration_hc3_qa.jsonl"
        args.sample_output = output_dir / "sample100.jsonl"
        args.rejected_output = output_dir / "rejected.jsonl"
        args.report_output = output_dir / "report.json"

    try:
        andy_candidates = load_andy_rows(args.andy_path)
        existing_candidates = load_existing_rows(args.existing_clean_input)
        hc3_wiki_candidates = load_hc3_wiki_rows(args.hc3_wiki_path)
        hc3_qa_candidates = load_hc3_textgen_qa_rows(args.hc3_qa_path)
    except (OSError, ValueError) as err:
        raise SystemExit(f"Failed to load inputs: {err}")

    seen_hashes: set[str] = set()
    andy_rows, andy_rejected, andy_reason_counts, andy_source_counts = normalize_rows(
        andy_candidates,
        min_words=args.min_words,
        max_words=args.max_words,
        seen_hashes=seen_hashes,
    )
    existing_rows, existing_rejected, existing_reason_counts, existing_source_counts = normalize_rows(
        existing_candidates,
        min_words=args.min_words,
        max_words=args.max_words,
        seen_hashes=seen_hashes,
    )
    hc3_wiki_rows, hc3_wiki_rejected, hc3_wiki_reason_counts, hc3_wiki_source_counts = normalize_rows(
        hc3_wiki_candidates,
        min_words=args.min_words,
        max_words=args.max_words,
        seen_hashes=seen_hashes,
    )
    hc3_qa_rows, hc3_qa_rejected, hc3_qa_reason_counts, hc3_qa_source_counts = normalize_rows(
        hc3_qa_candidates,
        min_words=args.min_words,
        max_words=args.max_words,
        seen_hashes=seen_hashes,
    )

    reason_counts = andy_reason_counts + existing_reason_counts + hc3_wiki_reason_counts + hc3_qa_reason_counts

    rejected_rows = (
        andy_rejected
        + existing_rejected
        + hc3_wiki_rejected
        + hc3_qa_rejected
    )

    supervised_pool = apply_source_ratio(
        andy_rows=andy_rows,
        existing_rows=existing_rows,
        ratio=args.andy_existing_ratio,
    )

    if not args.disable_label_balance:
        supervised_pool = balance_labels(supervised_pool)

    set_splits(supervised_pool, args.supervised_test_ratio)

    set_corpus_roles([row for row in supervised_pool if row["source_type"] == "human_written"], "supervised_train")
    set_corpus_roles([row for row in supervised_pool if row["source_type"] == "ai_generated"], "supervised_train")

    train_rows = [row for row in supervised_pool if row.get("split") == "train"]
    test_rows = [row for row in supervised_pool if row.get("split") == "test"]

    for row in train_rows:
        row["corpus_role"] = "supervised_train"
    for row in test_rows:
        row["corpus_role"] = "supervised_test"

    set_splits(hc3_wiki_rows, args.supervised_test_ratio)
    set_splits(hc3_qa_rows, args.supervised_test_ratio)
    set_corpus_roles(hc3_wiki_rows, "calibration_hc3_wiki")
    set_corpus_roles(hc3_qa_rows, "calibration_hc3_qa")

    sample_rows = build_sample(train_rows + test_rows, args.sample_size)
    for row in sample_rows:
        row["corpus_role"] = "sample100"

    combined_supervised_for_leakage = [row for row in supervised_pool]
    split_leakage_count = split_leakage(combined_supervised_for_leakage)

    write_jsonl(args.supervised_train_output, train_rows)
    write_jsonl(args.supervised_test_output, test_rows)
    write_jsonl(args.calibration_wiki_output, hc3_wiki_rows)
    write_jsonl(args.calibration_qa_output, hc3_qa_rows)
    write_jsonl(args.sample_output, sample_rows)
    write_jsonl(args.rejected_output, rejected_rows)

    report = build_report(
        inputs={
            "andy_rows": len(andy_candidates),
            "existing_rows": len(existing_candidates),
            "hc3_wiki_rows": len(hc3_wiki_candidates),
            "hc3_qa_rows": len(hc3_qa_candidates),
        },
        accepted={
            "andy_rows": len(andy_rows),
            "existing_rows": len(existing_rows),
            "hc3_wiki_rows": len(hc3_wiki_rows),
            "hc3_qa_rows": len(hc3_qa_rows),
            "supervised_rows": len(supervised_pool),
            "supervised_train_rows": len(train_rows),
            "supervised_test_rows": len(test_rows),
            "sample_rows": len(sample_rows),
        },
        rejected_count=len(rejected_rows),
        rejected_reason_counts=reason_counts,
        source_counts=dict(
            andy_supervised=len([
                row
                for row in supervised_pool
                if row.get("aux_labels", {}).get("source_set") == "andy_primary"
            ]),
            existing_supervised=len([
                row
                for row in supervised_pool
                if row.get("aux_labels", {}).get("source_set") == "existing_clean"
            ]),
            hc3_wiki=len(hc3_wiki_rows),
            hc3_qa=len(hc3_qa_rows),
        ),
        supervised_ratio_target=args.andy_existing_ratio,
        balanced_labels=not args.disable_label_balance,
        test_ratio=args.supervised_test_ratio,
        split_leakage_count=split_leakage_count,
        output_paths={
            "supervised_train": str(args.supervised_train_output),
            "supervised_test": str(args.supervised_test_output),
            "calibration_hc3_wiki": str(args.calibration_wiki_output),
            "calibration_hc3_qa": str(args.calibration_qa_output),
            "sample100": str(args.sample_output),
            "rejected": str(args.rejected_output),
            "report": str(args.report_output),
        },
        sample_size=args.sample_size,
    )
    write_json(args.report_output, report)

    print(
        json.dumps(
            {
                "report": str(args.report_output),
                "supervised_train_rows": len(train_rows),
                "supervised_test_rows": len(test_rows),
                "calibration_wiki_rows": len(hc3_wiki_rows),
                "calibration_qa_rows": len(hc3_qa_rows),
                "sample_rows": len(sample_rows),
                "rejected_rows": len(rejected_rows),
                "supervised_split_leakage_groups": split_leakage_count,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
