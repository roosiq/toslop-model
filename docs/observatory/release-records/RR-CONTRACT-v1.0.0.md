# RR-CONTRACT-v1.0.0: Observatory Score Contract

| Field | Value |
| --- | --- |
| Status | Shadow candidate |
| Created | 2026-07-25 |
| Artifact | Score output contract and semantic registries |
| Artifact version | 1.0.0 |
| Release owner | Applied science lead |
| Target state | Shadow |
| Affected specs | IS-001 v0.1.0; ES-001 v0.1.0 |

## Release contents

- `score-output.schema.json` with release and registry linkage.
- Score, warning, evidence-class, release, and version-bridge registries at
  `1.0.0`.
- Thirteen positive and fourteen negative public-safe fixtures with a checksum
  manifest.
- Exact-byte mirrors in the private gateway and public Worker repositories.
- Python Pydantic and JavaScript JSON Schema plus semantic validators.
- Generated public contract reference.

The immutable code revisions are recorded when the three repository changes
are committed. Until then this packet remains a shadow candidate.

## Gate evidence

| Gate | Disposition | Evidence |
| --- | --- | --- |
| G0 implementation | Pass | DR-001 |
| G0 multi-role ontology approval | Pending | IS-001 approval table |
| G3 contract conformance | Local pass | Python and JavaScript fixture suites |
| G5 production release | Pending | No scorer or API activation authorized |

## Known limitations

- Scorer-specific baselines, minimum samples, formulas, and confidence
  calibration are not approved by this shared contract.
- The release registry contains synthetic contract fixtures only.
- Entity-level publication remains disabled.
- No score producer or public score endpoint is enabled.

## Rollout and rollback

1. Run canonical registry and fixture checks.
2. Verify mirror checksums in both consumers.
3. Run Python and JavaScript conformance suites.
4. Shadow-validate synthetic outputs only.
5. Do not enable a scorer or endpoint under this record.

Rollback restores the prior mirror commit in both consumers, removes the
validator call from the consumer build, and retains the failed fixture and
validation code in the incident record. A rollback never substitutes a looser
schema or silently accepts an unknown value.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending shadow release approval |
| Approver | None |
| Decision date | None |
| Evidence | Local conformance run pending committed revisions |
