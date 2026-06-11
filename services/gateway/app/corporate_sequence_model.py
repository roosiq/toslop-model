from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

# Legacy heuristic labels are intentionally retained only for back-compat.
# SUMO-derived propositions and evidence are the authoritative source for production scoring.
MARKET_CHANGE = ("rapidly evolving", "changing landscape", "fast-changing", "complexity", "market shift")
ORG_NEED = ("organizations need", "businesses need", "teams need", "must adapt", "need agile")
AI_SOLUTION = ("ai-powered", "ai platform", "artificial intelligence", "intelligent platform", "agentic")
ABSTRACT_BENEFIT = ("transformation", "innovation", "efficiency", "growth", "business value", "better outcomes")
GENERIC_AUDIENCE = ("stakeholder", "stakeholders", "teams", "organizations", "customers")
SPECIFIC_AUDIENCE = ("enterprise", "enterprise customer", "enterprise customers", "customer", "customers", "team", "teams", "employees")
METRIC = ("%", "percent", "percentile", "reduced", "increased", "improved", "decreased", "reduction", "increase")
BASELINE = ("baseline", "versus", "compared with", "compared to")
TIMEFRAME = ("q1", "q2", "q3", "q4", "month", "quarter", "year", "pilot", "cycle")
WORKFLOW = ("workflow", "process", "review time", "onboarding")
MEASURABLE_CONTEXT = ("pilot", "test", "experiment", "baseline", "baseline.")
EVIDENCE_SOURCE = ("study", "analysis", "report", "internal memo", "source", "dashboard", "system", "dataset")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _text(value: Any) -> str:
    return str(value or "").strip()


def _to_lower(text: str) -> str:
    return text.lower()


def _safe_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[2].joinpath(*parts)


def _load_json(resource_path: Path) -> list[dict[str, Any]]:
    if not resource_path.exists():
        return []
    return json.loads(resource_path.read_text())


def _score(value: float) -> int:
    return max(0, min(100, round(value)))


def _contains_phrase(text: str, term: str) -> bool:
    lowered = _to_lower(text)
    if not term:
        return False
    escaped = re.escape(term.lower())
    if re.search(r"\w", term[0]) and re.search(r"\w", term[-1]):
        pattern = rf"\b{escaped}\b"
    else:
        pattern = rf"(?<!\w){escaped}(?!\w)"
    return bool(re.search(pattern, lowered))


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = _to_lower(text)
    return any(_contains_phrase(lowered, term) for term in terms)


def _append_unique(sequence: list[str], item: str) -> None:
    if item not in sequence:
        sequence.append(item)


def _contains_subsequence(sequence: list[str], pattern: list[str]) -> bool:
    if not pattern:
        return False
    if len(pattern) == 1:
        return pattern[0] in sequence
    for index in range(len(sequence) - len(pattern) + 1):
        if sequence[index : index + len(pattern)] == pattern:
            return True
    return False


def _pattern_is_missing_based(pattern: list[str], form: dict[str, Any]) -> bool:
    missing = form.get("missing_bindings", [])
    required = [item.split(":", 1)[1] for item in pattern if str(item).startswith("missing:")]
    if not required:
        return False
    return all(item in missing for item in required)


def _label_for_node(value: Any) -> str:
    if not isinstance(value, dict):
        return _text(value)
    for key in ("label", "term", "id"):
        candidate = _text(value.get(key))
        if candidate:
            return candidate
    return ""


def _format_sumo_proposition(item: dict[str, Any]) -> str:
    subject = _label_for_node(item.get("subject"))
    predicate = _label_for_node(item.get("predicate"))
    obj = _label_for_node(item.get("object"))
    if subject and predicate and obj:
        return f"{subject} {predicate} {obj}"
    if predicate and obj:
        return f"{predicate} {obj}"
    if subject and predicate:
        return f"{subject} {predicate}"
    return predicate or subject or obj


