from __future__ import annotations

import json
import os
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
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "lexical_shape_plus_markov_model.json"
DEFAULT_EDGE_ARTIFACT_PATH = DEFAULT_MODEL_DIR / "lexical_shape_plus_markov_edge_candidate.json"
DEFAULT_MARKOV_PATH = DEFAULT_MODEL_DIR / "surface_markov_models.json"
DEFAULT_TRAIN_PATH = EVAL_DIR / "authorship_corpus_v2" / "supervised_train_mix.jsonl"


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
        self.model_id = str(self.edge_artifact.get("modelVersion") or model_path.stem)
        self.method = str(self.edge_artifact.get("primaryMethod") or "lexical_shape_plus_markov")
        policy = self.edge_artifact.get("decisionPolicy") if isinstance(self.edge_artifact.get("decisionPolicy"), dict) else {}
        self.threshold = float(policy.get("threshold", 0.6))
        self._markov_models = None

    def _needs_markov(self) -> bool:
        return any(str(feature).startswith(("markov::", "seqng::", "semantic::")) for feature in self.model.get("vocab", []))

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
                features.update(surface_markov_features(row, markov_models))
            else:
                warnings.append("surface_markov_features_unavailable")
        return features, warnings

    def score(self, text: str) -> dict[str, Any]:
        features, warnings = self.features_for_text(text)
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
        likelihood = max(0, min(100, round(probability * 100)))
        label = _label(probability, self.threshold)
        contributions.sort(key=lambda item: abs(float(item["contribution"])), reverse=True)
        return {
            "available": True,
            "model_id": self.model_id,
            "method": self.method,
            "probability": round(probability, 6),
            "likelihood": likelihood,
            "label": label,
            "threshold": self.threshold,
            "confidence": _confidence(probability, self.threshold),
            "top_features": contributions[:12],
            "feature_count": active_count,
            "warnings": warnings,
        }


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
            "probability": None,
            "likelihood": None,
            "label": "unavailable",
            "threshold": detector.threshold,
            "confidence": "unavailable",
            "top_features": [],
            "feature_count": 0,
            "warnings": [f"corporate_authorship_model_failed:{type(exc).__name__}"],
        }
