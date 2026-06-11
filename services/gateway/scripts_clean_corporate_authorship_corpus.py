from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+")
URL_RE = re.compile(r"https?://|www\.|URL_\d+", re.I)
ASSISTANT_RE = re.compile(
    r"\b(Sure!|Certainly!|I'd be happy to|I apologize|As an AI|I do not have personal|Does that make sense\??)\b",
    re.I,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def text_hash(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def quality_flags(text: str) -> dict[str, bool]:
    words = WORD_RE.findall(text)
    chars = len(text)
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    punct = sum((not c.isalnum() and not c.isspace()) for c in text)
    upper = sum(c.isupper() for c in text)
    toks = [w.lower() for w in words]
    repeats = sum(1 for i in range(1, len(toks)) if toks[i] == toks[i - 1])
    return {
        "assistant_artifact": bool(ASSISTANT_RE.search(text)),
        "placeholder_url": bool(URL_RE.search(text)),
        "url_heavy": len(URL_RE.findall(text)) >= 2,
        "low_letter_ratio": chars > 50 and letters / max(chars, 1) < 0.45,
        "high_digit_ratio": chars > 80 and digits / max(chars, 1) > 0.25,
        "high_punct_ratio": chars > 80 and punct / max(chars, 1) > 0.18,
        "mostly_upper": len(words) > 20 and upper / max(letters, 1) > 0.55,
        "repeated_tokens": repeats >= 3,
    }


def bad_reasons(row: dict[str, Any], *, min_words: int, max_words: int) -> list[str]:
    text = str(row.get("text") or "")
    wc = word_count(text)
    reasons: list[str] = []
    if not text.strip():
        reasons.append("empty_text")
    if wc < min_words:
        reasons.append("too_short")
    if wc > max_words:
        reasons.append("too_long")
    flags = quality_flags(text)
    for key, value in flags.items():
        if value:
            reasons.append(key)
    # This dataset is useful as slop context, but it is pure AI + low-quality + corporate,
    # so it label-leaks for AI-authorship. Drop from the clean authorship corpus.
    if row.get("dataset") == "phxdev/corporate-speak-dataset":
        reasons.append("corporate_speak_label_shortcut")
    return reasons


def stable_group_split(hash_value: str, test_ratio: float) -> str:
    # deterministic hash split. Use first 8 hex chars as uniform-ish bucket.
    bucket = int(hashlib.sha256(hash_value.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if bucket < test_ratio else "train"


def build_clean(input_path: Path, output_path: Path, rejected_path: Path, report_path: Path, min_words: int, max_words: int, test_ratio: float) -> None:
    rows = read_jsonl(input_path)
    seen_hashes: set[str] = set()
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    duplicate_count = 0

    for row in rows:
        row = dict(row)
        text = str(row.get("text") or "")
        h = text_hash(text) if text.strip() else "EMPTY"
        reasons = bad_reasons(row, min_words=min_words, max_words=max_words)
        if h in seen_hashes:
            reasons.append("exact_duplicate")
            duplicate_count += 1
        if reasons:
            reason_counts.update(reasons)
            rejected.append({
                "doc_id": row.get("doc_id"),
                "dataset": row.get("dataset"),
                "source_type": row.get("source_type"),
                "domain": row.get("domain"),
                "doc_type": row.get("doc_type"),
                "word_count": word_count(text),
                "text_hash": h,
                "reasons": reasons,
                "text_preview": text[:300],
            })
            if h not in seen_hashes and text.strip():
                seen_hashes.add(h)
            continue
        seen_hashes.add(h)
        row["text_hash"] = h
        row["word_count"] = word_count(text)
        row["split"] = stable_group_split(h, test_ratio)
        row.setdefault("aux_labels", {})
        row["aux_labels"] = dict(row["aux_labels"])
        row["aux_labels"].update({k: v for k, v in quality_flags(text).items() if v})
        kept.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in kept:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with rejected_path.open("w", encoding="utf-8") as handle:
        for row in rejected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def counts(field: str, seq: list[dict[str, Any]]) -> dict[str, int]:
        return dict(Counter(str(r.get(field)) for r in seq).most_common())

    by_dataset_label: dict[str, dict[str, int]] = {}
    tmp: dict[str, Counter[str]] = defaultdict(Counter)
    for row in kept:
        tmp[str(row.get("dataset"))][str(row.get("source_type"))] += 1
    by_dataset_label = {key: dict(value) for key, value in tmp.items()}

    split_hashes: dict[str, set[str]] = defaultdict(set)
    for row in kept:
        split_hashes[str(row.get("text_hash"))].add(str(row.get("split")))
    leakage = sum(1 for splits in split_hashes.values() if len(splits) > 1)
    report = {
        "schema": "corporate.authorship_clean_corpus_report.v1",
        "input": str(input_path),
        "output": str(output_path),
        "rejected_output": str(rejected_path),
        "min_words": min_words,
        "max_words": max_words,
        "test_ratio": test_ratio,
        "input_rows": len(rows),
        "kept_rows": len(kept),
        "rejected_rows": len(rejected),
        "duplicate_rows_rejected": duplicate_count,
        "reason_counts": dict(reason_counts.most_common()),
        "counts": {
            "source_type": counts("source_type", kept),
            "dataset": counts("dataset", kept),
            "domain": counts("domain", kept),
            "doc_type": counts("doc_type", kept),
            "split": counts("split", kept),
        },
        "by_dataset_label": by_dataset_label,
        "hash_split_leakage_groups": leakage,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("../evals/corporate_sequence_model/hf_normalized_corpus.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1.jsonl"))
    parser.add_argument("--rejected", type=Path, default=Path("../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1_rejected.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1_report.json"))
    parser.add_argument("--min-words", type=int, default=30)
    parser.add_argument("--max-words", type=int, default=900)
    parser.add_argument("--test-ratio", type=float, default=0.25)
    args = parser.parse_args()
    build_clean(args.input, args.output, args.rejected, args.report, args.min_words, args.max_words, args.test_ratio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