def _proposition_sources(item: dict[str, Any]) -> list[str]:
    evidence_paths = item.get("evidence_paths")
    if not isinstance(evidence_paths, list):
        return []
    sources: list[str] = []
    for path in evidence_paths:
        if not isinstance(path, dict):
            continue
        source = path.get("source")
        if isinstance(source, dict):
            source = source.get("kind") or source.get("id")
        if source:
            sources.append(_text(source))
    return _unique(sources)


def extract_sumo_form(sumo_result: dict[str, Any]) -> dict[str, Any]:
    # SUMO-grounded extractor; these fields are treated as authoritative for sequence features.
    concept_hits = [item for item in (sumo_result.get("all_concepts") or sumo_result.get("concepts") or []) if isinstance(item, dict)]
    propositions = [item for item in (sumo_result.get("propositions") or []) if isinstance(item, dict)]

    concept_sequence: list[str] = []
    logic_sequence: list[str] = []
    proposition_sequence: list[str] = []
    grounding_offsets: list[str] = []
    missing_bindings: list[str] = []

    for concept in concept_hits:
        label = _label_for_node(concept)
        if label:
            concept_sequence.append(label)

    for proposition in propositions:
        logic = _label_for_node(proposition.get("predicate"))
        if logic:
            logic_sequence.append(logic)
        proposition_text = _format_sumo_proposition(proposition)
        if proposition_text:
            proposition_sequence.append(proposition_text)
        sources = _proposition_sources(proposition)
        if sources:
            grounding_offsets.extend(sources)
        else:
            missing_bindings.append("sumo_grounding")

    if not propositions:
        missing_bindings.append("sumo_proposition")
    if not concept_hits:
        missing_bindings.append("sumo_concept")

    return {
        "concept_sequence": _unique(concept_sequence),
        "proposition_sequence": _unique(proposition_sequence),
        "logic_sequence": _unique(logic_sequence),
        "missing_bindings": _unique(missing_bindings),
        "grounding_offsets": _unique(grounding_offsets),
    }


def _extract_semantic_form_legacy(text: str) -> dict[str, Any]:
    # DEPRECATED: throwaway ad-hoc extractor retained only for compatibility.
    lowered = _to_lower(text)
    concept_sequence: list[str] = []
    proposition_sequence: list[str] = []
    logic_sequence: list[str] = []
    missing_bindings: list[str] = []
    grounding_offsets: list[str] = []

    has_market_change = _has_any(lowered, MARKET_CHANGE)
    has_org_need = _has_any(lowered, ORG_NEED)
    has_ai_solution = _has_any(lowered, AI_SOLUTION)
    has_abstract_benefit = _has_any(lowered, ABSTRACT_BENEFIT)
    has_generic_audience = _has_any(lowered, GENERIC_AUDIENCE)
    has_specific_audience = _has_any(lowered, SPECIFIC_AUDIENCE)
    has_metric = _has_any(lowered, METRIC)
    has_baseline = _has_any(lowered, BASELINE)
    has_timeframe = _has_any(lowered, TIMEFRAME)
    has_workflow = _has_any(lowered, WORKFLOW)
    has_measurable = _has_any(lowered, MEASURABLE_CONTEXT) or has_metric
    has_evidence_source = _has_any(lowered, EVIDENCE_SOURCE)

    if has_market_change:
        _append_unique(concept_sequence, "MarketChange")
        _append_unique(logic_sequence, "ChangingLandscapeClaim")
    if has_org_need:
        _append_unique(concept_sequence, "Organization")
        _append_unique(logic_sequence, "OrganizationNeedClaim")
        proposition_sequence.append("Organization needs ScalableSolution")
    if has_ai_solution:
        _append_unique(concept_sequence, "AISolution")
        _append_unique(logic_sequence, "AISolutionClaim")
    if has_abstract_benefit:
        _append_unique(concept_sequence, "AbstractBusinessOutcome")
        _append_unique(logic_sequence, "AbstractBenefitClaim")
    if has_generic_audience:
        _append_unique(concept_sequence, "GenericAudience")
        if has_abstract_benefit:
            _append_unique(logic_sequence, "GenericAudienceBenefitClaim")
    if has_ai_solution and has_abstract_benefit:
        proposition_sequence.append("TechnologySystem enables AbstractBusinessOutcome")
        proposition_sequence.append("AbstractBusinessOutcome benefits GenericAudience")
    if has_workflow:
        _append_unique(concept_sequence, "SpecificWorkflow")
    if has_abstract_benefit and has_ai_solution and has_generic_audience:
        proposition_sequence.append("AbstractBusinessOutcome benefits GenericAudience")
    if has_measurable:
        _append_unique(logic_sequence, "MeasurableClaim")
    if has_metric and has_timeframe and has_workflow:
        _append_unique(logic_sequence, "MeasuredPerformanceClaim")
    if has_metric:
        grounding_offsets.append("metric")
    else:
        missing_bindings.append("metric")
    if has_baseline:
        grounding_offsets.append("baseline")
    else:
        missing_bindings.append("baseline")
    if has_timeframe:
        grounding_offsets.append("timeframe")
    else:
        missing_bindings.append("timeframe")
    if has_workflow:
        grounding_offsets.append("specific_workflow")
    else:
        missing_bindings.append("specific_workflow")
    if has_specific_audience:
        grounding_offsets.append("specific_audience")
    else:
        missing_bindings.append("specific_audience")
    if has_evidence_source:
        grounding_offsets.append("evidence_source")
    else:
        missing_bindings.append("evidence_source")
    if not has_specific_audience:
        missing_bindings.append("audience_boundary")

    proposition_sequence = [item for index, item in enumerate(proposition_sequence) if item not in proposition_sequence[:index]]
    concept_sequence = [item for index, item in enumerate(concept_sequence) if item not in concept_sequence[:index]]
    logic_sequence = [item for index, item in enumerate(logic_sequence) if item not in logic_sequence[:index]]

    return {
        "concept_sequence": concept_sequence,
        "proposition_sequence": proposition_sequence,
        "logic_sequence": logic_sequence,
        "missing_bindings": missing_bindings,
        "grounding_offsets": grounding_offsets,
    }


def extract_semantic_form(text: str) -> dict[str, Any]:
    # DEPRECATED: throwaway legacy extractor; SUMO-backed forms from map_sumo_concepts should be used when available.
    return _extract_semantic_form_legacy(text)


def _load_motif_library() -> list[dict[str, Any]]:
    # DEPRECATED fallback; these motifs were built for the legacy ad-hoc extractor and are retained for compatibility.
    path = _safe_path("evals", "corporate_sequence_model", "motifs.json")
    loaded = _load_json(path)
    if not loaded:
        return [
            {
                "id": "changing_landscape_need_solution_abstract_benefit",
                "type": "logic_sequence",
                "label": "Changing landscape → business need → AI solution → abstract benefit",
                "pattern": [
                    "ChangingLandscapeClaim",
                    "OrganizationNeedClaim",
                    "AISolutionClaim",
                    "AbstractBenefitClaim",
                ],
                "base_score": 86,
                "severity": "high",
            }
        ]
    return loaded


def _extract_features(form: dict[str, Any]) -> list[str]:
    concept_sequence = [str(item) for item in form.get("concept_sequence", [])]
    logic_sequence = [str(item) for item in form.get("logic_sequence", [])]
    propositions = [str(item) for item in form.get("proposition_sequence", [])]
    features: list[str] = []
    for concept in concept_sequence:
        features.append(f"concept:{concept}")
    for length in (2, 3):
        for start in range(len(concept_sequence) - length + 1):
            segment = concept_sequence[start : start + length]
            features.append("concept_set:" + "|".join(segment))
    features.append("logic_seq:" + "|".join(logic_sequence))
    for logic in logic_sequence:
        features.append(f"logic:{logic}")
    for proposition in propositions:
        features.append(f"proposition:{proposition}")
    for missing in [str(item) for item in form.get("missing_bindings", [])]:
        features.append(f"missing:{missing}")
    for grounding in [str(item) for item in form.get("grounding_offsets", [])]:
        features.append(f"grounded:{grounding}")
    return features


