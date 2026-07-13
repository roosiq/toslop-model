#!/usr/bin/env python3
"""Verify the prepared INFINI-NEWS v1 collection boundary and public artifacts."""

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = REPO_ROOT / "services/data/publication_shift/infini_news_v1"
PUBLIC_ROOT = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1"
MANIFEST = PUBLIC_ROOT / "frozen_request_manifest_264000.json"
REPORT = PUBLIC_ROOT / "full_report.json"
PINNED_REVISION = "5b78199b86a838a5634b2d3267d72b98b8f71721"
EXPECTED_TOTAL = 264_000


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_private_permissions() -> None:
    require(PRIVATE_ROOT.exists(), f"missing private root: {PRIVATE_ROOT}")
    require(mode(PRIVATE_ROOT) == 0o700, f"private root mode is {oct(mode(PRIVATE_ROOT))}, expected 0o700")
    for path in PRIVATE_ROOT.rglob("*"):
        expected = 0o700 if path.is_dir() else 0o600
        require(mode(path) == expected, f"{path} mode is {oct(mode(path))}, expected {oct(expected)}")


def assert_git_ignored() -> None:
    paths = [
        PRIVATE_ROOT / "normalized_rows.jsonl",
        PRIVATE_ROOT / "progress.json",
        PRIVATE_ROOT / "candidate_records.sqlite3",
    ]
    existing = [path for path in paths if path.exists()]
    require(bool(existing), "no private collection artifacts found to check-ignore")
    for path in existing:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=False,
        )
        require(completed.returncode == 0, f"private artifact is not git-ignored: {path}")


def assert_manifest_and_report() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    require(manifest["source_revision"] == PINNED_REVISION, "manifest source revision drifted")
    require(report["source_revision"] == PINNED_REVISION, "report source revision drifted")
    require(manifest["target_total_rows"] == EXPECTED_TOTAL, "manifest target total drifted")
    require(sum(manifest["targets_by_month"].values()) == EXPECTED_TOTAL, "month targets do not sum to 264,000")
    require(report["accepted_count"] == EXPECTED_TOTAL, "full report accepted count is not 264,000")
    require(report["target_total_rows"] == EXPECTED_TOTAL, "full report target total is not 264,000")
    require(report.get("private_output_root") == "services/data/publication_shift/infini_news_v1", "wrong private output root")
    require("records" not in report, "public full report must not contain per-record records")
    require(report.get("record_manifest_count") == EXPECTED_TOTAL, "private record manifest count mismatch")
    require(len(report.get("shard_identities", [])) > 0, "missing selected shard identities")
    encoded_report = json.dumps(report, sort_keys=True).lower()
    for banned in ['"text"', '"normalized_text"', '"title"', '"preview"', '"body"', '"content"']:
        require(banned not in encoded_report, f"public report contains banned key/string {banned}")


def main() -> int:
    assert_private_permissions()
    assert_git_ignored()
    assert_manifest_and_report()
    print("INFINI-NEWS v1 collection verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
