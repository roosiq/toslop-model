from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.corporate_ai_authorship_feature_spike import (
    char_shape_sequence_features,
    posish_sequence_features,
    sigmoid,
    style_stats_features,
    text_lexical_features,
    token_type_sequence_features,
)
from app.corporate_markov_features import (
    deserialize_surface_markov_models,
    fit_surface_markov_models,
    surface_markov_features,
)

GATEWAY_ROOT = Path(__file__).resolve().parents[1]
SERVICES_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = SERVICES_ROOT / "evals" / "corporate_sequence_model"
DEFAULT_MODEL_DIR = GATEWAY_ROOT / "model_artifacts" / "corporate_authorship"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "lexical_shape_plus_core_markov_xgboost_model.json"
DEFAULT_EDGE_ARTIFACT_PATH = DEFAULT_MODEL_DIR / "lexical_shape_plus_core_markov_xgboost_edge_candidate.json"
DEFAULT_MARKOV_PATH = DEFAULT_MODEL_DIR / "surface_markov_models.json"
DEFAULT_TRAIN_PATH = EVAL_DIR / "authorship_corpus_v2" / "supervised_train_mix.jsonl"
DEFAULT_MIXED_MIN_WORDS = 80
DEFAULT_MIXED_TARGET_WORDS = 180
DEFAULT_MIXED_MAX_WORDS = 320
DEFAULT_MIXED_MAX_CHUNKS = 48
MIN_MIXED_TEXT_WORDS = 40

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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _merge_features(*maps: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for mapping in maps:
        for key, value in mapping.items():
            out[key] = out.get(key, 0.0) + float(value)
    return out


def _lexical_style_features(row: dict[str, Any]) -> dict[str, float]:
    return _merge_features(text_lexical_features(row), style_stats_features(row))


def _shape_features(row: dict[str, Any]) -> dict[str, float]:
    return _merge_features(
        token_type_sequence_features(row),
        posish_sequence_features(row),
        char_shape_sequence_features(row),
    )


def _feature_family(feature: str) -> str:
    if feature.startswith(("lex::", "style::")):
        return "lexical_style"
    if feature.startswith(("toktype::", "posish::", "shape::")):
        return "shape_ngrams"
    if feature.startswith(("markov::", "seqng::", "semantic::")):
        return "surface_markov"
    return "other"


def _confidence(probability: float, threshold: float) -> str:
    distance = abs(probability - threshold)
    if distance >= 0.25:
        return "high"
    if distance >= 0.12:
        return "medium"
    return "low"


def _label(probability: float, threshold: float) -> str:
    return "ai_generated" if probability >= threshold else "human_written"


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


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
    if len(words) > 14 or body[-1:] in ".!?;:":
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
    return lowercase_starters <= max(1, len(alpha_words) // 2)


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_sections_with_offsets(text: str) -> list[dict[str, Any]]:
    normalized = re.sub(r"\r\n?", "\n", str(text or "")).strip()
    if not normalized:
        return []

    lines = list(re.finditer(r".*(?:\n|$)", normalized))
    sections: list[dict[str, Any]] = []
    current_heading = "front matter"
    current_start: int | None = None
    current_end: int | None = None

    def flush() -> None:
        nonlocal current_start, current_end
        if current_start is None or current_end is None:
            current_start = None
            current_end = None
            return
        start, end = _trimmed_span(normalized, current_start, current_end)
        if start < end:
            sections.append(
                {
                    "heading": current_heading,
                    "text": normalized[start:end],
                    "char_start": start,
                    "char_end": end,
                }
            )
        current_start = None
        current_end = None

    for match in lines:
        line = match.group(0)
        if not line:
            continue
        line_body = line.rstrip("\n")
        if _is_probable_heading(line_body):
            flush()
            current_heading = _normalize_heading(line_body)
            continue
        if line_body.strip():
            current_start = match.start() if current_start is None else current_start
            current_end = match.end()

    flush()
    return sections or [{"heading": "document", "text": normalized, "char_start": 0, "char_end": len(normalized)}]


def _paragraphs_with_offsets(section: dict[str, Any], *, first_paragraph_index: int) -> list[dict[str, Any]]:
    section_text = str(section.get("text") or "")
    section_start = int(section.get("char_start") or 0)
    paragraphs: list[dict[str, Any]] = []
    paragraph_index = first_paragraph_index
    for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n+|\Z)", section_text):
        local_start, local_end = _trimmed_span(section_text, match.start(), match.end())
        paragraph_text = section_text[local_start:local_end]
        if not paragraph_text:
            continue
        paragraphs.append(
            {
                "text": paragraph_text,
                "word_count": _word_count(paragraph_text),
                "char_start": section_start + local_start,
                "char_end": section_start + local_end,
                "paragraph_index": paragraph_index,
            }
        )
        paragraph_index += 1
    return paragraphs


def _chunk_long_paragraph(paragraph: dict[str, Any], *, max_words: int) -> list[dict[str, Any]]:
    words = list(re.finditer(r"\S+", str(paragraph.get("text") or "")))
    if not words:
        return []
    paragraph_text = str(paragraph["text"])
    paragraph_start = int(paragraph["char_start"])
    chunks: list[dict[str, Any]] = []
    for start_index in range(0, len(words), max_words):
        end_index = min(start_index + max_words, len(words))
        local_start = words[start_index].start()
        local_end = words[end_index - 1].end()
        text = paragraph_text[local_start:local_end].strip()
        chunks.append(
            {
                "text": text,
                "word_count": _word_count(text),
                "char_start": paragraph_start + local_start,
                "char_end": paragraph_start + local_end,
                "paragraph_start": int(paragraph["paragraph_index"]),
                "paragraph_end": int(paragraph["paragraph_index"]),
                "chunk_type": "long_paragraph_split",
            }
        )
    return chunks


def chunk_text_for_mixed_authorship(
    text: str,
    *,
    min_words: int = DEFAULT_MIXED_MIN_WORDS,
    target_words: int = DEFAULT_MIXED_TARGET_WORDS,
    max_words: int = DEFAULT_MIXED_MAX_WORDS,
    max_chunks: int = DEFAULT_MIXED_MAX_CHUNKS,
) -> list[dict[str, Any]]:
    total_words = _word_count(text)
    if total_words < MIN_MIXED_TEXT_WORDS:
        return []
    if total_words and max_chunks:
        max_words = min(900, max(max_words, math.ceil(total_words / max_chunks)))
        target_words = min(max_words, max(target_words, math.ceil(max_words * 0.58)))

    chunks: list[dict[str, Any]] = []
    paragraph_counter = 1
    for section in _split_sections_with_offsets(text):
        heading = str(section.get("heading") or "document")
        paragraphs = _paragraphs_with_offsets(section, first_paragraph_index=paragraph_counter)
        paragraph_counter += len(paragraphs)
        if not paragraphs:
            continue

        buffered: list[dict[str, Any]] = []
        buffered_words = 0

        def emit_buffered() -> None:
            nonlocal buffered, buffered_words
            if not buffered:
                return
            body = "\n\n".join(str(item["text"]) for item in buffered).strip()
            chunks.append(
                {
                    "text": body,
                    "word_count": _word_count(body),
                    "char_start": int(buffered[0]["char_start"]),
                    "char_end": int(buffered[-1]["char_end"]),
                    "section_heading": heading,
                    "paragraph_start": int(buffered[0]["paragraph_index"]),
                    "paragraph_end": int(buffered[-1]["paragraph_index"]),
                    "chunk_type": "paragraph_merge" if len(buffered) > 1 else "paragraph",
                }
            )
            buffered = []
            buffered_words = 0

        for paragraph in paragraphs:
            paragraph_words = int(paragraph["word_count"])
            if paragraph_words >= max_words:
                emit_buffered()
                for chunk in _chunk_long_paragraph(paragraph, max_words=max_words):
                    chunks.append({**chunk, "section_heading": heading})
                continue

            if buffered and buffered_words + paragraph_words > max_words:
                emit_buffered()
            buffered.append(paragraph)
            buffered_words += paragraph_words
            if buffered_words >= target_words:
                emit_buffered()

        emit_buffered()

    if not chunks:
        return []

    return [
        {
            **chunk,
            "index": index + 1,
            "chunk_total": len(chunks),
            "chunk_word_count": int(chunk["word_count"]),
            "score_reliability": "high" if int(chunk["word_count"]) >= min_words else "medium" if int(chunk["word_count"]) >= 45 else "low",
            "offset_basis": "normalized_text",
        }
        for index, chunk in enumerate(chunks[:max_chunks])
    ]


def _metadata_path_for(model_path: Path) -> Path:
    return model_path.with_name(f"{model_path.stem}_metadata.json")


def _parse_xgboost_base_score(value: Any) -> float:
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
    parsed = float(value)
    clipped = min(max(parsed, 1e-9), 1.0 - 1e-9)
    return math.log(clipped / (1.0 - clipped))


class XGBoostJsonScorer:
    def __init__(self, model: dict[str, Any], metadata: dict[str, Any]) -> None:
        learner = model.get("learner") if isinstance(model.get("learner"), dict) else {}
        model_params = learner.get("learner_model_param") if isinstance(learner.get("learner_model_param"), dict) else {}
        gradient_booster = learner.get("gradient_booster") if isinstance(learner.get("gradient_booster"), dict) else {}
        booster_model = gradient_booster.get("model") if isinstance(gradient_booster.get("model"), dict) else {}
        self.trees = list(booster_model.get("trees") or [])
        self.vocab = [str(item) for item in metadata.get("vocab", [])]
        self.feature_index = {feature: index for index, feature in enumerate(self.vocab)}
        self.base_margin = _parse_xgboost_base_score(model_params.get("base_score", 0.5))
        importance_rows = metadata.get("feature_importance", {}).get("by_gain", [])
        self.feature_gain = {
            str(item.get("feature")): float(item.get("gain") or 0.0)
            for item in importance_rows
            if isinstance(item, dict) and item.get("feature")
        }

    def _tree_margin(self, tree: dict[str, Any], active_features: dict[int, float]) -> float:
        left_children = tree["left_children"]
        right_children = tree["right_children"]
        default_left = tree["default_left"]
        split_indices = tree["split_indices"]
        split_conditions = tree["split_conditions"]
        base_weights = tree["base_weights"]
        node = 0
        while True:
            left = int(left_children[node])
            right = int(right_children[node])
            if left < 0 and right < 0:
                return float(base_weights[node])
            feature_index = int(split_indices[node])
            value = active_features.get(feature_index)
            if value is None:
                node = left if int(default_left[node]) else right
            else:
                node = left if value < float(split_conditions[node]) else right

    def predict(self, features: dict[str, float]) -> float:
        active_features = {
            self.feature_index[key]: float(value)
            for key, value in features.items()
            if value and key in self.feature_index
        }
        margin = self.base_margin
        for tree in self.trees:
            margin += self._tree_margin(tree, active_features)
        return sigmoid(margin)

    def active_feature_count(self, features: dict[str, float]) -> int:
        return sum(1 for key, value in features.items() if value and key in self.feature_index)

    def top_features(self, features: dict[str, float], *, limit: int = 12) -> list[dict[str, Any]]:
        rows = []
        for feature, value in features.items():
            if not value or feature not in self.feature_index:
                continue
            gain = self.feature_gain.get(feature, 0.0)
            if gain <= 0:
                continue
            rows.append(
                {
                    "feature": feature,
                    "family": _feature_family(feature),
                    "value": round(float(value), 6),
                    "importance_gain": round(gain, 6),
                    "direction": "model_signal",
                }
            )
        rows.sort(key=lambda item: float(item["importance_gain"]), reverse=True)
        return rows[:limit]


class CorporateAuthorshipDetector:
    def __init__(
        self,
        *,
        model_path: Path = DEFAULT_MODEL_PATH,
        edge_artifact_path: Path = DEFAULT_EDGE_ARTIFACT_PATH,
        markov_path: Path = DEFAULT_MARKOV_PATH,
        train_path: Path = DEFAULT_TRAIN_PATH,
    ) -> None:
        self.model_path = model_path
        self.edge_artifact_path = edge_artifact_path
        self.markov_path = markov_path
        self.train_path = train_path
        self.model = _read_json(model_path)
        self.edge_artifact = _read_json(edge_artifact_path) if edge_artifact_path.exists() else {}
        metadata_path = _metadata_path_for(model_path)
        self.model_metadata = _read_json(metadata_path) if metadata_path.exists() else {}
        self.trainer = str(
            self.edge_artifact.get("trainer")
            or self.model_metadata.get("trainer")
            or ("lr" if "weights" in self.model else "xgboost")
        )
        self.model_id = str(self.edge_artifact.get("modelVersion") or model_path.stem)
        self.method = str(self.edge_artifact.get("primaryMethod") or self.model_metadata.get("method") or "lexical_shape_plus_markov")
        policy = self.edge_artifact.get("decisionPolicy") if isinstance(self.edge_artifact.get("decisionPolicy"), dict) else {}
        self.threshold = float(policy.get("threshold", 0.6))
        self._markov_models = None
        self._xgboost_scorer = XGBoostJsonScorer(self.model, self.model_metadata) if self.trainer == "xgboost" else None

    def _needs_markov(self) -> bool:
        return any(str(feature).startswith(("markov::", "seqng::", "semantic::")) for feature in self._vocab())

    def _vocab(self) -> list[str]:
        if self.trainer == "xgboost":
            return [str(feature) for feature in self.model_metadata.get("vocab", [])]
        return [str(feature) for feature in self.model.get("vocab", [])]

    def _markov_include_views(self) -> set[str] | None:
        feature_source = self.edge_artifact.get("featureSource") if isinstance(self.edge_artifact.get("featureSource"), dict) else {}
        configured = feature_source.get("markovViews")
        if isinstance(configured, list) and configured:
            return {str(item) for item in configured}
        if "core_markov" in self.method:
            return {"shape", "posish", "true_pos"}
        return None

    def _load_markov_models(self):
        if self._markov_models is not None:
            return self._markov_models
        if not self._needs_markov():
            self._markov_models = {}
            return self._markov_models
        if self.markov_path.exists():
            self._markov_models = deserialize_surface_markov_models(_read_json(self.markov_path))
            return self._markov_models
        if not self.train_path.exists():
            self._markov_models = {}
            return self._markov_models
        self._markov_models = fit_surface_markov_models(_read_jsonl(self.train_path))
        return self._markov_models

    def warm(self) -> None:
        self._load_markov_models()

    def features_for_text(self, text: str) -> tuple[dict[str, float], list[str]]:
        row = {"text": text}
        warnings: list[str] = []
        features = _merge_features(_lexical_style_features(row), _shape_features(row))
        if self._needs_markov():
            markov_models = self._load_markov_models()
            if markov_models:
                features.update(surface_markov_features(row, markov_models, include_views=self._markov_include_views()))
            else:
                warnings.append("surface_markov_features_unavailable")
        return features, warnings

    def _score_text(self, text: str, *, top_feature_limit: int = 12) -> dict[str, Any]:
        features, warnings = self.features_for_text(text)
        if self.trainer == "xgboost":
            if self._xgboost_scorer is None:
                raise RuntimeError("xgboost_json_scorer_unavailable")
            probability = self._xgboost_scorer.predict(features)
            active_count = self._xgboost_scorer.active_feature_count(features)
            contributions = self._xgboost_scorer.top_features(features, limit=top_feature_limit)
        else:
            vocab = [str(item) for item in self.model["vocab"]]
            weights = [float(item) for item in self.model["weights"]]
            means = [float(item) for item in self.model["means"]]
            stds = [float(item) or 1.0 for item in self.model["stds"]]
            logit = float(self.model["bias"])
            contributions: list[dict[str, Any]] = []
            active_count = 0

            for feature, weight, mean, std in zip(vocab, weights, means, stds, strict=True):
                raw = float(features.get(feature, 0.0))
                if raw:
                    active_count += 1
                standardized = (raw - mean) / std
                contribution = standardized * weight
                logit += contribution
                if raw:
                    contributions.append(
                        {
                            "feature": feature,
                            "family": _feature_family(feature),
                            "value": round(raw, 6),
                            "weight": round(weight, 6),
                            "contribution": round(contribution, 6),
                            "direction": "ai_generated" if contribution >= 0 else "human_written",
                        }
                    )
            probability = sigmoid(logit)
            contributions.sort(key=lambda item: abs(float(item["contribution"])), reverse=True)
        likelihood = max(0, min(100, round(probability * 100)))
        label = _label(probability, self.threshold)
        return {
            "available": True,
            "model_id": self.model_id,
            "method": self.method,
            "trainer": self.trainer,
            "probability": round(probability, 6),
            "likelihood": likelihood,
            "label": label,
            "threshold": self.threshold,
            "confidence": _confidence(probability, self.threshold),
            "top_features": contributions[:top_feature_limit],
            "feature_count": active_count,
            "warnings": warnings,
        }

    def _score_chunks(self, text: str) -> tuple[list[dict[str, Any]], list[str]]:
        chunks = chunk_text_for_mixed_authorship(text)
        warnings: list[str] = []
        scored_chunks: list[dict[str, Any]] = []
        for chunk in chunks:
            score = self._score_text(str(chunk["text"]), top_feature_limit=4)
            warnings.extend(str(item) for item in score.get("warnings", []))
            scored_chunks.append(
                {
                    "index": chunk["index"],
                    "chunkTotal": chunk["chunk_total"],
                    "chunkType": chunk["chunk_type"],
                    "sectionHeading": chunk.get("section_heading"),
                    "paragraphStart": chunk["paragraph_start"],
                    "paragraphEnd": chunk["paragraph_end"],
                    "charStart": chunk["char_start"],
                    "charEnd": chunk["char_end"],
                    "offsetBasis": chunk["offset_basis"],
                    "wordCount": chunk["chunk_word_count"],
                    "scoreReliability": chunk["score_reliability"],
                    "probability": score["probability"],
                    "likelihood": score["likelihood"],
                    "label": score["label"],
                    "confidence": score["confidence"],
                    "topFeatures": score.get("top_features", []),
                    "textPreview": re.sub(r"\s+", " ", str(chunk["text"])).strip()[:220],
                }
            )
        return scored_chunks, sorted(set(warnings))

    def _mixed_authorship_summary(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        if not chunks:
            return {
                "available": False,
                "classification": "not_enough_text",
                "summary": "Text was too short for reliable mixed-authorship chunking.",
                "chunkCount": 0,
            }

        total_words = sum(int(chunk.get("wordCount") or 0) for chunk in chunks)
        ai_words = sum(int(chunk.get("wordCount") or 0) for chunk in chunks if chunk.get("label") == "ai_generated")
        human_words = max(0, total_words - ai_words)
        ai_chunk_count = sum(1 for chunk in chunks if chunk.get("label") == "ai_generated")
        human_chunk_count = len(chunks) - ai_chunk_count
        likelihoods = [int(chunk.get("likelihood") or 0) for chunk in chunks]
        likelihood_min = min(likelihoods)
        likelihood_max = max(likelihoods)
        contrast = likelihood_max - likelihood_min
        transition_count = sum(
            1
            for previous, current in zip(chunks, chunks[1:], strict=False)
            if previous.get("label") != current.get("label")
        )
        ai_word_share = ai_words / max(1, total_words)
        has_both = ai_chunk_count > 0 and human_chunk_count > 0
        if has_both and contrast >= 25 and 0.15 <= ai_word_share <= 0.85:
            classification = "mixed_ai_and_human"
            summary = "Chunk scores show both AI-like and human-like sections."
        elif ai_word_share >= 0.75:
            classification = "mostly_ai_like"
            summary = "Most scored words fall in AI-like chunks."
        elif ai_word_share <= 0.25:
            classification = "mostly_human_like"
            summary = "Most scored words fall in human-like chunks."
        else:
            classification = "mixed_or_uncertain"
            summary = "Chunk scores vary, but the contrast is not strong enough for a firm mixed label."

        ai_chunks = sorted(
            [chunk for chunk in chunks if chunk.get("label") == "ai_generated"],
            key=lambda chunk: int(chunk.get("likelihood") or 0),
            reverse=True,
        )
        human_chunks = sorted(
            [chunk for chunk in chunks if chunk.get("label") == "human_written"],
            key=lambda chunk: int(chunk.get("likelihood") or 0),
        )
        return {
            "available": True,
            "classification": classification,
            "summary": summary,
            "chunkCount": len(chunks),
            "aiChunkCount": ai_chunk_count,
            "humanChunkCount": human_chunk_count,
            "aiWordShare": round(ai_word_share, 4),
            "aiWordCount": ai_words,
            "humanWordCount": human_words,
            "likelihoodRange": {"min": likelihood_min, "max": likelihood_max, "contrast": contrast},
            "labelTransitionCount": transition_count,
            "strongAiChunks": ai_chunks[:3],
            "strongHumanChunks": human_chunks[:3],
            "chunking": {
                "strategy": "section_paragraph_window",
                "minWords": DEFAULT_MIXED_MIN_WORDS,
                "targetWords": DEFAULT_MIXED_TARGET_WORDS,
                "maxWords": DEFAULT_MIXED_MAX_WORDS,
                "maxChunks": DEFAULT_MIXED_MAX_CHUNKS,
                "offsetBasis": "normalized_text",
            },
        }

    def score(self, text: str) -> dict[str, Any]:
        result = self._score_text(text)
        chunks, chunk_warnings = self._score_chunks(text)
        result["authorship_chunks"] = chunks
        result["mixed_authorship"] = self._mixed_authorship_summary(chunks)
        result["warnings"] = sorted(set([*result.get("warnings", []), *chunk_warnings]))
        return result


@lru_cache(maxsize=1)
def get_corporate_authorship_detector() -> CorporateAuthorshipDetector | None:
    return get_corporate_authorship_detector_for_paths(
        os.getenv("CORPORATE_AUTHORSHIP_MODEL_PATH", str(DEFAULT_MODEL_PATH)),
        os.getenv("CORPORATE_AUTHORSHIP_EDGE_ARTIFACT_PATH", str(DEFAULT_EDGE_ARTIFACT_PATH)),
        os.getenv("CORPORATE_AUTHORSHIP_MARKOV_PATH", str(DEFAULT_MARKOV_PATH)),
        os.getenv("CORPORATE_AUTHORSHIP_TRAIN_PATH", str(DEFAULT_TRAIN_PATH)),
        os.getenv("CORPORATE_AUTHORSHIP_ENABLED", "true"),
    )


@lru_cache(maxsize=8)
def get_corporate_authorship_detector_for_paths(
    model_path: str,
    edge_artifact_path: str,
    markov_path: str,
    train_path: str,
    enabled: str = "true",
) -> CorporateAuthorshipDetector | None:
    if str(enabled).strip().lower() in {"0", "false", "no", "off"}:
        return None
    resolved_model_path = Path(model_path)
    if not resolved_model_path.exists():
        return None
    return CorporateAuthorshipDetector(
        model_path=resolved_model_path,
        edge_artifact_path=Path(edge_artifact_path),
        markov_path=Path(markov_path),
        train_path=Path(train_path),
    )


def get_corporate_authorship_detector_from_settings(settings: Any) -> CorporateAuthorshipDetector | None:
    return get_corporate_authorship_detector_for_paths(
        str(getattr(settings, "corporate_authorship_model_path", DEFAULT_MODEL_PATH)),
        str(getattr(settings, "corporate_authorship_edge_artifact_path", DEFAULT_EDGE_ARTIFACT_PATH)),
        str(getattr(settings, "corporate_authorship_markov_path", DEFAULT_MARKOV_PATH)),
        str(getattr(settings, "corporate_authorship_train_path", DEFAULT_TRAIN_PATH)),
        str(getattr(settings, "corporate_authorship_enabled", True)),
    )


def score_corporate_authorship(text: str, *, settings: Any | None = None) -> dict[str, Any]:
    detector = get_corporate_authorship_detector_from_settings(settings) if settings is not None else get_corporate_authorship_detector()
    if detector is None:
        return {
            "available": False,
            "model_id": None,
            "method": None,
            "trainer": None,
            "probability": None,
            "likelihood": None,
            "label": "unavailable",
            "threshold": None,
            "confidence": "unavailable",
            "top_features": [],
            "feature_count": 0,
            "warnings": ["corporate_authorship_model_unavailable"],
        }
    try:
        return detector.score(text)
    except Exception as exc:
        return {
            "available": False,
            "model_id": detector.model_id,
            "method": detector.method,
            "trainer": detector.trainer,
            "probability": None,
            "likelihood": None,
            "label": "unavailable",
            "threshold": detector.threshold,
            "confidence": "unavailable",
            "top_features": [],
            "feature_count": 0,
            "warnings": [f"corporate_authorship_model_failed:{type(exc).__name__}"],
        }
