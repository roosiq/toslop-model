from __future__ import annotations

import json
import math
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
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "lexical_shape_plus_core_markov_xgboost_model.json"
DEFAULT_EDGE_ARTIFACT_PATH = DEFAULT_MODEL_DIR / "lexical_shape_plus_core_markov_xgboost_edge_candidate.json"
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

    def score(self, text: str) -> dict[str, Any]:
        features, warnings = self.features_for_text(text)
        if self.trainer == "xgboost":
            if self._xgboost_scorer is None:
                raise RuntimeError("xgboost_json_scorer_unavailable")
            probability = self._xgboost_scorer.predict(features)
            active_count = self._xgboost_scorer.active_feature_count(features)
            contributions = self._xgboost_scorer.top_features(features)
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
