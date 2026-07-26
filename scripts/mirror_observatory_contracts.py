#!/usr/bin/env python3
"""Mirror canonical Observatory contracts into private and public consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


MODEL_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MODEL_ROOT / "docs" / "observatory" / "contracts"
DEFAULT_CONSUMERS = [
    MODEL_ROOT.parent
    / "slopslingers-infra"
    / "services"
    / "gateway"
    / "app"
    / "observatory"
    / "contracts",
    MODEL_ROOT.parent / "toslop" / "public" / "observatory" / "contracts",
]
CANONICAL_FILES = [
    "score-output.schema.json",
    "score-registry.json",
    "warning-codes.json",
    "evidence-classes.json",
    "release-registry.json",
    "version-bridges.json",
]


def source_files() -> list[Path]:
    files = [SOURCE / name for name in CANONICAL_FILES]
    files.extend(sorted((SOURCE / "fixtures").rglob("*.json")))
    return files


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_manifest() -> dict:
    return {
        "schema_version": "observatory.contract_mirror_manifest.v1",
        "canonical_repository": "roosiq/toslop-model",
        "files": [
            {
                "path": path.relative_to(SOURCE).as_posix(),
                "sha256": digest(path),
            }
            for path in source_files()
        ],
    }


def mirror(consumer: Path) -> None:
    for source in source_files():
        relative = source.relative_to(SOURCE)
        target = consumer / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (consumer / "mirror-manifest.json").write_text(
        json.dumps(expected_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def check(consumer: Path) -> list[str]:
    errors = []
    for source in source_files():
        relative = source.relative_to(SOURCE)
        target = consumer / relative
        if not target.is_file():
            errors.append(f"missing:{relative.as_posix()}")
        elif source.read_bytes() != target.read_bytes():
            errors.append(f"drift:{relative.as_posix()}")
    manifest_path = consumer / "mirror-manifest.json"
    if not manifest_path.is_file():
        errors.append("missing:mirror-manifest.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append("invalid:mirror-manifest.json")
        else:
            if manifest != expected_manifest():
                errors.append("drift:mirror-manifest.json")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--consumer", action="append", type=Path)
    args = parser.parse_args()
    consumers = args.consumer or DEFAULT_CONSUMERS

    failed = False
    for consumer in consumers:
        if args.check:
            errors = check(consumer)
            if errors:
                failed = True
                print(f"{consumer}: {'; '.join(errors)}")
            else:
                print(f"{consumer}: ok")
        else:
            mirror(consumer)
            print(f"{consumer}: mirrored")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
