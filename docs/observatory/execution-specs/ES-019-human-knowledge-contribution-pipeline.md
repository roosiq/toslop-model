# ES-019: Human Knowledge Contribution Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic formula complete; real collection blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-013 v0.1.0 bootstrap scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1-G5 |
| Start prerequisites | ES-001, ES-002 |
| Stage interfaces | ES-009 evaluation; ES-010 delivery |

## Implementation authorization

DR-009 authorizes synthetic platform activity observations and deterministic
aggregation. Platform collection and contributor identity processing remain
blocked by source and privacy decisions.

## Outcome

Implement S6 platform-normalized Q&A, explanatory, and maintenance contribution
components, fixed-panel weighting, bot coverage, and fail-closed score output.

## Current state

Strict platform aggregate inputs, baseline-ratio normalization, fixed weights,
bot/source-break controls, and suppressed ES-001 projection code are
implemented in `slopslingers-infra` PR 12. No approved activity ontology,
platform adapter, cohort store, or fitted baseline exists.

## Architecture and boundaries

```text
approved platform dumps -> platform eligibility/bot rules -> aggregate activity
                        -> baseline-normalized components -> fixed panel
                        -> S6 output and suppression
```

The scorer reads aggregates, not contributor event histories.

## Data contracts

Platform observations contain period, frame, platform, eligible object and
contributor counts, Q&A, explanation, maintenance, response/reuse rates, bot
and unresolved shares, platform-break status, and manifest versions. Counts are
non-negative and rates are bounded.

## Algorithm design

Within each platform and component, calculate a robust baseline ratio clipped
to the approved range and mapped to `[0,1]`. Component values combine eligible
activity rate and contributor breadth. Fixed baseline platform weights produce
`qa_contribution`, `explanatory_contribution`, and
`maintenance_contribution`; S6 is their equal mean times 100 for synthetic
bootstrap. Missing baseline, platform break, bot uncertainty, or inadequate
panel suppresses release.

## Implementation tasks

1. Define activity ontology and aggregate platform contracts.
2. Implement bounded baseline-ratio transform and platform weighting.
3. Implement three required components, diagnostics, and suppression.
4. Add duplicate, bot, bulk import, break, monotonic, and panel tests.
5. Approve one source decision and connector spec per platform.
6. Benchmark eligibility, bot resolution, and event deduplication.
7. Fit baseline, weights, uncertainty, and fixed-community sensitivities.
8. Run private backfill, external validation, G4, and G5 review.

## Test and benchmark plan

Tests cover invalid rates, zero baseline, bounds, duplicate invariance, added
contribution monotonicity, bot exclusion, and platform breaks. Benchmarks gate
platform eligibility and automation detection separately. Integration projects
a suppressed ES-001 S6 result.

## Operational design

Platform snapshots close independently and aggregate only when the fixed panel
is complete. Idempotency includes source, ontology, bot, baseline, and scorer
versions. Metrics include eligible events, contributors, bot share, panel
weight, components, breaks, uncertainty, and suppression.

## Security, privacy, rights, and compliance

Private stable identifiers are minimized, scoped, encrypted, and retained only
when approved. The aggregate scorer does not receive direct identifiers.
Deleted/restricted descendants are retired through ES-002 lineage.

## Release strategy

Start with synthetic platform fixtures, then one approved platform pilot,
multi-platform shadow, baseline backfill, protected benchmark, G4 review, and
G5. Rollback uses a complete prior platform/ontology/scorer release.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Mass automated import | volume/bot diagnostics | Exclude or suppress | Reprocess with reviewed rules |
| Platform migration | registry break | Block cross-break trend | Start new segment or bridge |
| Contributor resolution weak | unresolved rate | Suppress breadth component | Improve reviewed resolution |
| One platform dominates | weight/sensitivity delta | Warn or suppress | Use fixed panel and caps |

## Definition of done

- Synthetic contracts, formula, suppression, and property tests pass.
- Source rights, privacy, adapters, eligibility and bot benchmarks, baseline,
  sensitivities, monitoring, G4, and G5 evidence pass.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Activity ontologies and platforms | Research lead | G1 |
| Baseline transform and weights | Applied science lead | G2 |
| Pseudonym and bot policies | Governance reviewer | G1-G2 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap |
| Approved execution version | 0.1.0 bootstrap scope |
| Approved intent version | IS-013 v0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |
