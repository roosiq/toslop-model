#!/usr/bin/env python3
"""Verify the prepared INFINI-NEWS v1 collection boundary and public artifacts."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = Path(os.environ.get("PUBLICATION_SHIFT_PRIVATE_ROOT", REPO_ROOT / "services/data/publication_shift/infini_news_v1"))
PRIVATE_ROOT_MARKER = Path("services/data/publication_shift/infini_news_v1")
PUBLIC_ROOT = REPO_ROOT / "services/evals/publication_shift_model/infini_news_v1"
MANIFEST = PUBLIC_ROOT / "frozen_request_manifest_264000.json"
REPORT = PUBLIC_ROOT / "full_report.json"
PINNED_REVISION = "5b78199b86a838a5634b2d3267d72b98b8f71721"
EXPECTED_TOTAL = 264_000
HASH_RE = re.compile(r"[0-9a-f]{64}")
ABSOLUTE_LOCAL_PATH = re.compile(r"(?:^|\s)(?:/home/|/Users/|[A-Za-z]:[\\/]+Users[\\/]+)")
BANNED_VALUE_KEYS = {
    "text", "original_text", "normalized_text", "maintext", "title", "description", "preview", "body",
    "content", "url", "normalized_url", "link", "sitename", "url_hostname", "source_domain",
}


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
    paths = [PRIVATE_ROOT / name for name in ["normalized_rows.jsonl", "progress.json", "candidate_records.sqlite3"]]
    existing = [path for path in paths if path.exists()]
    require(bool(existing), "no private collection artifacts found to check-ignore")
    if PRIVATE_ROOT.resolve().is_relative_to(REPO_ROOT.resolve()):
        ignored_paths = [path.relative_to(REPO_ROOT) for path in existing]
    else:
        # External recovered private inputs cannot be checked by git pathspec;
        # verify the logical in-repo private locations remain ignored.
        ignored_paths = [PRIVATE_ROOT_MARKER / path.name for path in existing]
    for path in ignored_paths:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
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
    require("counts_by_sitename" not in report, "public report contains raw sitename count keys")
    sitename_counts = report.get("counts_by_sitename_hash")
    require(isinstance(sitename_counts, dict) and bool(sitename_counts), "missing hashed sitename counts")
    require(all(HASH_RE.fullmatch(str(key)) for key in sitename_counts), "sitename count map contains a non-hash key")
    require(
        all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in sitename_counts.values()),
        "sitename count map contains an invalid count",
    )
    require(sum(sitename_counts.values()) == EXPECTED_TOTAL, "hashed sitename counts do not reconcile to 264,000")
    encoded_report = json.dumps(report, sort_keys=True).lower()
    for banned in ['"text"', '"normalized_text"', '"title"', '"preview"', '"body"', '"content"']:
        require(banned not in encoded_report, f"public report contains banned key/string {banned}")


def _scan_json(payload: object, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}/{key}"
            lowered = str(key).lower()
            # Numeric overlap-audit counters may legitimately be named after a
            # source field. Public article-bearing values may not.
            if lowered in BANNED_VALUE_KEYS and not isinstance(value, (int, float, bool, type(None))):
                findings.append(child)
            findings.extend(_scan_json(value, child))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_scan_json(value, f"{path}[{index}]"))
    elif isinstance(payload, str) and ABSOLUTE_LOCAL_PATH.search(payload):
        findings.append(path)
    return findings


def assert_all_tracked_publication_shift_artifacts_safe() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "services/evals/publication_shift_model"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    findings: list[str] = []
    for relative in completed.stdout.splitlines():
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        decoded = path.read_bytes().decode("utf-8", errors="ignore")
        if ABSOLUTE_LOCAL_PATH.search(decoded):
            findings.append(f"{relative}:absolute-local-path")
        try:
            if path.suffix == ".json":
                findings.extend(f"{relative}:{item}" for item in _scan_json(json.loads(decoded)))
            elif path.suffix == ".jsonl":
                for line_number, line in enumerate(decoded.splitlines(), 1):
                    if line.strip():
                        findings.extend(f"{relative}:{line_number}:{item}" for item in _scan_json(json.loads(line)))
        except json.JSONDecodeError as exc:
            findings.append(f"{relative}:parse-error:{exc}")
    require(not findings, "tracked publication-shift artifact privacy findings: " + ", ".join(findings[:20]))


def main() -> int:
    assert_private_permissions()
    assert_git_ignored()
    assert_manifest_and_report()
    assert_all_tracked_publication_shift_artifacts_safe()
    print("INFINI-NEWS v1 collection verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