CURATED_MOTIFS = _load_motif_library()
_DEFAULT_SEQUENCE_MODEL: dict[str, Any] | None = None


def match_semantic_motifs(form: dict[str, Any]) -> list[dict[str, Any]]:
    logic_sequence = [str(item) for item in form.get("logic_sequence", [])]
    proposition_sequence = [str(item) for item in form.get("proposition_sequence", [])]
    concept_sequence = [str(item) for item in form.get("concept_sequence", [])]
    missing_bindings = [str(item) for item in form.get("missing_bindings", [])]
    matches: list[dict[str, Any]] = []

    for motif in CURATED_MOTIFS:
        motif_type = str(motif.get("type", ""))
        pattern = [str(item) for item in motif.get("pattern", [])]
        matched = False

        if motif_type == "logic_sequence":
            matched = _contains_subsequence(logic_sequence, pattern)
        elif motif_type == "proposition":
            matched = _contains_subsequence(proposition_sequence, pattern)
        elif motif_type in {"concept_sequence", "concept_set"}:
            if motif_type == "concept_set":
                matched = _contains_subsequence(concept_sequence, pattern)
            else:
                matched = _contains_subsequence(concept_sequence, pattern)
        elif motif_type == "missing_binding":
            matched = _pattern_is_missing_based(pattern, form)

        if not matched:
            continue

        motif_missing = [item.split(":", 1)[1] for item in pattern if item.startswith("missing:")]
        if not motif_missing:
            motif_missing = [item for item in missing_bindings if item in {"metric", "specific_workflow", "specific_audience", "baseline", "timeframe", "evidence_source", "audience_boundary"}]
        matches.append(
            {
                "id": str(motif.get("id")),
                "type": motif_type,
                "label": str(motif.get("label", motif.get("id", "Untitled motif"))),
                "severity": str(motif.get("severity", "medium")),
                "score": int(motif.get("base_score", 0)),
                "missingBindings": motif_missing[:6],
            }
        )

    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches


def train_sequence_lift_model(corpus: list[dict[str, Any]]) -> dict[str, Any]:
    if not corpus:
        return {
            "documentCount": 0,
            "aiDocumentCount": 0,
            "humanGroundedDocumentCount": 0,
            "featureCounts": {
                "ai": {},
                "human": {},
            },
            "featureLift": {},
        }

    ai_feature_counts: Counter[str] = Counter()
    human_feature_counts: Counter[str] = Counter()
    ai_documents = 0
    human_documents = 0
    grounded_human_documents = 0

    for doc in corpus:
        source_type = str(doc.get("source_type", ""))
        quality_label = str(doc.get("quality_label", ""))
        text = str(doc.get("text", ""))
        if not text:
            continue

        is_ai = source_type == "ai_generated"
        is_human = source_type == "human_written"
        if not is_ai and not is_human:
            continue

        form = _sequence_form_for_doc(doc)
        features = set(_extract_features(form))
        if is_ai:
            ai_documents += 1
            ai_feature_counts.update(features)
        else:
            human_documents += 1
            if quality_label != "low":
                grounded_human_documents += 1
            human_feature_counts.update(features)

    all_features = set(ai_feature_counts.keys()) | set(human_feature_counts.keys())
    denom_ai = ai_documents + 2
    denom_human = human_documents + 2
    feature_lift: dict[str, float] = {}
    for feature in all_features:
        ai_prob = (ai_feature_counts[feature] + 1) / denom_ai
        human_prob = (human_feature_counts[feature] + 1) / denom_human if human_documents else 1 / denom_ai
        feature_lift[feature] = ai_prob / human_prob if human_prob else 1.0

    return {
        "documentCount": ai_documents + human_documents,
        "aiDocumentCount": ai_documents,
        "humanGroundedDocumentCount": grounded_human_documents,
        "featureCounts": {
            "ai": dict(ai_feature_counts),
            "human": dict(human_feature_counts),
        },
        "featureLift": feature_lift,
    }


def _sequence_form_for_doc(doc: dict[str, Any]) -> dict[str, Any]:
    # SUMO-backed forms are preferred over legacy text heuristics.
    for key in ("sumo_map", "sumo_output", "sumo_payload"):
        payload = doc.get(key)
        if isinstance(payload, dict) and (payload.get("all_concepts") or payload.get("concepts") or payload.get("propositions")):
            return extract_sumo_form(payload)

    if doc.get("sumo_concepts") or doc.get("sumo_propositions"):
        payload = {"all_concepts": doc.get("sumo_concepts"), "propositions": doc.get("sumo_propositions")}
        return extract_sumo_form(payload)

    if isinstance(doc.get("sumo_sequence_form"), dict):
        return doc["sumo_sequence_form"]

    text = str(doc.get("text", ""))
    return extract_semantic_form(text)


def _default_sequence_model() -> dict[str, Any]:
    global _DEFAULT_SEQUENCE_MODEL
    if _DEFAULT_SEQUENCE_MODEL is None:
        path = _safe_path("evals", "corporate_sequence_model", "corpus.json")
        corpus = _load_json(path)
        _DEFAULT_SEQUENCE_MODEL = train_sequence_lift_model(corpus)
    return _DEFAULT_SEQUENCE_MODEL


def score_with_lift_model(form: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    if not model:
        model = {"featureLift": {}}

    features = _extract_features(form)
    feature_lift = model.get("featureLift") or {}
    score = 50.0
    top_positive: list[dict[str, Any]] = []

    for feature in sorted(set(features)):
        lift = float(feature_lift.get(feature, 1.0))
        if lift > 1.0:
            contribution = min(28, round((lift - 1) * 16))
            score += contribution
            top_positive.append({"feature": feature, "lift": round(lift, 3), "contribution": contribution})
        elif lift < 1.0:
            score -= min(18, round((1 - lift) * 16))

    if grounding := [item for item in form.get("grounding_offsets", []) if item]:
        score -= len(grounding) * 4

    likelihood = _score(score)
    if likelihood >= 80:
        confidence = "high"
    elif likelihood >= 55:
        confidence = "medium"
    else:
        confidence = "low"

    top_positive.sort(key=lambda item: item["contribution"], reverse=True)
    return {
        "aiSemanticLikelihood": likelihood,
        "semanticSequenceConfidence": confidence,
        "topPositiveFeatures": top_positive[:10],
        "groundingOffsets": grounding,
    }


def _build_sequence_summary(sequence: dict[str, Any], motifs: list[dict[str, Any]], likelihood: int) -> str:
    if motifs:
        top = motifs[0]
        if likelihood >= 70:
            return f"High AI-style semantic consistency via '{top['label']}'."
        if likelihood >= 45:
            return f"Moderate AI-style patterns, top hit '{top['label']}'."
        return f"AI-style signal present in '{top['label']}', but strong grounding exists."
    logic_count = len([item for item in sequence.get("logic_sequence", []) if item])
    if logic_count >= 4:
        return "Detected multiple abstract reasoning steps with limited explicit grounding."
    return "No strong AI-style semantic sequence motifs were detected."


def score_semantic_sequence(text: str, *, sumo_map: dict[str, Any] | None = None) -> dict[str, Any]:
    # Prefer SUMO results when available; fallback keeps existing behavior for compatibility.
    form = extract_sumo_form(sumo_map) if isinstance(sumo_map, dict) else extract_semantic_form(text)
    model = _default_sequence_model()
    score = score_with_lift_model(form, model)
    motifs = match_semantic_motifs(form)

    return {
        "aiSemanticLikelihood": score["aiSemanticLikelihood"],
        "semanticSequenceConfidence": score["semanticSequenceConfidence"],
        "matchedSemanticPatterns": motifs,
        "missingBindings": form.get("missing_bindings", []),
        "groundingOffsets": score["groundingOffsets"],
        "topPositiveFeatures": score["topPositiveFeatures"],
        "summary": _build_sequence_summary(form, motifs, score["aiSemanticLikelihood"]),
    }
