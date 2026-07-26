# DR-004: S7 Bootstrap Extractor Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G2 bootstrap only |
| Affected spec versions | IS-003 v0.1.0; ES-004 v0.1.0 |
| Supersedes | None |

## Decision

Approve a deterministic, source-blind S7 rule candidate and authored synthetic
rubric suite under extractor version `bootstrap-rule-v0`.

Approve the highest qualifying passage level as the provisional document
conflict rule for synthetic tests only. Mask negated, quoted, third-party, and
historical-only passages from escalation. Preserve every passage prediction
and warning in private evidence.

Every output from this candidate must carry `release_state: bootstrap_only`.

## Prohibited uses

The bootstrap candidate cannot:

- emit an experimental, validated, or production S7 score;
- be described as benchmarked against public employer language;
- replace the ES-009 labeled or protected benchmark;
- set final probability, ambiguity, or mechanism thresholds;
- use source, employer, period, occupation, jurisdiction, URL, or current score
  as runtime features;
- publish document IDs, passage IDs, text, or offsets.

## Expansion gate

Freezing an extractor requires the approved ES-009 rubric, split manifests,
adjudicated development and validation labels, candidate comparison, artifact
checksums, source-blindness evidence, and one-time protected-final evaluation.

## Approval evidence

Ryan Cook's implementation instruction on 2026-07-25, constrained by DR-001
through DR-003 and the release gates in IS-003 and ES-004.
