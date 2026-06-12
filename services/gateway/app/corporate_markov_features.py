from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

try:
    from nltk import pos_tag as _nltk_pos_tag
except Exception:  # pragma: no cover - optional NLP dependency for an experimental feature.
    _nltk_pos_tag = None

LABELS = ("human_written", "ai_generated")

ABSTRACT_TERMS = {
    "system", "systems", "data", "infrastructure", "layer", "context", "ambiguity", "meaning",
    "agents", "governance", "compliance", "determinism", "deterministic", "semantic", "constraints",
    "validation", "inference", "integration", "payload", "guarantee", "framework", "architecture",
    "deployment", "enterprise", "model", "models", "value", "visibility", "quality", "risk", "scale",
    "strategy", "capability", "workflow", "experience", "solution", "outcome", "impact", "performance",
    "innovation", "efficiency", "productivity", "transformation", "optimization", "growth", "success",
}
PRODUCT_TERMS = {
    "api", "sdk", "mcp", "sdc", "sdcstudio", "adk", "cloudflare", "chroma", "sumo", "wordnet",
    "json", "sql", "python", "javascript", "typescript", "react", "docker", "kubernetes", "github",
}
STOP_TERMS = set(
    "the a an and or but if when while for from to in on with without into of at by is are was were be been being "
    "your our their its it this that these those every no not as via about than then so because through across "
    "under over you we they he she his her them us i me my mine ours yours according report reports said says say "
    .split()
)
WORDNET_SUMO_HINTS = {
    "students": "Human",
    "student": "Human",
    "people": "GroupOfPeople",
    "person": "Human",
    "human": "Human",
    "migration": "Immigrating",
    "immigration": "Immigrating",
    "immigrant": "Immigrating",
    "revenue": "CurrencyMeasure",
    "money": "CurrencyMeasure",
    "dollar": "CurrencyMeasure",
    "policy": "Plan",
    "plan": "Plan",
    "data": "FactualText",
    "evidence": "FactualText",
    "company": "Corporation",
    "corporation": "Corporation",
    "report": "Stating",
    "reported": "Stating",
}
MODALS = {"should", "need", "needs", "must", "can", "could", "will", "would", "may", "might"}
CLAIM_VERBS = {
    "enable", "enables", "ensure", "ensures", "transform", "transforms", "optimize", "optimizes",
    "unlock", "unlocks", "deliver", "delivers", "drive", "drives", "guarantee", "guarantees",
    "enforce", "enforces", "empower", "empowers", "streamline", "streamlines", "accelerate", "accelerates",
}


