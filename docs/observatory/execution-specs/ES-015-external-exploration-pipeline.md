# ES-015: External Exploration Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic bootstrap implementing; release blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-009 v0.1.0 bootstrap scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1-G5 |
| Start prerequisites | ES-001, ES-002 |
| Stage interfaces | ES-009 evaluation; ES-010 released-score delivery |

## Implementation authorization

DR-009 authorizes deterministic formula code, schemas, and synthetic tests.
Real source access, fitted baselines, causal studies, and score release remain
blocked.

## Outcome

Normalize aggregate exploration observations and calculate a reproducible,
suppressed-by-default S1 result with breadth, public-knowledge-use, and citation
depth components plus source-panel diagnostics.

## Current state

The shared score contract supports S1, but there is no S1 observation model,
aggregation kernel, baseline, collector, benchmark, or release artifact.

## Architecture and boundaries

```text
approved aggregate adapters -> normalized source observations
                            -> matched frame and source panel
                            -> S1 components and uncertainty
                            -> suppression and ES-001 validation
```

Adapters remain source-specific. The scorer accepts only no-user,
period-aggregate observations.

## Data contracts

An observation identifies period, frame, source family, topic, eligible event
count, destination counts, public-knowledge activity rate, citation-depth
distribution, coverage, and source-break status. Counts are non-negative;
rates are in `[0,1]`; destination labels are private pseudonyms.

The output uses the ES-001 S1 contract and required components
`source_breadth`, `public_knowledge_use`, and `citation_depth`.

## Algorithm design

For destination shares `p`, calculate normalized entropy
`H(p)/log2(k)` and effective destination count `2^H(p)`. Provisional
`source_breadth` is normalized entropy. `public_knowledge_use` is the
source-standardized eligible activity rate. `citation_depth` is the winsorized
mean eligible external-reference depth normalized by the approved ceiling.

Synthetic S1 is the equal-weight mean of the three bounded components times
100. Production weights, standardization, thresholds, and baseline require G2.
Any missing component, source break, or inadequate panel suppresses release.

## Implementation tasks

1. Implement strict aggregate observation and source-panel contracts.
2. Implement entropy, effective breadth, activity, and depth components.
3. Implement fixed-source weighting, coverage, and break diagnostics.
4. Implement deterministic aggregate and suppressed score projection.
5. Add equal-share, monopoly, source-break, missing, and monotonic fixtures.
6. Add source-specific execution specs only after rights decisions.
7. Fit baseline, uncertainty, and sensitivity thresholds on development data.
8. Run protected and external negative-control validation.
9. Produce methods and release evidence before ES-010 activation.

## Test and benchmark plan

Unit tests cover bounds, entropy, depth, weights, invalid values, and
suppression. Property tests cover permutation invariance, scale invariance of
destination counts, finite outputs, and breadth monotonicity. Integration tests
project a suppressed ES-001 result. Protected validation includes platform
break and placebo-event slices.

## Operational design

Monthly source-family jobs close before aggregation. Idempotency includes
source snapshot, frame, formula, and baseline versions. Metrics include source
families, eligible events, effective destinations, component values, interval
width, breaks, warnings, and suppression. A source break blocks comparison.

## Security, privacy, rights, and compliance

The scorer rejects user/session identifiers. Source adapters use least
privilege and source-specific retention. Public outputs contain aggregates
only; destination drill-down is disabled until separately approved.

## Release strategy

Ship synthetic code, then run source-specific private pilots, a fixed-panel
shadow backfill, protected evaluation, G4 claims review, and G5 cutover. Roll
back to the prior complete S1 release; never mix source panels or baselines.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Platform methodology break | source registry event | Suppress cross-break trend | Start a new comparable segment |
| Source outage | panel coverage | Suppress primary result | Restore or approve matched panel |
| Bot or bulk traffic | adapter quality flags | Exclude or suppress | Reprocess with frozen eligibility rule |
| Topic-mix shift | matched-frame diagnostic | Warn or suppress | Reweight to baseline frame |

## Definition of done

- Synthetic contracts, formulas, property tests, and ES-001 projection pass.
- Real sources have approved rights records and connector specs.
- Baseline, thresholds, protected benchmark, sensitivities, and negative
  controls pass.
- Methods, lineage, monitoring, rollback, G4, and G5 evidence are complete.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Source families and panel weights | Research lead | G1-G2 |
| Depth ceiling and activity denominator | Applied science lead | G2 |
| Minimum panel and source-break policy | Data lead | G3 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap |
| Approved execution version | 0.1.0 bootstrap scope |
| Approved intent version | IS-009 v0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |
