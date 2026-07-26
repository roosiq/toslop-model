#!/usr/bin/env python3
"""Validate canonical ES-001 registries and fixture integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "observatory" / "contracts"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    schema = load_json(CONTRACTS / "score-output.schema.json")
    scores = load_json(CONTRACTS / "score-registry.json")
    warnings = load_json(CONTRACTS / "warning-codes.json")
    releases = load_json(CONTRACTS / "release-registry.json")
    evidence = load_json(CONTRACTS / "evidence-classes.json")
    bridges = load_json(CONTRACTS / "version-bridges.json")

    require(schema["$schema"].endswith("2020-12/schema"), "unexpected JSON Schema dialect")
    require(scores["registry_version"] == "1.0.0", "score registry is not 1.0.0")
    require(
        [item["id"] for item in scores["scores"]]
        == ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
        "score registry must contain S1-S8 exactly once and in order",
    )
    require(not scores["public_composite_allowed"], "public composite must remain disabled")

    warning_codes = [item["code"] for item in warnings["warnings"]]
    require(len(warning_codes) == len(set(warning_codes)), "warning codes must be unique")
    evidence_ids = [item["id"] for item in evidence["classes"]]
    require(
        evidence_ids == ["descriptive", "exposure_association", "causal_estimate"],
        "evidence registry is incomplete",
    )
    require(releases["default_public_entity_policy"] == "aggregate_only", "entity policy drift")
    require(
        all(not item["automatic_join_allowed"] for item in bridges["bridges"]),
        "major-version bridges cannot automatically join contract fixtures",
    )

    required_versions = set(schema["properties"]["versions"]["required"])
    require(
        {"score_registry", "warning_registry", "release_registry"} <= required_versions,
        "score output does not pin every semantic registry",
    )

    manifest = load_json(CONTRACTS / "fixtures" / "manifest.json")
    listed_paths = set()
    for item in manifest["files"]:
        path = CONTRACTS / item["path"]
        require(path.is_file(), f"missing fixture: {item['path']}")
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"],
            f"fixture checksum drift: {item['path']}",
        )
        listed_paths.add(path.resolve())
    actual_paths = {
        path.resolve()
        for path in (CONTRACTS / "fixtures").glob("*/*.json")
    }
    require(listed_paths == actual_paths, "fixture manifest membership drift")
    require(
        len(list((CONTRACTS / "fixtures" / "positive").glob("*.json"))) == 13,
        "positive fixture count changed",
    )
    require(
        len(list((CONTRACTS / "fixtures" / "negative").glob("*.json"))) == 14,
        "negative fixture count changed",
    )
    print("Canonical Observatory contract checks passed.")


if __name__ == "__main__":
    main()
