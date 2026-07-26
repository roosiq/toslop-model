# ES-016: Source Concentration Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic formula complete; mappings and release blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-010 v0.1.0 bootstrap scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1-G5 |
| Start prerequisites | ES-001, ES-002 |
| Stage interfaces | ES-009 evaluation; ES-010 released-score delivery |

## Implementation authorization

DR-009 authorizes synthetic canonical mappings, concentration formulas, and
tests. Real crawling, ownership claims, and release remain blocked.

## Outcome

Calculate deterministic S2 domain, publisher, and ownership concentration from
eligible authored-reference counts while preserving mapping coverage and
suppression.

## Current state

Strict aggregate distributions, mapping coverage, HHI, top-k, entropy,
effective-count diagnostics, and a suppressed ES-001 projection are implemented
in `slopslingers-infra` PR 12. Real link extraction, canonical mappings, and
benchmarks do not exist.

## Architecture and boundaries

```text
eligible authored links -> canonical domains -> publisher/owner mappings
                        -> level distributions -> S2 components
                        -> coverage/suppression -> ES-001 output
```

Text extraction and entity mapping are private; aggregate distributions cross
into the scorer boundary.

## Data contracts

The input contains frame, period, level (`domain`, `publisher`, `ownership`),
versioned destination IDs and non-negative counts, eligible document count,
mapping coverage, and deduplication manifest. The output components are
`domain_concentration`, `publisher_concentration`, and
`ownership_concentration`.

## Algorithm design

For shares `p`, compute HHI `sum(p^2)`, top-1 and top-5 shares, entropy, and
effective source count. Normalize HHI for observed cardinality:
`(HHI - 1/k)/(1 - 1/k)` for `k > 1`; a one-source monopoly is 1.
Provisional level concentration is the equal mean of normalized HHI and top-1
share. S2 is the equal mean of the three level components times 100.
Unresolved mappings are excluded only when coverage passes; otherwise the
affected level is missing and the score is suppressed.

## Implementation tasks

1. Define canonical-reference and versioned mapping contracts.
2. Implement distribution statistics and normalized concentration.
3. Implement domain, publisher, and owner component aggregation.
4. Add mapping coverage, deduplication, and suppression diagnostics.
5. Add monopoly, equal-share, mapping-merge, duplicate, and unresolved tests.
6. Benchmark authored-link extraction and mapping precision.
7. Run topic, genre, syndication, self-link, and leave-one-source sensitivities.
8. Backfill matched private frames and prepare release evidence.

## Test and benchmark plan

Exact numerical tests cover HHI, top-k, entropy, effective count, one-source,
and empty distributions. Properties cover permutation, count-scale, duplicate,
and concentration monotonicity. Benchmarks separately gate link extraction,
domain mapping, publisher mapping, and ownership mapping.

## Operational design

Mapping versions and source snapshots are part of the idempotency key.
Re-resolving ownership creates a new score run. Metrics include reference
count, unique destinations, mapping coverage, top shares, HHI, sensitivity
deltas, and suppression.

## Security, privacy, rights, and compliance

Ownership mappings require attributable evidence and review. Restricted mapping
evidence and source text remain private. Named public drill-down is disabled by
default.

## Release strategy

Release proceeds from synthetic mappings to private shadow, adjudicated mapping
benchmark, historical backfill, independent review, and G5. A mapping revision
creates a new release and never mutates an old result.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Template links included | extraction benchmark/drift | Suppress | Re-extract with frozen block rules |
| Ownership mapping stale | expiry and evidence audit | Suppress owner component | Review and version mappings |
| Syndication dominates | logical identity coverage | Warn or suppress | Deduplicate and rerun |
| One level lacks coverage | mapping threshold | Suppress headline | Publish valid components only if approved |

## Definition of done

- Exact formulas and synthetic projections pass.
- Link extraction and all mapping benchmarks meet thresholds.
- Source, mapping, deduplication, baseline, uncertainty, sensitivity, lineage,
  monitoring, and G5 evidence are complete.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Registrable-domain and host policy | Data lead | G1 |
| Level component formula and weights | Research lead | G2 |
| Ownership evidence expiry | Governance reviewer | G1 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap |
| Approved execution version | 0.1.0 bootstrap scope |
| Approved intent version | IS-010 v0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |
