#!/usr/bin/env python3
"""Build deterministic public-safe conformance fixtures for ES-001."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "observatory" / "contracts"
FIXTURES = CONTRACTS / "fixtures"


def load_json(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def score_fixture(score: dict, index: int) -> dict:
    component_ids = score["required_components"]
    weight = 1.0 / len(component_ids)
    normalized = 52.0 + index
    current = normalized
    baseline = normalized - 10.0
    components = {
        component_id: {
            "raw_value": normalized,
            "normalized_value": normalized,
            "weight": weight,
            "unit": "contract_fixture_unit",
            "status": "available",
        }
        for component_id in component_ids
    }
    return {
        "schema_version": "observatory.score_output.v1",
        "release_id": "contract-fixtures-v1",
        "study_release_id": None,
        "score_id": score["id"],
        "score_name": score["name"],
        "entity": {
            "id": "aggregate",
            "type": "aggregate",
            "label": "All eligible observations",
            "version": "1.0.0",
        },
        "topic": None,
        "source_frame": {
            "id": "synthetic-contract-frame",
            "label": "Synthetic contract frame",
            "source_family_count": 2,
            "version": "1.0.0",
        },
        "period": {
            "id": "2026-Q2",
            "granularity": "quarter",
            "start": "2026-04-01",
            "end": "2026-06-30",
        },
        "evidence_class": "descriptive",
        "release_state": "experimental",
        "score": normalized,
        "confidence": {
            "value": 0.8,
            "method": "contract_fixture_calibration",
            "calibration_version": "1.0.0",
        },
        "uncertainty_interval": {
            "lower": normalized - 2.0,
            "upper": normalized + 2.0,
            "level": 0.95,
            "method": "cluster_bootstrap",
            "replicates": 1000,
            "cluster_unit": "synthetic_entity",
        },
        "sample": {
            "size": 240,
            "effective_size": 180.0,
            "unit": "eligible_documents",
        },
        "coverage": {
            "eligible_rate": 0.9,
            "matched_rate": 0.85,
            "entity_count": 24,
            "source_count": 2,
            "source_family_count": 2,
            "complete": True,
            "dimensions": {"fixture": True},
        },
        "baseline": {
            "id": "synthetic-baseline",
            "start": "2020-01-01",
            "end": "2021-12-31",
            "value": baseline,
            "complete": True,
            "version": "1.0.0",
        },
        "current_value": current,
        "change": {
            "absolute": 10.0,
            "relative": 10.0 / baseline,
        },
        "trend": "increasing",
        "components": components,
        "warnings": [
            {
                "code": "EXPERIMENTAL",
                "severity": "info",
                "message": "This scorer or series has not completed all validation and production gates.",
            }
        ],
        "suppression": {"status": "released", "reasons": []},
        "lineage": {
            "data_snapshot_ids": [f"synthetic-{score['id'].lower()}-snapshot-v1"],
            "run_id": f"contract-fixture-{score['id'].lower()}",
            "manifest_sha256": hashlib.sha256(score["id"].encode()).hexdigest(),
        },
        "versions": {
            "scorer": "1.0.0",
            "feature_pipeline": "1.0.0",
            "corpus": "1.0.0",
            "benchmark": "1.0.0",
            "ontology": "0.1.0",
            "score_registry": "1.0.0",
            "warning_registry": "1.0.0",
            "release_registry": "1.0.0",
        },
        "calculated_at": "2026-07-25T12:00:00Z",
        "links": {
            "methodology": "/observatory/methods",
            "benchmark": "/observatory/benchmarks/contract-fixtures-v1",
            "release": "/observatory/releases/contract-fixtures-v1",
        },
    }


def suppressed_fixture(base: dict) -> dict:
    value = copy.deepcopy(base)
    value["score"] = None
    value["confidence"]["value"] = None
    value["uncertainty_interval"]["lower"] = None
    value["uncertainty_interval"]["upper"] = None
    value["baseline"]["value"] = None
    value["baseline"]["complete"] = False
    value["current_value"] = None
    value["change"] = {"absolute": None, "relative": None}
    value["trend"] = "insufficient"
    value["coverage"]["complete"] = False
    for component in value["components"].values():
        component["raw_value"] = None
        component["normalized_value"] = None
        component["status"] = "suppressed"
    value["warnings"] = [
        {
            "code": "LOW_SAMPLE_SIZE",
            "severity": "error",
            "message": "The eligible observation count is below the approved release threshold.",
        },
        {
            "code": "SUPPRESSED",
            "severity": "error",
            "message": "The result is intentionally withheld because one or more required gates failed.",
        },
    ]
    value["suppression"] = {
        "status": "suppressed",
        "reasons": ["LOW_SAMPLE_SIZE"],
    }
    return value


def negative_case(name: str, payload: dict, expected_error: str) -> dict:
    return {
        "fixture_version": "observatory.contract_negative_fixture.v1",
        "name": name,
        "expected_error": expected_error,
        "payload": payload,
    }


def main() -> None:
    registry = load_json("score-registry.json")
    positives = {
        score["id"].lower(): score_fixture(score, index)
        for index, score in enumerate(registry["scores"])
    }

    special = {}
    special["suppressed"] = suppressed_fixture(positives["s7"])

    special["warned"] = copy.deepcopy(positives["s3"])
    special["warned"]["warnings"].append(
        {
            "code": "SOURCE_MIX_SHIFT",
            "severity": "warning",
            "message": "The source-family composition changed beyond the approved comparison tolerance.",
        }
    )

    special["exposure_association"] = copy.deepcopy(positives["s3"])
    special["exposure_association"]["release_id"] = "contract-fixtures-s3-exposure-v1"
    special["exposure_association"]["study_release_id"] = "study-fixture-exposure-v1"
    special["exposure_association"]["evidence_class"] = "exposure_association"

    special["causal_estimate"] = copy.deepcopy(positives["s7"])
    special["causal_estimate"]["release_id"] = "contract-fixtures-s7-causal-v1"
    special["causal_estimate"]["study_release_id"] = "study-fixture-causal-v1"
    special["causal_estimate"]["evidence_class"] = "causal_estimate"

    special["version_break"] = copy.deepcopy(positives["s3"])
    special["version_break"]["versions"]["scorer"] = "2.0.0"
    special["version_break"]["warnings"].append(
        {
            "code": "VERSION_BREAK",
            "severity": "warning",
            "message": "A major scorer version starts a separate series unless an approved bridge permits comparison.",
        }
    )

    negatives = []

    payload = copy.deepcopy(positives["s1"])
    payload["score_id"] = "ALL"
    negatives.append(negative_case("public_composite", payload, "schema_error"))

    payload = copy.deepcopy(positives["s2"])
    payload["warnings"][0]["code"] = "UNKNOWN_WARNING"
    negatives.append(negative_case("unknown_warning", payload, "unknown_warning"))

    payload = copy.deepcopy(positives["s3"])
    del payload["lineage"]
    negatives.append(negative_case("missing_lineage", payload, "schema_error"))

    payload = copy.deepcopy(positives["s4"])
    payload["period"]["start"] = "2026-07-01"
    payload["period"]["end"] = "2026-06-30"
    negatives.append(negative_case("invalid_period", payload, "invalid_period"))

    payload = copy.deepcopy(positives["s5"])
    payload["confidence"]["value"] = 1.5
    negatives.append(negative_case("invalid_confidence", payload, "schema_error"))

    payload = copy.deepcopy(positives["s6"])
    payload["uncertainty_interval"]["lower"] = 80.0
    payload["uncertainty_interval"]["upper"] = 20.0
    negatives.append(negative_case("invalid_uncertainty", payload, "invalid_uncertainty"))

    payload = suppressed_fixture(positives["s7"])
    payload["score"] = 50.0
    negatives.append(negative_case("suppressed_non_null", payload, "schema_error"))

    payload = copy.deepcopy(positives["s8"])
    payload["coverage"]["complete"] = False
    negatives.append(negative_case("incomplete_released_coverage", payload, "schema_error"))

    payload = copy.deepcopy(positives["s1"])
    del payload["components"]["source_breadth"]
    negatives.append(negative_case("missing_required_component", payload, "missing_component"))

    payload = copy.deepcopy(positives["s2"])
    payload["score"] += 1.0
    negatives.append(negative_case("arithmetic_mismatch", payload, "arithmetic_mismatch"))

    payload = copy.deepcopy(positives["s1"])
    payload["evidence_class"] = "causal_estimate"
    payload["study_release_id"] = "unapproved-study"
    negatives.append(negative_case("unapproved_causal_class", payload, "unsupported_evidence_class"))

    payload = copy.deepcopy(positives["s3"])
    first_component = next(iter(payload["components"].values()))
    first_component["weight"] = 0.9
    negatives.append(negative_case("component_weight_mismatch", payload, "component_weight_mismatch"))

    payload = copy.deepcopy(positives["s3"])
    payload["release_id"] = "contract-fixtures-s3-exposure-v1"
    payload["evidence_class"] = "exposure_association"
    negatives.append(negative_case("missing_study_release", payload, "study_release_required"))

    payload = copy.deepcopy(positives["s4"])
    payload["private_diagnostic"] = "must never cross a public boundary"
    negatives.append(negative_case("unknown_field", payload, "schema_error"))

    for directory in (FIXTURES / "positive", FIXTURES / "negative"):
        directory.mkdir(parents=True, exist_ok=True)
        for existing in directory.glob("*.json"):
            existing.unlink()

    for name, payload in {**positives, **special}.items():
        write_json(FIXTURES / "positive" / f"{name}.json", payload)
    for case in negatives:
        write_json(FIXTURES / "negative" / f"{case['name']}.json", case)

    manifest = {"schema_version": "observatory.fixture_manifest.v1", "files": []}
    for path in sorted(FIXTURES.glob("*/*.json")):
        manifest["files"].append(
            {
                "path": path.relative_to(CONTRACTS).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    write_json(FIXTURES / "manifest.json", manifest)


if __name__ == "__main__":
    main()
