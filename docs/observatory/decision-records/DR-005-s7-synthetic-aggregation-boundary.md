# DR-005: S7 Synthetic Aggregation Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G2 formula bootstrap only |
| Affected spec versions | IS-003 v0.1.0; ES-005 v0.1.0 |
| Supersedes | None |

## Decision

Approve implementation and testing of the ES-005 ordinal formula, employer
balancing, baseline-cell standardization, coverage gates, deterministic
employer-cluster bootstrap, and sensitivity calculations using synthetic
observations and explicitly approved synthetic baseline fixtures.

The provisional severity mapping is `none=0`, `optional=1`, `encouraged=2`,
`expected=3`, `required=4`, and `monitored_or_enforced=5`, divided by five and
scaled to 0-100.

## Fail-closed release rule

Until the real baseline, weighting policy, ES-004 artifact, and ES-009 benchmark
pass their gates, every score-contract projection must:

- use suppression status;
- null score, current, baseline, change, interval, confidence, and component
  values;
- report `EXPERIMENTAL`, `BENCHMARK_REGRESSION`, and `SUPPRESSED`;
- retain candidate formula values only in private bootstrap diagnostics;
- identify the implementation as bootstrap-only.

## Prohibited uses

Synthetic aggregate values cannot be published as observed employer trends,
compared with the existing Toslop AI-likeness series, or used in exposure or
causal claims. The provisional mapping and cell policy are not frozen scorer
semantics.

## Expansion gate

Release requires approved baseline dates and cell weights, real corpus and
extractor releases, effective-sample and sensitivity thresholds, protected
benchmark success, backfill evidence, and a non-fixture release registry row.

## Approval evidence

Ryan Cook's implementation instruction on 2026-07-25, constrained by DR-001
through DR-004.
