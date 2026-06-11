from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable

LABEL_TO_INT = {"human_written": 0, "ai_generated": 1}
INT_TO_LABEL = {0: "human_written", 1: "ai_generated"}
LEAKAGE_FEATURES = {"source_is_ai_generated", "source_is_human_written"}

RRF_SEQUENCE_FIELDS = (
    "sumo_term_sequence",
    "sumo_class_sequence",
    "proposition_kind_sequence",
    "proposition_source_sequence",
    "unresolved_surface_sequence",
    "unresolved_type_sequence",
)

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]*|\\d+(?:\\.\\d+)?|[^\w\s]")
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\\d+")
SENTENCE_RE = re.compile(r"[.!?]")

DET_WORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "this",
    "those",
    "these",
    "his",
    "her",
    "its",
    "my",
    "your",
    "our",
    "their",
    "each",
    "every",
    "some",
    "any",
    "no",
    "another",
    "other",
}
PRONOUN_WORDS = {
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "mine",
    "yours",
    "his",
    "hers",
    "its",
    "our",
    "ours",
    "their",
    "theirs",
    "who",
    "whom",
    "which",
    "what",
    "where",
    "whoever",
    "whichever",
}
AUX_WORDS = {
    "be",
    "is",
    "am",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "can",
    "could",
    "will",
    "would",
    "shall",
    "should",
}
MODAL_WORDS = {"can", "could", "will", "would", "shall", "should", "may", "might", "must", "mustn't", "ought"}
PREP_WORDS = {
    "in",
    "on",
    "at",
    "to",
    "from",
    "by",
    "for",
    "with",
    "without",
    "about",
    "into",
    "through",
    "throughout",
    "during",
    "before",
    "after",
    "above",
    "below",
    "under",
    "over",
    "between",
    "among",
    "around",
    "inside",
    "outside",
    "toward",
    "towards",
}
CONJ_WORDS = {
    "and",
    "or",
    "but",
    "so",
    "yet",
    "for",
    "nor",
    "although",
    "because",
    "if",
    "unless",
    "while",
    "since",
    "until",
    "when",
    "where",
    "once",
}
ADV_WORDS = {
    "again",
    "also",
    "almost",
    "always",
    "anyway",
    "anymore",
    "around",
    "away",
    "almost",
    "later",
    "here",
    "there",
    "quite",
    "soon",
    "very",
    "well",
    "often",
    "then",
    "just",
    "now",
    "still",
    "thus",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_markdown(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def stable_key(row: dict[str, Any]) -> str:
    return str(row.get("doc_id") or json.dumps(row, sort_keys=True))


def normalize_label(row: dict[str, Any]) -> int | None:
    source_type = str(row.get("source_type", ""))
    return LABEL_TO_INT.get(source_type)


def grounded_hard_labeled(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        label = normalize_label(row)
        if label is None:
            continue
        if str(row.get("grounding_status")) != "grounded":
            continue
        doc_id = str(row.get("doc_id", ""))
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        labeled_row = dict(row)
        labeled_row["ai_generated_label"] = label
        out.append(labeled_row)
    return out


def balanced_sample(rows: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_label: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for row in rows:
        by_label[int(row["ai_generated_label"])].append(row)
    per_label = n // 2
    sample = []
    for rows_by_label in by_label.values():
        ordered = sorted(rows_by_label, key=lambda r: hashlib.sha256((stable_key(r) + str(seed)).encode()).hexdigest())
        sample.extend(ordered[: min(per_label, len(ordered))])
    rng.shuffle(sample)
    return sample


def stratified_split(rows: list[dict[str, Any]], test_ratio: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row.get("dataset")), int(row["ai_generated_label"])), []).append(row)
    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda r: hashlib.sha256(stable_key(r).encode()).hexdigest())
        if len(ordered) > 1:
            test_count = max(1, round(len(ordered) * test_ratio))
        else:
            test_count = 0
        test.extend(ordered[:test_count])
        train.extend(ordered[test_count:])
    return train, test


def text_from_row(row: dict[str, Any]) -> str:
    for field in ("text", "normalized_text", "document_text", "content", "title"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            if field == "title":
                continue
            return value
    text = row.get("text") if isinstance(row.get("text"), str) else ""
    title = row.get("title")
    if isinstance(title, str) and title.strip() and not text.strip():
        return title
    if isinstance(title, str) and title.strip():
        if text:
            return f"{title}\\n{text}"
        return title
    return ""


def build_text_lookup(paths: list[Path]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for path in paths:
        if not path or not path.exists():
            continue
        for row in read_jsonl(path):
            doc_id = str(row.get("doc_id", ""))
            if not doc_id:
                continue
            if doc_id in lookup:
                continue
            text = text_from_row(row)
            if text:
                lookup[doc_id] = text
    return lookup


def attach_text(rows: list[dict[str, Any]], text_lookup: dict[str, str]) -> tuple[list[dict[str, Any]], int]:
    out: list[dict[str, Any]] = []
    missing = 0
    for row in rows:
        enriched = dict(row)
        if "text" not in enriched and row.get("doc_id") is not None:
            text = text_lookup.get(str(row.get("doc_id")))
            if text:
                enriched["text"] = text
        if not isinstance(enriched.get("text"), str) or not enriched["text"].strip():
            missing += 1
            enriched["text"] = ""
        else:
            enriched["text"] = enriched["text"].strip()
        out.append(enriched)
    return out, missing


def normalize_feature_token(value: Any) -> str:
    value = str(value).strip().lower()
    if not value:
        return "blank"
    value = re.sub(r"\\s+", "_", value)
    value = re.sub(r"[^a-z0-9_./:+-]", "_", value)
    return value


def tokenize(text: str) -> list[str]:
    return [m.group(0) for m in TOKEN_RE.finditer(str(text or ""))]


def word_tokens(text: str, *, lower: bool = True) -> list[str]:
    if lower:
        return [m.group(0).lower() for m in WORD_RE.finditer(str(text or ""))]
    return [m.group(0) for m in WORD_RE.finditer(str(text or ""))]


def add_ngram_features(features: dict[str, float], items: list[str], n: int, prefix: str) -> None:
    if len(items) < n:
        return
    for i in range(0, len(items) - n + 1):
        gram = "|".join(items[i : i + n])
        key = f"{prefix}={gram}"
        features[key] = features.get(key, 0.0) + 1.0


def row_feature_map(row: dict[str, Any], feature_fn: Callable[[dict[str, Any]], dict[str, float]]) -> dict[str, float]:
    return feature_fn(row)


def rrf_numeric_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    raw = row.get("features")
    if not isinstance(raw, dict):
        return feats
    for key, value in raw.items():
        if key in LEAKAGE_FEATURES:
            continue
        if isinstance(value, bool):
            feats[f"rrf_num::{key}"] = float(value)
        elif isinstance(value, (int, float)):
            feats[f"rrf_num::{key}"] = float(value)
    return feats


def _rrf_sequence_items(row: dict[str, Any], field: str) -> list[str]:
    values = row.get(field)
    if not isinstance(values, list):
        return []
    return [normalize_feature_token(v) for v in values if str(v).strip()]


def _add_skip_bigram_features(features: dict[str, float], items: list[str], skip: int, prefix: str) -> None:
    if len(items) <= skip + 1:
        return
    step = skip + 1
    for i in range(0, len(items) - step):
        gram = f"{items[i]}|{items[i + step]}"
        key = f"{prefix}::skip={skip}::{gram}"
        features[key] = features.get(key, 0.0) + 1.0


def _collapse_adjacent_repeats(items: list[str]) -> tuple[list[str], list[int]]:
    if not items:
        return [], []
    collapsed: list[str] = []
    run_lengths: list[int] = []
    current = items[0]
    current_run = 1
    for item in items[1:]:
        if item == current:
            current_run += 1
            continue
        collapsed.append(current)
        run_lengths.append(current_run)
        current = item
        current_run = 1
    collapsed.append(current)
    run_lengths.append(current_run)
    return collapsed, run_lengths


def _add_transition_features(features: dict[str, float], items: list[str], prefix: str) -> None:
    for left, right in zip(items, items[1:]):
        key = f"{prefix}::{left}::{right}"
        features[key] = features.get(key, 0.0) + 1.0


def rrf_sequence_features(row: dict[str, Any], n: int) -> dict[str, float]:
    feats: dict[str, float] = {}
    for field in RRF_SEQUENCE_FIELDS:
        items = _rrf_sequence_items(row, field)
        if not items:
            continue
        add_ngram_features(feats, items, n, f"rrf_seq{n}::{field}")
    return feats


def rrf_sequence_unigram_features(row: dict[str, Any]) -> dict[str, float]:
    return rrf_sequence_features(row, 1)


def rrf_sequence_bigram_features(row: dict[str, Any]) -> dict[str, float]:
    return rrf_sequence_features(row, 2)


def rrf_all_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    for feature_fn in (rrf_numeric_features, rrf_sequence_unigram_features, rrf_sequence_bigram_features):
        for key, value in feature_fn(row).items():
            feats[key] = feats.get(key, 0.0) + value
    return feats


def rrf_term_sequence_advanced_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    items = _rrf_sequence_items(row, "sumo_term_sequence")
    if not items:
        return feats
    for ngram_n in (1, 2, 3):
        add_ngram_features(feats, items, ngram_n, f"rrf_term::n={ngram_n}")
    _add_skip_bigram_features(feats, items, skip=1, prefix="rrf_term")
    repeats = 0
    for left, right in zip(items, items[1:]):
        if left == right:
            repeats += 1
            feats[f"rrf_term::adj_repeat::{left}"] = feats.get(f"rrf_term::adj_repeat::{left}", 0.0) + 1.0
    feats["rrf_term::adj_repeat_count"] = float(repeats)
    collapsed_items, run_lengths = _collapse_adjacent_repeats(items)
    feats["rrf_term::collapsed_len"] = float(len(collapsed_items))
    for idx, run_length in enumerate(run_lengths):
        feats[f"rrf_term::collapse_run::{idx}::{run_length}"] = float(run_length)
    for ngram_n in (1, 2, 3):
        add_ngram_features(feats, collapsed_items, ngram_n, f"rrf_term_collapsed::n={ngram_n}")
    return feats


def rrf_class_sequence_ngrams_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    items = _rrf_sequence_items(row, "sumo_class_sequence")
    if not items:
        return feats
    for ngram_n in (1, 2, 3):
        add_ngram_features(feats, items, ngram_n, f"rrf_class::n={ngram_n}")
    return feats


def rrf_proposition_aligned_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    kinds = _rrf_sequence_items(row, "proposition_kind_sequence")
    sources = _rrf_sequence_items(row, "proposition_source_sequence")
    aligned_len = min(len(kinds), len(sources))
    if aligned_len == 0:
        return feats
    aligned: list[str] = [f"{kinds[i]}::{sources[i]}" for i in range(aligned_len)]
    feats["rrf_prop::aligned_length"] = float(aligned_len)
    for ngram_n in (1, 2, 3):
        add_ngram_features(feats, aligned, ngram_n, f"rrf_prop::aligned_n={ngram_n}")
    _add_transition_features(feats, kinds[:aligned_len], "rrf_prop::kind_transition")
    _add_transition_features(feats, sources[:aligned_len], "rrf_prop::source_transition")
    _add_transition_features(feats, aligned, "rrf_prop::aligned_transition")
    feats["rrf_prop::kind_len"] = float(len(kinds))
    feats["rrf_prop::source_len"] = float(len(sources))
    feats["rrf_prop::alignment_delta"] = float(abs(len(kinds) - len(sources)))
    return feats


def _coarse_group_tokens(row: dict[str, Any]) -> list[str]:
    terms = _rrf_sequence_items(row, "sumo_term_sequence")
    classes = _rrf_sequence_items(row, "sumo_class_sequence")
    kinds = _rrf_sequence_items(row, "proposition_kind_sequence")
    sources = _rrf_sequence_items(row, "proposition_source_sequence")
    total_len = max(len(terms), len(classes), len(kinds), len(sources))
    if total_len == 0:
        return []
    tokens: list[str] = []
    for index in range(total_len):
        parts: list[str] = []
        if index < len(terms):
            parts.append("T")
        if index < len(classes):
            parts.append("C")
        if index < len(kinds):
            parts.append("K")
        if index < len(sources):
            parts.append("S")
        tokens.append("".join(parts))
    return tokens


def rrf_meta_group_sequence_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    group_tokens = _coarse_group_tokens(row)
    if not group_tokens:
        return feats
    feats["rrf_meta::token_count"] = float(len(group_tokens))
    for ngram_n in (1, 2, 3):
        add_ngram_features(feats, group_tokens, ngram_n, f"rrf_meta::seq_n={ngram_n}")
    for window in (2, 3, 4):
        if window > len(group_tokens):
            continue
        for start in range(0, len(group_tokens) - window + 1):
            chunk_idx = start // window
            chunk = group_tokens[start : start + window]
            for ngram_n in (1, 2, 3):
                add_ngram_features(
                    feats,
                    chunk,
                    ngram_n,
                    f"rrf_meta::window={window}::chunk={chunk_idx}",
                )
    return feats


def token_type_of(token: str) -> str:
    if not token:
        return "EMPTY"
    if token.isdigit():
        return "NUM"
    if token.isalpha():
        if token.isupper() and len(token) > 1:
            return "CAPS"
        if token.istitle():
            return "TITLE"
        if token.islower():
            return "LOWER"
        return "ALPHA_MIXED"
    if all(not ch.isalnum() for ch in token):
        return "PUNCT"
    if any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token):
        return "ALNUM"
    return "OTHER"


def token_type_sequence_features(row: dict[str, Any], n: int = 2) -> dict[str, float]:
    feats: dict[str, float] = {}
    categories = [token_type_of(token) for token in tokenize(row.get("text", ""))]
    if not categories:
        return feats
    for gram_n in (1, n):
        add_ngram_features(feats, categories, gram_n, f"toktype::{gram_n}")
    return feats


def posish_category(token: str) -> str:
    if not token:
        return "EMPTY"
    if all(not ch.isalnum() for ch in token):
        return "PUNCT"
    if token.isdigit():
        return "NUM"
    lower = token.lower()
    if lower in DET_WORDS:
        return "DET"
    if lower in PRONOUN_WORDS:
        return "PRON"
    if lower in MODAL_WORDS:
        return "MODAL"
    if lower in AUX_WORDS:
        return "AUX"
    if lower in PREP_WORDS:
        return "PREP"
    if lower in CONJ_WORDS:
        return "CONJ"
    if lower in ADV_WORDS or lower.endswith("ly"):
        return "ADV"
    if lower.endswith("ing") and len(lower) >= 4:
        return "GERUND"
    if lower.endswith("ed") and len(lower) >= 3:
        return "PAST"
    if lower.isupper() and len(token) > 1:
        return "CAPS"
    return "NOUNISH"


def posish_sequence_features(row: dict[str, Any], n: int = 2) -> dict[str, float]:
    feats: dict[str, float] = {}
    categories = [posish_category(token) for token in tokenize(row.get("text", ""))]
    if not categories:
        return feats
    for gram_n in (1, n):
        add_ngram_features(feats, categories, gram_n, f"posish::{gram_n}")
    return feats


def char_shape(token_char: str) -> str:
    if token_char.isupper():
        return "U"
    if token_char.islower():
        return "l"
    if token_char.isdigit():
        return "D"
    if token_char.isspace():
        return "S"
    if token_char in ".,!?;:-()[]{}\"'":
        return "P"
    return "O"


def char_shape_sequence_features(row: dict[str, Any], ngram_sizes: tuple[int, ...] = (1, 2, 3)) -> dict[str, float]:
    feats: dict[str, float] = {}
    text = str(row.get("text", ""))
    if not text:
        return feats
    shapes = [char_shape(ch) for ch in text]
    for gram_n in ngram_sizes:
        add_ngram_features(feats, shapes, gram_n, f"shape::{gram_n}")
    return feats


def style_stats_features(row: dict[str, Any]) -> dict[str, float]:
    text = str(row.get("text", ""))
    toks = word_tokens(text, lower=False)
    toks_lower = word_tokens(text)
    word_count = len(toks)
    unique_words = len(set(toks_lower))
    letters = [ch for ch in text if ch.isalpha()]
    sentence_count = max(1, len(SENTENCE_RE.findall(text)))
    punct = sum(1 for ch in text if not ch.isalnum() and not ch.isspace())
    upper = sum(1 for tok in toks if tok and tok[0].isupper())
    lower = sum(1 for tok in toks if tok.islower())
    return {
        "style::words": float(word_count),
        "style::unique_words": float(unique_words),
        "style::chars": float(len(text)),
        "style::letters": float(len(letters)),
        "style::sentences": float(sentence_count),
        "style::punct": float(punct),
        "style::upper_tokens": float(upper),
        "style::lower_tokens": float(lower),
        "style::avg_word_len": sum(len(tok) for tok in toks_lower) / max(1, word_count),
        "style::lexical_diversity": unique_words / max(1, word_count),
        "style::words_per_sentence": word_count / max(1, sentence_count),
        "style::punct_ratio": punct / max(1, len(text)),
        "style::alpha_ratio": len(letters) / max(1, len(text)),
        "style::upper_ratio": upper / max(1, word_count),
    }


def text_lexical_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    toks = word_tokens(row.get("text", ""))
    if not toks:
        return feats
    add_ngram_features(feats, toks, 1, "lex::1")
    add_ngram_features(feats, toks, 2, "lex::2")
    return feats


def text_rrf_posish_features(row: dict[str, Any]) -> dict[str, float]:
    feats: dict[str, float] = {}
    for feature_fn in (rrf_all_features, text_lexical_features, posish_sequence_features, style_stats_features):
        for key, value in feature_fn(row).items():
            feats[key] = feats.get(key, 0.0) + value
    return feats


def build_vocab(counter: Counter[str], min_frequency: int, max_features: int | None) -> list[str]:
    candidates = [(k, c) for k, c in counter.items() if c >= min_frequency]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    if max_features:
        candidates = candidates[:max_features]
    return [k for k, _ in candidates]


def vectorize(rows: list[dict[str, float]], vocab: list[str]) -> list[list[float]]:
    idx = {key: i for i, key in enumerate(vocab)}
    matrix: list[list[float]] = [[0.0] * len(vocab) for _ in rows]
    for row_i, row_features in enumerate(rows):
        for key, value in row_features.items():
            j = idx.get(key)
            if j is not None:
                matrix[row_i][j] = float(value)
    return matrix


def standardize_train(matrix: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    width = len(matrix[0]) if matrix else 0
    means: list[float] = []
    stds: list[float] = []
    for c in range(width):
        vals = [row[c] for row in matrix]
        mean = sum(vals) / max(1, len(vals))
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals))
        std = math.sqrt(var) or 1.0
        means.append(mean)
        stds.append(std)
    return (
        [[(row[c] - means[c]) / stds[c] for c in range(width)] for row in matrix],
        means,
        stds,
    )


def standardize_apply(matrix: list[list[float]], means: list[float], stds: list[float]) -> list[list[float]]:
    return [[(row[c] - means[c]) / stds[c] for c in range(len(means))] for row in matrix]


def sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def dot(row: list[float], weights: list[float]) -> float:
    return sum(a * b for a, b in zip(row, weights, strict=True))


def train_lr(
    rows_features: list[dict[str, float]],
    labels: list[int],
    *,
    min_frequency: int,
    max_features: int | None = None,
    epochs: int = 500,
    lr: float = 0.1,
    l2: float = 0.02,
    sparse: bool = False,
) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    for row in rows_features:
        counter.update(row.keys())
    vocab = build_vocab(counter, min_frequency=min_frequency, max_features=max_features)
    if sparse:
        model = train_lr_sparse(rows_features, labels, vocab, min_frequency=min_frequency, max_features=max_features, epochs=epochs, lr=lr, l2=l2)
        model["training_backend"] = "sparse_python"
        return model
    x_raw = vectorize(rows_features, vocab)
    x, means, stds = standardize_train(x_raw)
    y = list(labels)
    weights = [0.0] * len(vocab)
    bias = 0.0
    n = max(1, len(rows_features))
    for _ in range(epochs):
        grad_w = [0.0] * len(vocab)
        grad_b = 0.0
        for xi, yi in zip(x, y, strict=True):
            p = sigmoid(dot(xi, weights) + bias)
            error = p - yi
            grad_b += error
            for j, val in enumerate(xi):
                if val:
                    grad_w[j] += error * val
        for j in range(len(weights)):
            weights[j] -= lr * (grad_w[j] / n + l2 * weights[j])
        bias -= lr * (grad_b / n)
    return {
        "vocab": vocab,
        "weights": weights,
        "bias": bias,
        "means": means,
        "stds": stds,
        "min_frequency": min_frequency,
        "max_features": max_features,
        "epochs": epochs,
        "lr": lr,
        "l2": l2,
        "training_backend": "dense_python",
    }


def train_lr_sparse(
    rows_features: list[dict[str, float]],
    labels: list[int],
    vocab: list[str],
    *,
    min_frequency: int,
    max_features: int | None = None,
    epochs: int = 500,
    lr: float = 0.1,
    l2: float = 0.02,
) -> dict[str, Any]:
    idx = {key: i for i, key in enumerate(vocab)}
    n = max(1, len(rows_features))
    width = len(vocab)
    sums = [0.0] * width
    sumsq = [0.0] * width
    sparse_rows: list[list[tuple[int, float]]] = []
    for row_features in rows_features:
        row_items: list[tuple[int, float]] = []
        for key, value in row_features.items():
            j = idx.get(key)
            if j is None:
                continue
            val = float(value)
            if val:
                row_items.append((j, val))
                sums[j] += val
                sumsq[j] += val * val
        sparse_rows.append(row_items)
    means = [value / n for value in sums]
    stds = []
    for j in range(width):
        var = (sums[j] * means[j] * -2.0 + sumsq[j]) / n + means[j] * means[j]
        stds.append(math.sqrt(max(0.0, var)) or 1.0)
    weights = [0.0] * width
    bias = 0.0
    y = list(labels)
    mean_over_std = [means[j] / stds[j] for j in range(width)]
    active_features = [j for j, value in enumerate(mean_over_std) if value]
    zero_offset = -sum(weights[j] * mean_over_std[j] for j in active_features)
    for _ in range(epochs):
        grad_w = [0.0] * width
        grad_b = 0.0
        total_error = 0.0
        for items, yi in zip(sparse_rows, y, strict=True):
            score = bias + zero_offset
            for j, raw in items:
                score += weights[j] * (raw / stds[j])
            p = sigmoid(score)
            error = p - yi
            total_error += error
            grad_b += error
            for j, raw in items:
                grad_w[j] += error * (raw / stds[j])
        if total_error:
            for j in active_features:
                grad_w[j] -= total_error * mean_over_std[j]
        for j in range(width):
            weights[j] -= lr * (grad_w[j] / n + l2 * weights[j])
        bias -= lr * (grad_b / n)
        zero_offset = -sum(weights[j] * mean_over_std[j] for j in active_features)
    return {
        "vocab": vocab,
        "weights": weights,
        "bias": bias,
        "means": means,
        "stds": stds,
        "min_frequency": min_frequency,
        "max_features": max_features,
        "epochs": epochs,
        "lr": lr,
        "l2": l2,
    }


def predict(
    model: dict[str, Any],
    rows_features: list[dict[str, float]],
) -> tuple[list[float], list[str]]:
    x = standardize_apply(vectorize(rows_features, list(model["vocab"])), list(model["means"]), list(model["stds"]))
    weights = [float(v) for v in model["weights"]]
    bias = float(model["bias"])
    probs = [sigmoid(dot(xi, weights) + bias) for xi in x]
    return probs, model["vocab"]


def evaluate(
    rows: list[dict[str, Any]],
    rows_features: list[dict[str, float]],
    model: dict[str, Any],
) -> dict[str, Any]:
    probs, _ = predict(model, rows_features)
    correct = 0
    confusion: Counter[str] = Counter()
    predictions: list[dict[str, Any]] = []
    for row, prob in zip(rows, probs, strict=True):
        actual_i = int(row["ai_generated_label"])
        pred_i = int(prob >= 0.5)
        actual = INT_TO_LABEL[actual_i]
        pred = INT_TO_LABEL[pred_i]
        ok = actual_i == pred_i
        correct += int(ok)
        confusion[f"{actual}->{pred}"] += 1
        predictions.append(
            {
                "doc_id": row.get("doc_id"),
                "dataset": row.get("dataset"),
                "domain": row.get("domain"),
                "doc_type": row.get("doc_type"),
                "actual": actual,
                "predicted": pred,
                "ai_generated_probability": round(float(prob), 6),
                "correct": bool(ok),
            }
        )
    return {
        "row_count": len(rows),
        "correct_count": correct,
        "accuracy": correct / max(1, len(rows)),
        "confusion": dict(confusion),
        "predictions": predictions,
        "vocab_size": len(model["vocab"]),
    }


def method_specs(text_vocab_max_features: int, text_rrf_posish_vocab_max_features: int, common_min_frequency: int) -> list[dict[str, Any]]:
    return [
        {
            "name": "rrf_numeric",
            "builder": rrf_numeric_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_sequence_unigrams",
            "builder": rrf_sequence_unigram_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_sequence_bigrams",
            "builder": rrf_sequence_bigram_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_all",
            "builder": rrf_all_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_ontology_term_advanced_sequence",
            "builder": rrf_term_sequence_advanced_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_ontology_class_ngrams",
            "builder": rrf_class_sequence_ngrams_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_ontology_proposition_aligned_ngrams_transitions",
            "builder": rrf_proposition_aligned_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "rrf_ontology_meta_grouped_sequence_windows",
            "builder": rrf_meta_group_sequence_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": False,
        },
        {
            "name": "token_type_sequence_ngrams",
            "builder": token_type_sequence_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": True,
        },
        {
            "name": "posish_sequence_ngrams",
            "builder": posish_sequence_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": True,
        },
        {
            "name": "char_shape_sequence_ngrams",
            "builder": char_shape_sequence_features,
            "min_frequency": common_min_frequency,
            "max_features": None,
            "requires_text": True,
        },
        {
            "name": "style_stats",
            "builder": style_stats_features,
            "min_frequency": 1,
            "max_features": None,
            "requires_text": True,
        },
        {
            "name": "text_lexical_limited",
            "builder": text_lexical_features,
            "min_frequency": common_min_frequency,
            "max_features": text_vocab_max_features,
            "requires_text": True,
        },
        {
            "name": "text_rrf_posish",
            "builder": text_rrf_posish_features,
            "min_frequency": common_min_frequency,
            "max_features": text_rrf_posish_vocab_max_features,
            "requires_text": True,
        },
    ]


def default_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[2] / "evals" / "corporate_sequence_model" / Path(*parts)


def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name)