def tokenise_markov(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*|\d+(?:\.\d+)?(?:[%+])?|[$€£]|[.!?;:—-]", str(text or ""))


def coarse_state(token: str) -> str:
    low = token.lower()
    if re.fullmatch(r"[.!?;:—-]", token):
        return "PUNCT"
    if re.fullmatch(r"\d+(?:\.\d+)?(?:[%+])?", low) or low in {"$", "€", "£"}:
        return "NUM"
    if low in {"no", "not", "never", "without"}:
        return "NEG"
    if low in {"every", "all", "any", "always"}:
        return "UNIV"
    if low in MODALS:
        return "MODAL"
    if low in CLAIM_VERBS:
        return "CLAIM_VERB"
    if token[:1].isupper() and low not in STOP_TERMS:
        return "ENTITY"
    if low in PRODUCT_TERMS:
        return "PRODUCT"
    if low in ABSTRACT_TERMS or low.endswith(("tion", "ity", "ism", "ance", "ence", "ment", "ness", "ability", "ibility")):
        return "ABSTRACT"
    if low in STOP_TERMS:
        return "FUNC"
    return "CONTENT"


def shape_state(token: str) -> str:
    if re.fullmatch(r"[.!?;:—-]", token):
        return "PUNCT"
    if re.fullmatch(r"\d+(?:\.\d+)?(?:[%+])?", token):
        return "NUM"
    if token.isupper() and len(token) > 1:
        return "ALLCAPS"
    if token[:1].isupper():
        return "CAP"
    if token.lower() in STOP_TERMS:
        return "FUNC"
    if len(token) <= 3:
        return "SHORT"
    if len(token) >= 10:
        return "LONG"
    return "WORD"


def posish_state(token: str) -> str:
    low = token.lower()
    if re.fullmatch(r"[.!?]", token):
        return "SENT_END"
    if re.fullmatch(r"[;:—-]", token):
        return "CLAUSE_PUNCT"
    if re.fullmatch(r"\d+(?:\.\d+)?(?:[%+])?", low) or low in {"$", "€", "£"}:
        return "NUM"
    if low in {"no", "not", "never", "without"}:
        return "NEG"
    if low in MODALS:
        return "MODAL"
    if low in CLAIM_VERBS:
        return "CLAIM_VERB"
    if low in STOP_TERMS:
        return "FUNC"
    if token.isupper() and len(token) > 1:
        return "ACRONYM"
    if token[:1].isupper():
        return "TITLE"
    if low.endswith("ly"):
        return "ADVISH"
    if low.endswith(("ed", "ing", "ize", "izes", "ise", "ises")):
        return "VERBISH"
    if low.endswith(("tion", "ity", "ism", "ance", "ence", "ment", "ness", "ability", "ibility")):
        return "NOUN_ABSTRACT"
    if low.endswith(("ive", "ous", "al", "ic", "able", "ible", "less", "ful")):
        return "ADJISH"
    return "CONTENT"


def _true_pos_state(tag: str, token: str) -> str:
    if token == "." or token == "," or token in {"?", "!", ";", ":", "-", "—"}:
        return "PUNCT"
    if not tag:
        return "OTHER"
    tag = tag.upper()
    if tag.startswith("NN"):
        return "NOUN"
    if tag.startswith("VB"):
        return "VERB"
    if tag.startswith("JJ"):
        return "ADJ"
    if tag.startswith("RB"):
        return "ADV"
    if tag in {"PRP", "PRP$", "WP", "WP$"}:
        return "PRON"
    if tag in {"DT", "WDT"}:
        return "DET"
    if tag in {"IN"}:
        return "ADP"
    if tag in {"CC"}:
        return "CONJ"
    if tag in {"MD"}:
        return "MODAL"
    if tag in {"CD"}:
        return "NUM"
    if tag in {"UH"}:
        return "INTJ"
    if tag in {"TO", "RP", "POS"}:
        return "FUNC"
    return "OTHER"


def _fallback_true_pos_state(token: str) -> str:
    state = posish_state(token)
    if state in {"PUNCT", "NUM", "NEG", "UNIV", "MODAL", "CLAIM_VERB"}:
        return state
    if state == "ACRONYM":
        return "OTHER"
    if state == "TITLE":
        return "NOUN"
    if state == "ADVISH":
        return "ADV"
    if state == "VERBISH":
        return "VERB"
    if state == "NOUN_ABSTRACT":
        return "NOUN"
    if state == "ADJISH":
        return "ADJ"
    if state == "FUNC":
        return "DET"
    return "OTHER"


def true_pos_sequence(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    if _nltk_pos_tag is None:
        return [_fallback_true_pos_state(token) for token in tokens]
    try:
        tagged = _nltk_pos_tag(tokens)
    except LookupError:
        return [_fallback_true_pos_state(token) for token in tokens]
    except Exception:
        return [_fallback_true_pos_state(token) for token in tokens]
    states: list[str] = []
    for token, tag in tagged:
        if token:
            states.append(_true_pos_state(str(tag), str(token)))
        else:
            states.append(_fallback_true_pos_state(str(token)))
    return states


def semantic_pattern_sequence(text: str) -> list[str]:
    patterns: list[str] = []
    for token in tokenise_markov(text):
        low = token.lower()
        if re.fullmatch(r"\d+(?:\.\d+)?(?:[%+])?", low) or low in {"$", "€", "£"}:
            patterns.append("NUMERIC")
            continue
        if low in STOP_TERMS or len(low) <= 1:
            continue
        sumo = WORDNET_SUMO_HINTS.get(low)
        if sumo is not None:
            patterns.append(f"SUMO::{sumo}")
            continue
        if low.endswith(("tion", "ity", "ism", "ance", "ence", "ment", "ness", "ability", "ibility")):
            patterns.append("WORDNET_LEX::noun.attribute")
        elif low.endswith(("ed", "ing", "ize", "izes", "ise", "ises")):
            patterns.append("WORDNET_POS::verb")
        elif low.endswith(("ive", "ous", "al", "ic", "able", "ible", "less", "ful")):
            patterns.append("WORDNET_POS::adj")
        elif token[:1].isupper():
            patterns.append("WORDNET_ENTITY_CANDIDATE")
        else:
            patterns.append("WORDNET_CONTENT")
    return patterns or ["NO_SEMANTIC_PATTERN"]


def _as_sequence(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _valid_sequence_value(value: str) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False
    return normalized.lower() not in {
        "none",
        "null",
        "no_wordnet_match",
        "no_wordnet_relation",
        "no_sumo_mapping",
        "no_mapping",
        "unknown",
    }


def semantic_sequence_from_row(row: dict[str, Any]) -> list[str]:
    terms = _as_sequence(row.get("wordnet_sumo_term_sequence"))
    relations = _as_sequence(row.get("wordnet_sumo_relation_sequence"))
    lexnames = _as_sequence(row.get("wordnet_lexname_sequence"))
    poses = _as_sequence(row.get("wordnet_pos_sequence"))
    if not any((terms, relations, lexnames, poses)):
        return semantic_pattern_sequence(str(row.get("text") or ""))

    patterns: list[str] = []
    for term in terms:
        patterns.append(f"SUMO::{term}" if _valid_sequence_value(term) else "NO_SUMO_MAPPING")
    for relation in relations:
        if _valid_sequence_value(relation):
            patterns.append(f"SUMO_REL::{relation}")
    for lexname in lexnames:
        if _valid_sequence_value(lexname):
            patterns.append(f"WORDNET_LEX::{lexname}")
    for pos in poses:
        if _valid_sequence_value(pos):
            patterns.append(f"WORDNET_POS::{pos}")
    return patterns or ["NO_SEMANTIC_PATTERN"]


def semantic_features_from_sequence(sequence: list[str]) -> dict[str, float]:
    features: dict[str, float] = {}
    for pattern in sequence:
        if pattern == "NO_SEMANTIC_PATTERN":
            continue
        key = "semantic::" + pattern
        features[key] = features.get(key, 0.0) + 1.0
    features["semantic::pattern_count"] = float(sum(1 for pattern in sequence if pattern != "NO_SEMANTIC_PATTERN"))
    return features


def semantic_pattern_features(text: str) -> dict[str, float]:
    return semantic_features_from_sequence(semantic_pattern_sequence(text))


def sequence_ngram_features(
    prefix: str,
    states: list[str],
    *,
    orders: tuple[int, ...] = (2, 3),
    max_per_order: int = 64,
) -> dict[str, float]:
    features: dict[str, float] = {}
    for order in orders:
        counts: Counter[tuple[str, ...]] = Counter(
            tuple(states[idx : idx + order])
            for idx in range(0, max(0, len(states) - order + 1))
        )
        for ngram, count in counts.most_common(max_per_order):
            key = f"seqng::{prefix}::{order}::" + "_".join(ngram)
            features[key] = float(count)
    return features


def motif_sequence(states: list[str]) -> list[str]:
    motifs: list[str] = []
    for prev, nxt in zip(states, states[1:]):
        if prev == "NEG" and nxt in {"ABSTRACT", "CONTENT", "CLAIM_VERB"}:
            motifs.append(f"NEG_{nxt}")
        elif prev == "UNIV" and nxt in {"ABSTRACT", "CONTENT", "ENTITY", "PRODUCT"}:
            motifs.append(f"UNIV_{nxt}")
        elif prev == "MODAL" and nxt in {"CLAIM_VERB", "CONTENT", "ABSTRACT"}:
            motifs.append(f"MODAL_{nxt}")
        elif prev == "NUM" and nxt in {"ABSTRACT", "CONTENT"}:
            motifs.append(f"NUM_{nxt}")
        elif prev in {"ENTITY", "PRODUCT"} and nxt in {"ENTITY", "PRODUCT", "CONTENT"}:
            motifs.append(f"SPECIFIC_{prev}_{nxt}")
        elif prev == "ABSTRACT" and nxt in {"ABSTRACT", "CLAIM_VERB"}:
            motifs.append(f"ABSTRACT_{nxt}")
    return motifs or ["NO_MOTIF"]


def surface_sequences(source: str | dict[str, Any]) -> dict[str, list[str]]:
    text = str(source.get("text") or "") if isinstance(source, dict) else str(source or "")
    tokens = tokenise_markov(text)
    coarse = [coarse_state(token) for token in tokens]
    shape = [shape_state(token) for token in tokens]
    posish = [posish_state(token) for token in tokens]
    true_pos = true_pos_sequence(tokens)
    semantic = semantic_sequence_from_row(source) if isinstance(source, dict) else semantic_pattern_sequence(text)
    return {
        "shape": shape,
        "coarse": coarse,
        "posish": posish,
        "true_pos": true_pos,
        "motif": motif_sequence(coarse),
        "semantic": semantic,
    }


class MarkovPair:
    def __init__(self, order: int, alpha: float = 0.1) -> None:
        self.order = int(order)
        self.alpha = float(alpha)
        self.transition_counts: dict[str, Counter[tuple[str, ...]]] = {label: Counter() for label in LABELS}
        self.context_counts: dict[str, Counter[tuple[str, ...]]] = {label: Counter() for label in LABELS}
        self.vocab: set[str] = set()

    def fit_one(self, label: str, states: list[str]) -> None:
        if label not in LABELS or len(states) <= self.order:
            return
        self.vocab.update(states)
        for idx in range(self.order, len(states)):
            context = tuple(states[idx - self.order: idx])
            nxt = states[idx]
            self.transition_counts[label][context + (nxt,)] += 1
            self.context_counts[label][context] += 1

    def logprob(self, label: str, states: list[str]) -> tuple[float, int]:
        if label not in LABELS or len(states) <= self.order:
            return 0.0, 0
        vocab_size = max(1, len(self.vocab))
        total = 0.0
        count = 0
        for idx in range(self.order, len(states)):
            context = tuple(states[idx - self.order: idx])
            nxt = states[idx]
            transition = context + (nxt,)
            numerator = self.transition_counts[label][transition] + self.alpha
            denominator = self.context_counts[label][context] + self.alpha * vocab_size
            total += math.log(numerator / denominator)
            count += 1
        return total, count

    def feature_values(self, prefix: str, states: list[str]) -> dict[str, float]:
        ai_logprob, transitions = self.logprob("ai_generated", states)
        human_logprob, _ = self.logprob("human_written", states)
        base = f"markov::{prefix}::order{self.order}"
        if transitions <= 0:
            return {
                f"{base}::n": 0.0,
                f"{base}::llr_total": 0.0,
                f"{base}::llr_per_transition": 0.0,
                f"{base}::ai_cross_entropy": 0.0,
                f"{base}::human_cross_entropy": 0.0,
            }
        return {
            f"{base}::n": float(transitions),
            f"{base}::llr_total": ai_logprob - human_logprob,
            f"{base}::llr_per_transition": (ai_logprob - human_logprob) / transitions,
            f"{base}::ai_cross_entropy": -ai_logprob / transitions,
            f"{base}::human_cross_entropy": -human_logprob / transitions,
        }

    def top_transition_log_odds(self, limit: int = 20) -> list[dict[str, Any]]:
        transitions = set(self.transition_counts["ai_generated"]) | set(self.transition_counts["human_written"])
        vocab_size = max(1, len(self.vocab))
        scored: list[tuple[float, tuple[str, ...], int, int]] = []
        for transition in transitions:
            context = transition[:-1]
            ai_count = self.transition_counts["ai_generated"][transition]
            human_count = self.transition_counts["human_written"][transition]
            ai_denominator = self.context_counts["ai_generated"][context] + self.alpha * vocab_size
            human_denominator = self.context_counts["human_written"][context] + self.alpha * vocab_size
            ai_probability = (ai_count + self.alpha) / ai_denominator
            human_probability = (human_count + self.alpha) / human_denominator
            scored.append((math.log(ai_probability / human_probability), transition, ai_count, human_count))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "transition": " -> ".join(transition),
                "log_odds_ai_vs_human": score,
                "ai_count": ai_count,
                "human_count": human_count,
            }
            for score, transition, ai_count, human_count in scored[:limit]
        ]

    def to_dict(self) -> dict[str, Any]:
        def counter_rows(counter: Counter[tuple[str, ...]]) -> list[dict[str, Any]]:
            return [
                {"key": list(key), "count": count}
                for key, count in sorted(counter.items(), key=lambda item: item[0])
            ]

        return {
            "order": self.order,
            "alpha": self.alpha,
            "vocab": sorted(self.vocab),
            "transition_counts": {
                label: counter_rows(counter)
                for label, counter in self.transition_counts.items()
            },
            "context_counts": {
                label: counter_rows(counter)
                for label, counter in self.context_counts.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MarkovPair":
        model = cls(order=int(payload.get("order", 1)), alpha=float(payload.get("alpha", 0.1)))
        model.vocab = {str(item) for item in payload.get("vocab", [])}

        def rows_to_counter(rows: Any) -> Counter[tuple[str, ...]]:
            counter: Counter[tuple[str, ...]] = Counter()
            if not isinstance(rows, list):
                return counter
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = row.get("key")
                count = row.get("count")
                if not isinstance(key, list):
                    continue
                counter[tuple(str(item) for item in key)] = int(count or 0)
            return counter

        for label in LABELS:
            transition_payload = payload.get("transition_counts", {})
            context_payload = payload.get("context_counts", {})
            if isinstance(transition_payload, dict):
                model.transition_counts[label] = rows_to_counter(transition_payload.get(label))
            if isinstance(context_payload, dict):
                model.context_counts[label] = rows_to_counter(context_payload.get(label))
        return model


def fit_surface_markov_models(rows: list[dict[str, Any]], *, label_key: str = "source_type") -> dict[tuple[str, int], MarkovPair]:
    models = {
        (view, order): MarkovPair(order=order)
        for view in ("shape", "coarse", "posish", "motif", "semantic", "true_pos")
        for order in (1, 2)
    }
    for row in rows:
        label = str(row.get(label_key) or "")
        if label not in LABELS:
            value = row.get("ai_generated_label")
            if isinstance(value, bool):
                label = "ai_generated" if value else "human_written"
            elif value in (0, 1):
                label = "ai_generated" if int(value) else "human_written"
        if label not in LABELS:
            continue
        sequences = surface_sequences(row)
        for view, states in sequences.items():
            for order in (1, 2):
                models[(view, order)].fit_one(label, states)
    return models


def surface_markov_features(
    source: str | dict[str, Any],
    models: dict[tuple[str, int], MarkovPair],
    *,
    include_views: set[str] | None = None,
) -> dict[str, float]:
    sequences = surface_sequences(source)
    features: dict[str, float] = {}
    for (view, order), model in sorted(models.items()):
        if include_views is not None and view not in include_views:
            continue
        features.update(model.feature_values(view, sequences.get(view, [])))
    for view in ("coarse", "posish", "true_pos", "semantic"):
        if include_views is not None and view not in include_views:
            continue
        features.update(sequence_ngram_features(view, sequences.get(view, []), max_per_order=48))
    if include_views is None or "semantic" in include_views:
        features.update(semantic_features_from_sequence(sequences.get("semantic", [])))
    return features


def surface_markov_model_summary(models: dict[tuple[str, int], MarkovPair], *, limit: int = 15) -> dict[str, Any]:
    return {
        f"{view}_order{order}": {
            "vocab_size": len(model.vocab),
            "ai_context_count": len(model.context_counts["ai_generated"]),
            "human_context_count": len(model.context_counts["human_written"]),
            "top_ai_transitions": model.top_transition_log_odds(limit=limit),
        }
        for (view, order), model in sorted(models.items())
    }


def serialize_surface_markov_models(models: dict[tuple[str, int], MarkovPair]) -> dict[str, Any]:
    return {
        "schema": "corporate.surface_markov_models.v1",
        "models": {
            f"{view}_order{order}": {
                "view": view,
                **model.to_dict(),
            }
            for (view, order), model in sorted(models.items())
        },
    }


def deserialize_surface_markov_models(payload: dict[str, Any]) -> dict[tuple[str, int], MarkovPair]:
    out: dict[tuple[str, int], MarkovPair] = {}
    models = payload.get("models")
    if not isinstance(models, dict):
        return out
    for model_payload in models.values():
        if not isinstance(model_payload, dict):
            continue
        view = str(model_payload.get("view") or "")
        order = int(model_payload.get("order") or 0)
        if not view or order <= 0:
            continue
        out[(view, order)] = MarkovPair.from_dict(model_payload)
    return out
