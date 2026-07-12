import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKSUM_MANIFEST = REPO_ROOT / "metadata" / "artifact_checksums.sha256"
PUBLICATION_SHIFT_ARTIFACT = "services/gateway/model_artifacts/publication_shift/publication_shift_lexical_v1.joblib"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_artifact_checksum_manifest_matches_tracked_files():
    mismatches = []
    for line in CHECKSUM_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative_path = line.split(maxsplit=1)
        actual = _sha256(REPO_ROOT / relative_path)
        if actual != expected:
            mismatches.append((relative_path, expected, actual))

    assert mismatches == []


def test_publication_shift_artifact_is_recorded_in_global_checksum_manifest():
    manifest = CHECKSUM_MANIFEST.read_text(encoding="utf-8")

    assert PUBLICATION_SHIFT_ARTIFACT in manifest