def run(args: argparse.Namespace) -> dict[str, Any]:
    all_rrf_rows = grounded_hard_labeled(read_jsonl(args.input))
    text_lookup = build_text_lookup([args.hard_labeled_input, args.normalized_corpus_input])
    all_rows, missing_text_total = attach_text(all_rrf_rows, text_lookup)

    sample = balanced_sample(all_rows, args.sample_size, args.seed)
    train_rows, test_rows = stratified_split(sample, args.test_ratio)

    train_labels = [int(r["ai_generated_label"]) for r in train_rows]
    test_labels = [int(r["ai_generated_label"]) for r in test_rows]

    methods = method_specs(args.text_lexical_max_features, args.text_rrf_posish_max_features, args.min_frequency)
    results: list[dict[str, Any]] = []

    for method in methods:
        name = method["name"]
        builder = method["builder"]
        train_features = [row_feature_map(row, builder) for row in train_rows]
        test_features = [row_feature_map(row, builder) for row in test_rows]

        model = train_lr(
            train_features,
            train_labels,
            min_frequency=int(method["min_frequency"]),
            max_features=method["max_features"],
            epochs=args.epochs,
            lr=args.learning_rate,
            l2=args.l2,
        )

        train_metrics = evaluate(train_rows, train_features, model)
        test_metrics = evaluate(test_rows, test_features, model)

        predictions_path = args.output_dir / f"{sanitize_name(name)}_predictions.jsonl"
        write_jsonl(predictions_path, test_metrics["predictions"])

        method_result = {
            "method": name,
            "vocab_size": model["vocab_size"] if "vocab_size" in model else len(model["vocab"]),
            "min_frequency": int(method["min_frequency"]),
            "max_features": method["max_features"],
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
            "train_accuracy": train_metrics["accuracy"],
            "test_accuracy": test_metrics["accuracy"],
            "test_confusion": test_metrics["confusion"],
            "predictions_jsonl": str(predictions_path),
        }
        if method["requires_text"]:
            missing_method_text = sum(1 for row in test_rows if not str(row.get("text", "")).strip())
            method_result["missing_text_rows"] = missing_method_text
        results.append(method_result)

    method_result_rows = [
        {
            "method": result["method"],
            "test_accuracy": result["test_accuracy"],
            "confusion": result["test_confusion"],
        }
        for result in results
    ]

    comparison = {
        "schema": "corporate.ai_authorship_feature_spike.v1",
        "input": str(args.input),
        "hard_labeled_lookup": str(args.hard_labeled_input),
        "normalized_corpus_lookup": str(args.normalized_corpus_input),
        "sample_size": args.sample_size,
        "seed": args.seed,
        "test_ratio": args.test_ratio,
        "sample_rows": len(sample),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "sample_label_counts": dict(Counter(str(r["ai_generated_label"]) for r in sample)),
        "missing_text_rows_total": missing_text_total,
        "methods": results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "method_comparison.json", comparison)
    write_markdown(
        args.output_dir / "method_comparison.md",
        generate_markdown_table(method_result_rows),
    )

    # Keep stdout concise: summary table only.
    print(f"{'method':35s}  {'test_acc':>8s}  {'confusion'}")
    for result in results:
        print(
            f"{result['method']:35s}  {result['test_accuracy']:8.4f}  {json.dumps(result['test_confusion'], sort_keys=True)}"
        )

    return comparison


def generate_markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = ["# Corporate AI Authorship Feature Spike", "", "| method | test_accuracy | confusion |", "|---|---:|---|"]
    for row in rows:
        lines.append(
            f"| {row['method']} | {row['test_accuracy']:.4f} | {json.dumps(row['confusion'], sort_keys=True)} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=default_path("authorship", "test500", "rrf_features.current.jsonl"),
        help="RRF-grounded rows to benchmark.",
    )
    parser.add_argument(
        "--hard-labeled-input",
        type=Path,
        default=default_path("authorship", "ai_authorship_hard_labeled_balanced.jsonl"),
        help="Balanced supervised corpus with text for doc_id join.",
    )
    parser.add_argument(
        "--normalized-corpus-input",
        type=Path,
        default=default_path("hf_normalized_corpus.extended.jsonl"),
        help="Extended normalized corpus used as fallback text source.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_path("authorship", "spike_methods"),
        help="Directory where comparison reports and per-method predictions are written.",
    )
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260521)
    parser.add_argument("--test-ratio", type=float, default=0.25)
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--text-lexical-max-features", type=int, default=4000)
    parser.add_argument("--text-rrf-posish-max-features", type=int, default=8000)
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=0.02)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
