#!/usr/bin/env python3
"""Generate public-safe ES-001 registry reference documentation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "observatory" / "contracts"
OUTPUT = CONTRACTS / "reference.md"


def load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def main() -> None:
    scores = load("score-registry.json")
    warnings = load("warning-codes.json")
    evidence = load("evidence-classes.json")
    lines = [
        "# Observatory Contract Reference",
        "",
        "Generated from the versioned ES-001 registries. Approved claim language",
        "remains in the intent and execution specifications; this file does not",
        "replace it.",
        "",
        f"Score registry: `{scores['registry_version']}`",
        "",
        f"Warning registry: `{warnings['registry_version']}`",
        "",
        "## Scores",
        "",
        "| ID | Name | Direction | Unit | Required components |",
        "| --- | --- | --- | --- | --- |",
    ]
    for score in scores["scores"]:
        components = ", ".join(f"`{item}`" for item in score["required_components"])
        lines.append(
            f"| {score['id']} | {score['name']} | `{score['direction']}` | "
            f"`{score['unit']}` | {components} |"
        )
    lines.extend(
        [
            "",
            "Public composites are prohibited. Every score retains its own",
            "construct, evidence class, release, lineage, components, and warnings.",
            "",
            "## Evidence Classes",
            "",
            "| ID | Meaning | Separate study required |",
            "| --- | --- | --- |",
        ]
    )
    for item in evidence["classes"]:
        required = "Yes" if item["requires_study_release"] else "No"
        lines.append(f"| `{item['id']}` | {item['meaning']} | {required} |")
    lines.extend(
        [
            "",
            "## Warning Codes",
            "",
            "| Code | Severity | Meaning |",
            "| --- | --- | --- |",
        ]
    )
    for item in warnings["warnings"]:
        lines.append(
            f"| `{item['code']}` | `{item['default_severity']}` | {item['message']} |"
        )
    lines.extend(
        [
            "",
            "## Compatibility",
            "",
            "- Patch versions may correct documentation without changing semantics.",
            "- Minor versions may add backward-compatible fields.",
            "- Major scorer versions start separate series.",
            "- An approved bridge may explain comparison, but contract fixtures never",
            "  permit an automatic major-version join.",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
