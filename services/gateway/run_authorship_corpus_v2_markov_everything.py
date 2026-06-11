from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from app.corporate_ai_authorship_feature_spike import (
    INT_TO_LABEL,
    char_shape_sequence_features,
    evaluate,
    posish_sequence_features,
    read_jsonl,
    style_stats_features,
    text_lexical_features,
    token_type_sequence_features,
    train_lr,
    write_json,
    write_jsonl,
)
from app.corporate_markov_features import (
    fit_surface_markov_models,
    surface_markov_features,
    surface_markov_model_summary,
)
from app.corporate_sumo_model_smoke import vectorize_row
from app.corporate_wordnet_feature_rows import transform_wordnet_feature_row

BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR / ".." / "evals" / "corporate_sequence_model"
DEFAULT_TRAIN = EVAL_DIR / "authorship_corpus_v2" / "supervised_train_mix.jsonl"
DEFAULT_TEST = EVAL_DIR / "authorship_corpus_v2" / "supervised_test_mix.jsonl"
DEFAULT_WIKI = EVAL_DIR / "authorship_corpus_v2" / "calibration_hc3_wiki.jsonl"
DEFAULT_QA = EVAL_DIR / "authorship_corpus_v2" / "calibration_hc3_qa.jsonl"
DEFAULT_OUTPUT = EVAL_DIR / "authorship_corpus_v2_markov_everything"

WORDNET_PREFIXES = (
    "seq::wordnet_synset_sequence::",
    "seq::wordnet_synonym_match_sequence::",
    "seq::wordnet_lexname_sequence::",
    "seq::wordnet_pos_sequence::",
    "seq::wordnet_category_sequence::",
    "num::wordnet_",
)

REAL_WORLD_DEFAULT_MIN_CHUNK_WORDS = 100
REAL_WORLD_DEFAULT_MAX_CHUNK_WORDS = 320

ARTICLE_SECTION_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "methods",
    "method",
    "methodology",
    "approach",
    "results",
    "discussion",
    "conclusion",
    "conclusions",
    "references",
    "appendix",
}

NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
DATE_RE = re.compile(
    r"\b(?:(?:19|20)\d{2}|"
    r"\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|sept|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|sept|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{2}|"
    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\s+of\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|sept|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
EVIDENCE_MARKER_RE = re.compile(r"\b(according to|reported|report|study|studies|survey|data|source|sources|filing|filed|published|evidence)\b", re.IGNORECASE)
CLAIM_MARKER_RE = re.compile(r"\b(says?|said|expect(s|ed|ing)?|plan(ned|s)?|aim(ed|s)?|promis(es|ed|ing)?|will|must|should|could|would|might|intend(ed)?|target(ed)?|expects?)\b", re.IGNORECASE)
NAMED_ANCHOR_RE = re.compile(r"\b(?:[A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+|[A-Z]{2,})\b")
ABSTRACT_TOKENS = {
    "some",
    "many",
    "various",
    "multiple",
    "improve",
    "increase",
    "decrease",
    "potential",
    "likely",
    "unlikely",
    "approximately",
    "around",
    "roughly",
    "generic",
    "important",
    "significant",
    "notable",
    "likely",
    "support",
    "help",
}
WORDNET_EVIDENCE_KEYS = ("wordnet_abstract_ratio", "wordnet_concrete_ratio", "wordnet_generic_ratio")
SEMANTIC_MARKOV_PREFIXES = (
    "markov::semantic::",
    "seqng::semantic::",
    "semantic::",
)
CONCEPT_SEQUENCE_FIELDS = {
    "wordnet": (
        "wordnet_pos_sequence",
        "wordnet_lexname_sequence",
        "wordnet_synset_sequence",
        "wordnet_category_sequence",
        "wordnet_synonym_match_sequence",
        "wordnet_antonym_match_sequence",
    ),
    "wordnet_sumo": (
        "wordnet_sumo_term_sequence",
        "wordnet_sumo_relation_sequence",
    ),
    "sumo": (
        "sumo_term_sequence",
        "sumo_class_sequence",
        "proposition_kind_sequence",
        "proposition_source_sequence",
        "unresolved_surface_sequence",
        "unresolved_type_sequence",
    ),
}


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _word_count(text: str) -> int:
    return len((text or "").split())


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _heading_body(line: str) -> str | None:
    stripped = _normalize_heading(line)
    if not stripped or len(stripped) > 120:
        return None

    numbered = re.match(r"^(?:[0-9]+(?:\.[0-9]+)*|[A-Z])\.?\s+(.+)$", stripped)
    body = numbered.group(1).strip() if numbered else stripped
    lower_body = body.lower()
    if lower_body in ARTICLE_SECTION_HEADINGS:
        return body
    if not numbered:
        return None
    return body


def _is_probable_heading(line: str) -> bool:
    body = _heading_body(line)
    if not body:
        return False

    words = body.split()
    if len(words) > 14:
        return False
    if body[-1:] in ".!?;:":
        return False

    letters = sum(character.isalpha() for character in body)
    digits = sum(character.isdigit() for character in body)
    if letters < 3:
        return False
    if digits and letters / max(1, letters + digits) < 0.65:
        return False

    alpha_words = [re.sub(r"[^A-Za-z]", "", word) for word in words]
    alpha_words = [word for word in alpha_words if word]
    if not alpha_words:
        return False
    lowercase_starters = sum(word[0].islower() for word in alpha_words)
    if lowercase_starters > max(1, len(alpha_words) // 2):
        return False

    return True


def _split_into_sections(text: str) -> list[dict[str, str]]:
    normalized = re.sub(r"\r\n", "\n", str(text or "").strip())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    if not normalized:
        return []

    lines = normalized.split("\n")
    sections: list[dict[str, list[str] | str]] = []
    current_heading = "front matter"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        if body:
            sections.append({"heading": current_heading, "lines": current_lines})
        current_lines = []

    for line in lines:
        if _is_probable_heading(line):
            flush()
            current_heading = _normalize_heading(line)
            continue
        current_lines.append(line)
    flush()

    if not sections:
        return [{"heading": "document", "text": normalized}]

    merged: list[dict[str, str]] = []
    for section in sections:
        heading = str(section["heading"])
        body = "\n".join(section["lines"]).strip()
        if not body:
            continue
        if merged and heading.lower() != "references" and _word_count(body) < 80:
            previous = merged[-1]
            previous["text"] = f"{previous['text']}\n\n{heading}\n{body}".strip()
            continue
        merged.append({"heading": heading, "text": body})
    return merged or [{"heading": "document", "text": normalized}]


def _chunk_long_paragraph(text: str, *, max_words: int) -> list[dict[str, Any]]:
    words = text.split()
    if not words:
        return []
    chunks: list[dict[str, Any]] = []
    for start in range(0, len(words), max_words):
        piece = " ".join(words[start : start + max_words])
        chunks.append({"text": piece, "word_count": _word_count(piece)})
    return chunks


def chunk_article_prose(
    text: str,
    *,
    min_words: int = REAL_WORLD_DEFAULT_MIN_CHUNK_WORDS,
    max_words: int = REAL_WORLD_DEFAULT_MAX_CHUNK_WORDS,
    allow_isolated_short_chunks: bool = False,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    sections = _split_into_sections(text)
    if not sections:
        return []

    for section in sections:
        heading = str(section["heading"])
        section_paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", str(section["text"])) if paragraph.strip()]
        if not section_paragraphs:
            continue

        buffered_parts: list[str] = []
        buffered_words = 0

        def emit_buffered() -> None:
            if not buffered_parts:
                return
            body = "\n\n".join(buffered_parts).strip()
            heading_prefix = f"{heading}\n\n" if heading not in {"front matter", "document"} else ""
            chunk_text = f"{heading_prefix}{body}".strip()
            chunks.append(
                {
                    "text": chunk_text,
                    "word_count": _word_count(chunk_text),
                    "section_heading": heading,
                    "chunk_type": "article_section_merge",
                }
            )

        for paragraph in section_paragraphs:
            paragraph_words = _word_count(paragraph)
            if paragraph_words >= max_words:
                emit_buffered()
                buffered_parts = []
                buffered_words = 0
                for piece in _chunk_long_paragraph(paragraph, max_words=max_words):
                    heading_prefix = f"{heading}\n\n" if heading not in {"front matter", "document"} else ""
                    piece_text = f"{heading_prefix}{piece['text']}" if heading_prefix else piece['text']
                    chunks.append({
                        **piece,
                        "text": piece_text,
                        "section_heading": heading,
                        "chunk_type": "article_long_paragraph",
                    })
                continue

            if buffered_parts and buffered_words + paragraph_words + len(buffered_parts) > max_words:
                emit_buffered()
                buffered_parts = []
                buffered_words = 0

            buffered_parts.append(paragraph)
            buffered_words += paragraph_words

        emit_buffered()

    if not allow_isolated_short_chunks and len(chunks) > 1:
        chunks = [chunk for chunk in chunks if chunk["word_count"] >= min_words]

    if not chunks:
        return []

    # Avoid scoring isolated short chunks unless explicitly requested.
    if not allow_isolated_short_chunks and chunks and max(chunk["word_count"] for chunk in chunks) < min_words:
        return []

    return [
        {
            **chunk,
            "index": index + 1,
            "chunk_total": len(chunks),
            "chunk_word_count": chunk["word_count"],
        }
        for index, chunk in enumerate(chunks)
    ]


def build_evidence_feature_row(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    sentences = [item.strip() for item in SENTENCE_SPLIT_RE.split(text or "") if item.strip()]

    evidence_marker_count = len(EVIDENCE_MARKER_RE.findall(lowered))
    date_anchor_count = len(DATE_RE.findall(text or ""))
    number_anchor_count = len(NUMBER_RE.findall(text or ""))
    named_anchor_count = len(NAMED_ANCHOR_RE.findall(text or ""))

    claim_sentences = 0
    for sentence in sentences:
        if CLAIM_MARKER_RE.search(sentence):
            claim_sentences += 1

    tokens = re.findall(r"[a-z']+", lowered)
    token_count = max(1, len(tokens))
    abstract_token_count = sum(1 for token in tokens if token in ABSTRACT_TOKENS)

    claim_evidence_gap = 0.0
    if claim_sentences > 0:
        claim_evidence_gap = max(0.0, (claim_sentences - evidence_marker_count) / claim_sentences)

    return {
        "claim_evidence_gap": float(claim_evidence_gap),
        "claim_sentence_count": int(claim_sentences),
        "evidence_marker_count": int(evidence_marker_count),
        "named_anchor_count": int(named_anchor_count),
        "date_anchor_count": int(date_anchor_count),
        "count_anchor_count": int(number_anchor_count),
        "abstract_ratio": abstract_token_count / token_count,
    }


def build_wordnet_evidence_ratio_features(row: dict[str, Any]) -> dict[str, float]:
    defaults = {key: 0.0 for key in WORDNET_EVIDENCE_KEYS}
    try:
        enriched = transform_wordnet_feature_row(row, {})
        vector = vectorize_row(enriched)
        return {
            "wordnet_abstract_ratio": _safe_float(
                vector.get("num::wordnet_abstract_lexicon_ratio", defaults["wordnet_abstract_ratio"])
            ),
            "wordnet_concrete_ratio": _safe_float(
                vector.get("num::wordnet_concrete_lexicon_ratio", defaults["wordnet_concrete_ratio"])
            ),
            "wordnet_generic_ratio": _safe_float(
                vector.get("num::wordnet_generic_lexicon_ratio", defaults["wordnet_generic_ratio"])
            ),
        }
    except Exception:
        return defaults


def build_real_world_calibration_rows(
    path: Path,
    *,
    chunking_strategy: str = "article_prose",
    min_chunk_words: int = REAL_WORLD_DEFAULT_MIN_CHUNK_WORDS,
    max_chunk_words: int = REAL_WORLD_DEFAULT_MAX_CHUNK_WORDS,
    allow_isolated_short_chunks: bool = False,
) -> list[dict[str, Any]]:
    raw_rows = read_jsonl(path)
    out: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        label = parse_label(raw)
        if label is None:
            continue

        source_text = _coerce_text(
            raw.get("text")
            or raw.get("normalized_text")
            or raw.get("document_text")
            or raw.get("content")
        )
        if not source_text:
            continue

        base = dict(raw)
        base["ai_generated_label"] = label
        base.setdefault("source_type", INT_TO_LABEL[label])
        base.setdefault("dataset", "unknown")
        base.setdefault("domain", "unknown")
        base.setdefault("doc_type", "unknown")
        base.setdefault("corpus_role", "real_world")
        base["text"] = source_text

        if chunking_strategy == "article_prose":
            chunks = chunk_article_prose(
                source_text,
                min_words=min_chunk_words,
                max_words=max_chunk_words,
                allow_isolated_short_chunks=allow_isolated_short_chunks,
            )
        elif chunking_strategy == "single_chunk":
            chunks = [
                {
                    "text": source_text,
                    "word_count": _word_count(source_text),
                    "section_heading": "document",
                    "chunk_type": "single",
                    "index": 1,
                    "chunk_total": 1,
                    "chunk_word_count": _word_count(source_text),
                }
            ]
        else:
            raise ValueError(f"unsupported chunking strategy: {chunking_strategy}")

        if not chunks:
            continue

        for chunk in chunks:
            row = dict(base)
            row["text"] = chunk["text"]
            row["word_count"] = chunk["word_count"]
            row["chunk_index"] = int(chunk["index"])
            row["chunk_total"] = int(chunk["chunk_total"])
            row["chunk_word_count"] = int(chunk["chunk_word_count"])
            row["chunk_section"] = chunk.get("section_heading")
            row["chunk_type"] = chunk.get("chunk_type")
            row["chunking_strategy"] = chunking_strategy
            row["chunk_min_words"] = int(min_chunk_words)
            row["chunk_max_words"] = int(max_chunk_words)
            row["allow_isolated_short_chunks"] = bool(allow_isolated_short_chunks)
            row["real_world_fixture"] = str(path)
            row["real_world_fixture_name"] = path.name
            row.update(build_evidence_feature_row(row["text"]))
            row.update(build_wordnet_evidence_ratio_features(row))
            out.append(row)
    return out


def summarize_real_world_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_rows: dict[str, int] = defaultdict(int)
    fixture_doc_types: dict[str, dict[str, int]] = {}
    fixture_chunking: dict[str, dict[str, int]] = {}
    fixture_doc_type_and_chunking: dict[str, dict[str, dict[str, int]]] = {}
    for row in rows:
        fixture = str(row.get("real_world_fixture_name", row.get("real_world_fixture", "unknown")))
        doc_type = str(row.get("doc_type", "unknown"))
        chunking = str(row.get("chunking_strategy", "unknown"))

        fixture_rows[fixture] += 1

        doc_types = fixture_doc_types.setdefault(fixture, {})
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        doc_type_and_chunking = fixture_doc_type_and_chunking.setdefault(fixture, {}).setdefault(doc_type, {})
        doc_type_and_chunking[chunking] = doc_type_and_chunking.get(chunking, 0) + 1

        chunking_counts = fixture_chunking.setdefault(fixture, {})
        chunking_counts[chunking] = chunking_counts.get(chunking, 0) + 1

    summary: dict[str, dict[str, Any]] = {}
    for fixture in sorted(fixture_rows):
        summary[fixture] = {
            "row_count": fixture_rows[fixture],
            "doc_type_counts": dict(fixture_doc_types.get(fixture, {})),
            "chunking_strategy_counts": dict(fixture_chunking.get(fixture, {})),
            "doc_type_by_chunking_strategy": dict(fixture_doc_type_and_chunking.get(fixture, {})),
        }
    return {
        "fixtures": summary,
        "total_rows": sum(fixture_rows.values()),
    }


def _mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def _numeric_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {"min": min(values), "max": max(values), "mean": _mean(values)}


def _label_name(row: dict[str, Any]) -> str:
    label = parse_label(row)
    return INT_TO_LABEL[label] if label in {0, 1} else str(row.get("source_type", "unknown"))


def _large_scale_group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "mean_claim_evidence_gap": _mean([_safe_float(row.get("claim_evidence_gap")) for row in rows]),
        "mean_evidence_marker_count": _mean([_safe_float(row.get("evidence_marker_count")) for row in rows]),
        "mean_named_anchor_count": _mean([_safe_float(row.get("named_anchor_count")) for row in rows]),
        "mean_date_anchor_count": _mean([_safe_float(row.get("date_anchor_count")) for row in rows]),
        "mean_count_anchor_count": _mean([_safe_float(row.get("count_anchor_count")) for row in rows]),
        "mean_abstract_ratio": _mean([_safe_float(row.get("abstract_ratio")) for row in rows]),
        "mean_wordnet_abstract_ratio": _mean([_safe_float(row.get("wordnet_abstract_ratio")) for row in rows]),
        "mean_wordnet_concrete_ratio": _mean([_safe_float(row.get("wordnet_concrete_ratio")) for row in rows]),
        "mean_wordnet_generic_ratio": _mean([_safe_float(row.get("wordnet_generic_ratio")) for row in rows]),
    }


def build_large_scale_real_world_calibration_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize real-world calibration chunks at scale before trusting detector scores."""
    label_counts = Counter(_label_name(row) for row in rows)
    doc_type_counts = Counter(str(row.get("doc_type", "unknown")) for row in rows)
    domain_counts = Counter(str(row.get("domain", "unknown")) for row in rows)
    chunking_counts = Counter(str(row.get("chunk_type", "unknown")) for row in rows)
    word_counts = [_safe_float(row.get("chunk_word_count", row.get("word_count"))) for row in rows]

    by_doc_type: dict[str, Any] = {}
    by_domain: dict[str, Any] = {}
    for doc_type in sorted(doc_type_counts):
        by_doc_type[doc_type] = _large_scale_group_summary([row for row in rows if str(row.get("doc_type", "unknown")) == doc_type])
    for domain in sorted(domain_counts):
        by_domain[domain] = _large_scale_group_summary([row for row in rows if str(row.get("domain", "unknown")) == domain])

    false_positive_probes = [
        row
        for row in rows
        if _label_name(row) == "human_written"
        and str(row.get("doc_type", "")) in {"news_article", "legal_news", "annual_report", "sec_filing"}
        and _safe_float(row.get("named_anchor_count")) >= 2
        and (
            _safe_float(row.get("evidence_marker_count"))
            + _safe_float(row.get("date_anchor_count"))
            + _safe_float(row.get("count_anchor_count"))
        ) >= 1
    ]
    low_evidence_ai_probes = [
        row
        for row in rows
        if _label_name(row) == "ai_generated"
        and _safe_float(row.get("evidence_marker_count")) <= 1
        and _safe_float(row.get("named_anchor_count")) <= 1
    ]

    return {
        "row_count": len(rows),
        "label_counts": dict(label_counts),
        "doc_type_counts": dict(doc_type_counts),
        "domain_counts": dict(domain_counts),
        "chunking": dict(chunking_counts),
        "chunk_word_count": _numeric_summary(word_counts),
        "short_chunk_count": sum(1 for value in word_counts if value < REAL_WORLD_DEFAULT_MIN_CHUNK_WORDS),
        "false_positive_probe_count": len(false_positive_probes),
        "low_evidence_ai_probe_count": len(low_evidence_ai_probes),
        "by_doc_type": by_doc_type,
        "by_domain": by_domain,
    }


def parse_label(row: dict[str, Any]) -> int | None:
    value = row.get("ai_generated_label")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value in {0, 1} else None
    if isinstance(value, float):
        return int(value) if value in (0.0, 1.0) else None
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"1", "true", "ai_generated", "ai", "generated"}:
            return 1
        if low in {"0", "false", "human_written", "human", "humanonly", "human-authored", "humanwritten"}:
            return 0
    source_type = str(row.get("source_type", "")).strip().lower()
    if source_type == "ai_generated":
        return 1
    if source_type == "human_written":
        return 0
    return None


def coerce_rows(path: Path, role: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in read_jsonl(path):
        label = parse_label(row)
        if label is None:
            continue
        copy = dict(row)
        copy["ai_generated_label"] = label
        copy["source_type"] = INT_TO_LABEL[label]
        copy.setdefault("dataset", "unknown")
        copy.setdefault("domain", "unknown")
        copy.setdefault("doc_type", "unknown")
        copy.setdefault("corpus_role", role)
        out.append(copy)
    return out


def build_wordnet_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            out.append(transform_wordnet_feature_row(row, {}))
        except Exception:
            out.append(dict(row))
    return out


def wordnet_features(row: dict[str, Any]) -> dict[str, float]:
    vector = vectorize_row(row)
    return {f"wn::{key}": float(value) for key, value in vector.items() if any(key.startswith(prefix) for prefix in WORDNET_PREFIXES)}


def lexical_features(row: dict[str, Any]) -> dict[str, float]:
    features: dict[str, float] = {}
    for fn in (text_lexical_features, style_stats_features):
        for key, value in fn(row).items():
            features[key] = features.get(key, 0.0) + float(value)
    return features


def shape_ngram_features(row: dict[str, Any]) -> dict[str, float]:
    features: dict[str, float] = {}
    for fn in (token_type_sequence_features, posish_sequence_features, char_shape_sequence_features):
        for key, value in fn(row).items():
            features[key] = features.get(key, 0.0) + float(value)
    return features


def lexical_shape_features(row: dict[str, Any]) -> dict[str, float]:
    features = lexical_features(row)
    for key, value in shape_ngram_features(row).items():
        features[key] = features.get(key, 0.0) + value
    return features


def merge_builders(*builders: Callable[[dict[str, Any]], dict[str, float]]) -> Callable[[dict[str, Any]], dict[str, float]]:
    def merged(row: dict[str, Any]) -> dict[str, float]:
        features: dict[str, float] = {}
        for builder in builders:
            for key, value in builder(row).items():
                features[key] = features.get(key, 0.0) + float(value)
        return features
    return merged


def _concept_fields_for_lane(lane: str) -> tuple[str, ...]:
    if lane == "all":
        return tuple(field for fields in CONCEPT_SEQUENCE_FIELDS.values() for field in fields)
    if lane not in CONCEPT_SEQUENCE_FIELDS:
        raise ValueError(f"Unknown concept lane: {lane}")
    return CONCEPT_SEQUENCE_FIELDS[lane]


def concept_sequence_features(row: dict[str, Any], *, lane: str) -> dict[str, float]:
    features: dict[str, float] = {}
    for field in _concept_fields_for_lane(lane):
        values = row.get(field)
        if not isinstance(values, list):
            continue
        normalized = [str(item or "").strip().lower() for item in values if str(item or "").strip()]
        for item in normalized:
            features[f"concept::seq::{field}::{item}"] = features.get(f"concept::seq::{field}::{item}", 0.0) + 1.0
        for order in (2, 3):
            for idx in range(0, max(0, len(normalized) - order + 1)):
                key = f"concept_ng::{field}::{order}::" + "_".join(normalized[idx : idx + order])
                features[key] = features.get(key, 0.0) + 1.0
    return features


def semantic_markov_only_features(row: dict[str, Any], markov_features: dict[str, float]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in markov_features.items()
        if key.startswith(SEMANTIC_MARKOV_PREFIXES)
    }


def make_method_builders(
    train_rows: list[dict[str, Any]],
) -> tuple[dict[str, Callable[[dict[str, Any]], dict[str, float]]], dict[tuple[str, int], Any]]:
    markov_models = fit_surface_markov_models(train_rows)

    def markov_builder(row: dict[str, Any]) -> dict[str, float]:
        return surface_markov_features(row, markov_models)

    def semantic_markov_builder(row: dict[str, Any]) -> dict[str, float]:
        return semantic_markov_only_features(row, markov_builder(row))

    builders: dict[str, Callable[[dict[str, Any]], dict[str, float]]] = {
        "lexical_style": lexical_features,
        "wordnet_only": wordnet_features,
        "markov_surface": markov_builder,
        "semantic_markov_only": semantic_markov_builder,
        "wordnet_concepts_only": lambda row: concept_sequence_features(row, lane="wordnet"),
        "wordnet_sumo_concepts_only": lambda row: concept_sequence_features(row, lane="wordnet_sumo"),
        "sumo_concepts_only": lambda row: concept_sequence_features(row, lane="sumo"),
        "all_concepts_only": lambda row: concept_sequence_features(row, lane="all"),
        "shape_ngrams": shape_ngram_features,
        "lexical_plus_markov": merge_builders(lexical_features, markov_builder),
        "lexical_semantic_markov": merge_builders(lexical_features, semantic_markov_builder),
        "wordnet_plus_markov": merge_builders(wordnet_features, markov_builder),
        "wordnet_semantic_markov": merge_builders(wordnet_features, semantic_markov_builder),
        "shape_ngrams_plus_markov": merge_builders(shape_ngram_features, markov_builder),
        "wordnet_plus_lexical": merge_builders(wordnet_features, lexical_features),
        "lexical_shape": lexical_shape_features,
        "lexical_shape_plus_markov": merge_builders(lexical_shape_features, markov_builder),
        "wordnet_lexical_markov": merge_builders(wordnet_features, lexical_features, markov_builder),
        "wordnet_lexical_semantic_markov": merge_builders(wordnet_features, lexical_features, semantic_markov_builder),
        "wordnet_lexical_shape_markov": merge_builders(wordnet_features, lexical_shape_features, markov_builder),
    }
    return builders, markov_models


def methods_require_wordnet(methods: str) -> bool:
    """Return whether the requested method subset needs expensive WordNet enrichment."""
    if not methods:
        return True
    requested = {part.strip() for part in methods.split(",") if part.strip()}
    return any(
        "wordnet" in method
        or "semantic_markov" in method
        or method in {"sumo_concepts_only", "all_concepts_only"}
        for method in requested
    )


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(INT_TO_LABEL[int(row["ai_generated_label"])] for row in rows))


def normalized_hash(text: str) -> str:
    normalized = " ".join(str(text or "").lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def leakage_audit(train_rows: list[dict[str, Any]], named_splits: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    train_hashes = defaultdict(list)
    for row in train_rows:
        train_hashes[str(row.get("text_hash") or normalized_hash(str(row.get("text") or "")))].append(row.get("doc_id"))
    report: dict[str, Any] = {}
    for name, rows in named_splits.items():
        split_hashes = defaultdict(list)
        for row in rows:
            split_hashes[str(row.get("text_hash") or normalized_hash(str(row.get("text") or "")))].append(row.get("doc_id"))
        overlap = sorted(set(train_hashes) & set(split_hashes))
        report[name] = {
            "row_count": len(rows),
            "unique_hashes": len(split_hashes),
            "duplicate_hash_groups_within_split": sum(1 for ids in split_hashes.values() if len(ids) > 1),
            "train_overlap_hash_groups": len(overlap),
            "train_overlap_examples": [
                {"hash": h, "train_doc_ids": train_hashes[h][:3], "split_doc_ids": split_hashes[h][:3]} for h in overlap[:10]
            ],
        }
    return report


def source_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def group(field: str) -> dict[str, Any]:
        buckets: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            buckets[str(row.get(field, "unknown"))][INT_TO_LABEL[int(row["ai_generated_label"])] ] += 1
        return {key: {"row_count": sum(counter.values()), "label_counts": dict(counter)} for key, counter in buckets.items()}
    return {"dataset": group("dataset"), "domain": group("domain"), "doc_type": group("doc_type"), "label_counts": label_counts(rows)}


def attach_context(rows: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row, pred in zip(rows, predictions, strict=True):
        item = dict(pred)
        item["dataset"] = row.get("dataset", "unknown")
        item["domain"] = row.get("domain", "unknown")
        item["doc_type"] = row.get("doc_type", "unknown")
        item["corpus_role"] = row.get("corpus_role", "unknown")
        item["source_type"] = row.get("source_type", "unknown")
        for key in (
            "real_world_fixture",
            "real_world_fixture_name",
            "chunking_strategy",
            "chunk_min_words",
            "chunk_max_words",
            "allow_isolated_short_chunks",
            "chunk_type",
            "chunk_section",
            "chunk_index",
            "chunk_total",
            "chunk_word_count",
        ):
            if key in row:
                item[key] = row.get(key)
        item["word_count"] = row.get("word_count")
        out.append(item)
    return out


def grouped_metrics(predictions: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"row_count": 0, "correct_count": 0, "confusion": Counter(), "label_counts": Counter(), "predicted_counts": Counter()})
    for pred in predictions:
        bucket = groups[str(pred.get(field, "unknown"))]
        bucket["row_count"] += 1
        bucket["correct_count"] += int(bool(pred.get("correct")))
        bucket["confusion"][f"{pred.get('actual')}->{pred.get('predicted')}"] += 1
        bucket["label_counts"][str(pred.get("actual"))] += 1
        bucket["predicted_counts"][str(pred.get("predicted"))] += 1
    return {
        key: {
            "row_count": val["row_count"],
            "correct_count": val["correct_count"],
            "accuracy": val["correct_count"] / max(1, val["row_count"]),
            "confusion": dict(val["confusion"]),
            "label_counts": dict(val["label_counts"]),
            "predicted_counts": dict(val["predicted_counts"]),
        }
        for key, val in groups.items()
    }


def threshold_metrics(predictions: list[dict[str, Any]], thresholds: list[float]) -> list[dict[str, Any]]:
    out = []
    for threshold in thresholds:
        confusion = Counter()
        correct = 0
        for pred in predictions:
            actual = str(pred["actual"])
            predicted = "ai_generated" if float(pred["ai_generated_probability"]) >= threshold else "human_written"
            confusion[f"{actual}->{predicted}"] += 1
            correct += int(actual == predicted)
        fp = confusion.get("human_written->ai_generated", 0)
        tn = confusion.get("human_written->human_written", 0)
        tp = confusion.get("ai_generated->ai_generated", 0)
        fn = confusion.get("ai_generated->human_written", 0)
        out.append({
            "threshold": threshold,
            "accuracy": correct / max(1, len(predictions)),
            "confusion": dict(confusion),
            "human_false_positive_rate": fp / max(1, fp + tn),
            "ai_recall": tp / max(1, tp + fn),
        })
    return out


def strip_predictions(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key != "predictions"}


def top_coefficients(model: dict[str, Any], limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    pairs = sorted(zip(model.get("vocab", []), model.get("weights", []), strict=True), key=lambda x: x[1])
    return {
        "toward_human_written": [{"feature": str(k), "weight": round(float(v), 6)} for k, v in pairs[:limit]],
        "toward_ai_generated": [{"feature": str(k), "weight": round(float(v), 6)} for k, v in reversed(pairs[-limit:])],
    }


def normalize_model_for_edge(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the Python LR model JSON shape to the TypeScript edge artifact shape."""
    return {
        "bias": payload.get("bias"),
        "vocab": payload.get("vocab"),
        "means": payload.get("means"),
        "stds": payload.get("stds"),
        "weights": payload.get("weights"),
        "minFrequency": payload.get("min_frequency"),
        "maxFeatures": payload.get("max_features"),
        "epochs": payload.get("epochs"),
        "lr": payload.get("lr"),
        "l2": payload.get("l2"),
    }


def build_edge_candidate_artifact(report: dict[str, Any], method: str, *, threshold: float = 0.6) -> dict[str, Any]:
    """Build a compact handoff artifact for the edge cheap-detector exporter."""
    methods = {str(item.get("method")): item for item in report.get("results", [])}
    if method not in methods:
        raise ValueError(f"method {method!r} not found in report results")
    result = methods[method]
    model_path = Path(str(result.get("files", {}).get("model") or ""))
    if not model_path.exists():
        raise FileNotFoundError(f"model file for {method!r} not found: {model_path}")
    model = normalize_model_for_edge(json.loads(model_path.read_text(encoding="utf-8")))
    supervised = result.get("splits", {}).get("supervised_test", {})
    selected_threshold = None
    for item in supervised.get("threshold_sweep", []):
        if abs(float(item.get("threshold", -1.0)) - threshold) < 1e-9:
            selected_threshold = item
            break
    feature_families = ["lexical_style", "shape_ngrams", "surface_markov"] if method == "lexical_shape_plus_markov" else [method]
    return {
        "modelVersion": "corporate-lexical-shape-markov-authorship-v2-candidate",
        "primaryMethod": method,
        "primaryModel": model,
        "decisionPolicy": {
            "threshold": threshold,
            "selectedThresholdMetrics": selected_threshold,
            "labelAtOrAboveThreshold": "ai_generated",
            "labelBelowThreshold": "human_written",
            "falsePositivePolicy": "favor threshold 0.6+ to reduce false AI accusations",
        },
        "featureFamilies": feature_families,
        "featureSource": {
            "modelDirectory": str(Path(str(report.get("output_dir", model_path.parent))).resolve()),
            "modelFile": model_path.name,
            "comparisonFile": "method_comparison.json",
        },
        "evaluation": {
            "supervisedTest": {
                "accuracy": supervised.get("accuracy"),
                "correctCount": supervised.get("correct_count"),
                "rowCount": supervised.get("row_count"),
                "confusion": supervised.get("confusion"),
                "thresholdSweep": supervised.get("threshold_sweep"),
                "sourceAware": supervised.get("source_aware"),
            },
            "calibrationHc3Wiki": result.get("splits", {}).get("calibration_hc3_wiki"),
            "calibrationHc3Qa": result.get("splits", {}).get("calibration_hc3_qa"),
        },
        "metadata": {
            "schema": "corporate.edge_candidate_detector.v1",
            "sourceReportSchema": report.get("schema"),
            "trainingSettings": report.get("settings"),
            "rows": report.get("rows"),
            "leakageAudit": report.get("leakage_audit"),
            "markovModelSummary": report.get("markov_model_summary"),
        },
    }


def evaluate_method(
    name: str,
    builder: Callable[[dict[str, Any]], dict[str, float]],
    train_rows: list[dict[str, Any]],
    eval_splits: dict[str, list[dict[str, Any]]],
    *,
    extra_splits: dict[str, list[dict[str, Any]] | None] = None,
    output_dir: Path,
    min_frequency: int,
    max_features: int,
    epochs: int,
) -> dict[str, Any]:
    print(f"=== {name} ===", flush=True)
    train_features = [builder(row) for row in train_rows]
    labels = [int(row["ai_generated_label"]) for row in train_rows]
    model = train_lr(train_features, labels, min_frequency=min_frequency, max_features=max_features, epochs=epochs, lr=0.1, l2=0.02, sparse=True)
    full_eval_splits = dict(eval_splits)
    if extra_splits:
        for split_name, rows in extra_splits.items():
            if rows is not None:
                full_eval_splits[split_name] = rows
    result: dict[str, Any] = {
        "method": name,
        "vocab_size": len(model.get("vocab", [])),
        "min_frequency": min_frequency,
        "max_features": max_features,
        "epochs": epochs,
        "top_coefficients": top_coefficients(model, limit=25),
        "splits": {},
        "files": {},
    }
    write_json(output_dir / f"{name}_model.json", model)
    result["files"]["model"] = str(output_dir / f"{name}_model.json")
    for split_name, rows in full_eval_splits.items():
        features = [builder(row) for row in rows]
        metrics = evaluate(rows, features, model)
        metrics["predictions"] = attach_context(rows, metrics["predictions"])
        pred_path = output_dir / f"{name}_predictions_{split_name}.jsonl"
        write_jsonl(pred_path, metrics["predictions"])
        result["files"][f"predictions_{split_name}"] = str(pred_path)
        split_report = strip_predictions(metrics)
        split_report["threshold_sweep"] = threshold_metrics(metrics["predictions"], [0.5, 0.6, 0.7, 0.8, 0.9])
        split_report["source_aware"] = {
            "dataset": grouped_metrics(metrics["predictions"], "dataset"),
            "domain": grouped_metrics(metrics["predictions"], "domain"),
            "doc_type": grouped_metrics(metrics["predictions"], "doc_type"),
        }
        result["splits"][split_name] = split_report
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    train_rows_raw = coerce_rows(args.train, "supervised_train")
    test_rows_raw = coerce_rows(args.test, "supervised_test")
    wiki_rows_raw = coerce_rows(args.calibration_hc3_wiki, "calibration_hc3_wiki")
    qa_rows_raw = coerce_rows(args.calibration_hc3_qa, "calibration_hc3_qa")
    real_world_rows_raw: list[dict[str, Any]] = []
    for fixture_path in args.real_world_calibration:
        real_world_rows_raw.extend(
            build_real_world_calibration_rows(
                fixture_path,
                chunking_strategy=args.real_world_chunking_strategy,
                min_chunk_words=args.real_world_min_chunk_words,
                max_chunk_words=args.real_world_max_chunk_words,
                allow_isolated_short_chunks=args.real_world_allow_isolated_short_chunks,
            )
        )

    real_world_methods = {
        method.strip() for method in str(args.real_world_methods).split(",") if method.strip()
    } or {"lexical_shape_plus_markov", "wordnet_lexical_shape_markov"}

    if args.limit_per_split:
        def cap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                by_label[int(row["ai_generated_label"])].append(row)
            selected = []
            per_label = max(1, args.limit_per_split // 2)
            for label_rows in by_label.values():
                selected.extend(label_rows[:per_label])
            return selected
        train_rows_raw = cap(train_rows_raw)
        test_rows_raw = cap(test_rows_raw)
        wiki_rows_raw = cap(wiki_rows_raw)
        qa_rows_raw = cap(qa_rows_raw)

    all_raw_for_wordnet = train_rows_raw + test_rows_raw + wiki_rows_raw + qa_rows_raw + real_world_rows_raw
    if methods_require_wordnet(args.methods):
        all_wordnet = build_wordnet_rows(all_raw_for_wordnet)
    else:
        all_wordnet = all_raw_for_wordnet
    n_train = len(train_rows_raw)
    n_test = len(test_rows_raw)
    n_wiki = len(wiki_rows_raw)
    train_rows = all_wordnet[:n_train]
    test_rows = all_wordnet[n_train : n_train + n_test]
    wiki_rows = all_wordnet[n_train + n_test : n_train + n_test + n_wiki]
    qa_rows = all_wordnet[n_train + n_test + n_wiki : n_train + n_test + n_wiki + len(qa_rows_raw)]
    real_world_rows = all_wordnet[n_train + n_test + n_wiki + len(qa_rows_raw) :] if real_world_rows_raw else []
    if not methods_require_wordnet(args.methods) and real_world_rows_raw:
        real_world_rows = build_wordnet_rows(real_world_rows) if real_world_rows else real_world_rows

    builders, markov_models = make_method_builders(train_rows)
    markov_summary = surface_markov_model_summary(markov_models, limit=12)
    if args.methods:
        wanted = set(args.methods.split(","))
        builders = {key: val for key, val in builders.items() if key in wanted}

    eval_splits = {
        "supervised_test": test_rows,
        "calibration_hc3_wiki": wiki_rows,
        "calibration_hc3_qa": qa_rows,
    }
    results = []
    for name, builder in builders.items():
        method_real_world_split = None
        if real_world_rows_raw and name in real_world_methods:
            method_real_world_split = real_world_rows if "wordnet" in name else real_world_rows_raw
        method = evaluate_method(
            name,
            builder,
            train_rows,
            eval_splits,
            extra_splits={"real_world_calibration": method_real_world_split} if method_real_world_split else None,
            output_dir=output_dir,
            min_frequency=args.min_frequency,
            max_features=args.max_features,
            epochs=args.epochs,
        )
        results.append(method)
        summary = build_report(
            args,
            output_dir,
            train_rows_raw,
            test_rows_raw,
            wiki_rows_raw,
            qa_rows_raw,
            results,
            markov_summary,
            real_world_rows=real_world_rows_raw,
            real_world_summary=summarize_real_world_rows(real_world_rows_raw),
        )
        write_json(output_dir / "method_comparison.json", summary)
        print(json.dumps({
            "method": name,
            "supervised_test_accuracy": method["splits"]["supervised_test"]["accuracy"],
            "supervised_test_confusion": method["splits"]["supervised_test"]["confusion"],
            "vocab_size": method["vocab_size"],
        }, indent=2), flush=True)
    summary = build_report(
        args,
        output_dir,
        train_rows_raw,
        test_rows_raw,
        wiki_rows_raw,
        qa_rows_raw,
        results,
        markov_summary,
        real_world_rows=real_world_rows_raw,
        real_world_summary=summarize_real_world_rows(real_world_rows_raw),
    )
    write_json(output_dir / "method_comparison.json", summary)
    if args.export_edge_candidate:
        artifact = build_edge_candidate_artifact(summary, args.export_edge_candidate, threshold=args.edge_threshold)
        export_path = output_dir / f"{args.export_edge_candidate}_edge_candidate.json"
        write_json(export_path, artifact)
        summary["edge_candidate_export"] = str(export_path)
        write_json(output_dir / "method_comparison.json", summary)
    return summary


def build_report(
    args: argparse.Namespace,
    output_dir: Path,
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    wiki_rows: list[dict[str, Any]],
    qa_rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    markov_summary: dict[str, Any],
    *,
    real_world_rows: list[dict[str, Any]] | None = None,
    real_world_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda item: float(item["splits"]["supervised_test"].get("accuracy", 0.0)), reverse=True)
    safe_real_world_rows = real_world_rows if real_world_rows is not None else []
    safe_real_world_summary = real_world_summary if real_world_summary is not None else summarize_real_world_rows(safe_real_world_rows)
    return {
        "schema": "corporate.authorship_corpus_v2_markov_everything.v1",
        "output_dir": str(output_dir),
        "settings": {
            "train": str(args.train),
            "test": str(args.test),
            "calibration_hc3_wiki": str(args.calibration_hc3_wiki),
            "calibration_hc3_qa": str(args.calibration_hc3_qa),
            "min_frequency": args.min_frequency,
            "max_features": args.max_features,
            "epochs": args.epochs,
            "limit_per_split": args.limit_per_split,
            "real_world_calibration": [str(path) for path in args.real_world_calibration],
            "real_world_chunking_strategy": args.real_world_chunking_strategy,
            "real_world_min_chunk_words": args.real_world_min_chunk_words,
            "real_world_max_chunk_words": args.real_world_max_chunk_words,
            "real_world_allow_isolated_short_chunks": args.real_world_allow_isolated_short_chunks,
            "real_world_methods": str(args.real_world_methods),
        },
        "rows": {
            "train": len(train_rows),
            "supervised_test": len(test_rows),
            "calibration_hc3_wiki": len(wiki_rows),
            "calibration_hc3_qa": len(qa_rows),
            "real_world_calibration": len(safe_real_world_rows),
        },
        "source_summary": {
            "train": source_summary(train_rows),
            "supervised_test": source_summary(test_rows),
            "calibration_hc3_wiki": source_summary(wiki_rows),
            "calibration_hc3_qa": source_summary(qa_rows),
            "real_world_calibration": source_summary(safe_real_world_rows),
        },
        "leakage_audit": leakage_audit(train_rows, {"supervised_test": test_rows, "calibration_hc3_wiki": wiki_rows, "calibration_hc3_qa": qa_rows}),
        "real_world_calibration_summary": safe_real_world_summary,
        "markov_model_summary": markov_summary,
        "results": ordered,
        "best_supervised_test": ordered[0] if ordered else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lexical/WordNet/Markov everything ablations on authorship_corpus_v2.")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--test", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--calibration-hc3-wiki", type=Path, default=DEFAULT_WIKI)
    parser.add_argument("--calibration-hc3-qa", type=Path, default=DEFAULT_QA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-frequency", type=int, default=8)
    parser.add_argument("--max-features", type=int, default=12000)
    parser.add_argument("--epochs", type=int, default=220)
    parser.add_argument("--limit-per-split", type=int, default=0, help="Optional smoke cap per split, balanced by label.")
    parser.add_argument("--methods", default="", help="Comma-separated method subset.")
    parser.add_argument("--real-world-calibration", type=Path, nargs="*", default=[], help="Optional real-world calibration JSONL fixtures.")
    parser.add_argument(
        "--real-world-chunking-strategy",
        default="article_prose",
        choices=("article_prose", "single_chunk"),
        help="Chunking strategy for real-world fixtures.",
    )
    parser.add_argument("--real-world-min-chunk-words", type=int, default=REAL_WORLD_DEFAULT_MIN_CHUNK_WORDS)
    parser.add_argument("--real-world-max-chunk-words", type=int, default=REAL_WORLD_DEFAULT_MAX_CHUNK_WORDS)
    parser.add_argument(
        "--real-world-allow-isolated-short-chunks",
        action="store_true",
        help="Allow scoring isolated short chunks in real-world chunking.",
    )
    parser.add_argument(
        "--real-world-methods",
        default="lexical_shape_plus_markov,wordnet_lexical_shape_markov",
        help="Methods to run on real-world fixtures.",
    )
    parser.add_argument("--export-edge-candidate", default="", help="Write an edge-candidate detector artifact for this method.")
    parser.add_argument("--edge-threshold", type=float, default=0.6, help="Decision threshold to record in the edge-candidate artifact.")
    return parser.parse_args()


def main() -> int:
    report = run(parse_args())
    compact = {
        "output": report["output_dir"],
        "best": {
            "method": report["best_supervised_test"]["method"],
            "accuracy": report["best_supervised_test"]["splits"]["supervised_test"]["accuracy"],
            "confusion": report["best_supervised_test"]["splits"]["supervised_test"]["confusion"],
        } if report.get("best_supervised_test") else None,
        "leakage_audit": report["leakage_audit"],
    }
    print(json.dumps(compact, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
