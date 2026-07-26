# DR-007: Benchmark Synthetic Framework Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G2 framework bootstrap only |
| Affected spec versions | IS-006 v0.1.0; ES-009 v0.1.0 |
| Supersedes | None |

## Decision

Approve implementation and testing of the synthetic, no-text, and protected
evaluation framework described by ES-009 without authorizing human benchmark
collection or a scorer validation claim.

The approved boundary includes:

- strict benchmark-item, prediction-submission, and freeze-record contracts;
- deterministic transitive grouping, split assignment, and overlap audit;
- append-only double annotation and adjudication state transitions using
  authored fixtures;
- a role-restricted in-memory final-label store with access audit;
- classification and pairwise metrics;
- immutable gate definitions and PASS, HOLD, and REJECT behavior;
- prediction-only protected evaluation with checksum, coverage, artifact,
  freeze-record, and scorer-lineage controls;
- an allowlisted aggregate public packet and restricted-field hygiene scan;
- reference passing and failing candidates using synthetic labels.

## Prohibited uses

This decision does not approve real benchmark sources, annotator recruitment,
protected production storage, benchmark 1.0.0, final S7 or S3 thresholds, a
VALIDATED or RELEASED scorer disposition, or any empirical performance claim.

Synthetic gate results demonstrate harness behavior only. They do not establish
construct validity, scorer accuracy, external validity, or causal validity.

## Expansion gate

Human benchmark execution requires the source frame, source rights, annotator
qualification, protected-store operator, split proportions, task design, and
thresholds listed in IS-006 and ES-009 to be approved. Protected final
evaluation additionally requires one frozen scorer lineage, an immutable final
manifest, role isolation, independent review, and benchmark 1.0.0 release
evidence.

## Approval evidence

Ryan Cook's instruction on 2026-07-25 to create todos for every spec and build
them, constrained by DR-001 through DR-006 and the G0-G5 release gates.
