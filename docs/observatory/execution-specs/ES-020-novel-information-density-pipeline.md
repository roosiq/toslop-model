# ES-020: Novel Information Density Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic formula complete; real extraction blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-014 v0.1.0 bootstrap scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1-G5 |
| Start prerequisites | ES-001, ES-006 |
| Stage interfaces | ES-009 protected evaluation; ES-017 perspective input; ES-010 delivery |

## Implementation authorization

DR-009 authorizes synthetic cluster-count observations, density formulas, and
tests. Real claim extraction, sensitive entity processing, and score release
remain blocked.

## Outcome

Implement the S8 aggregate kernel for claim, perspective, and source novelty per
explicit content denominator with extraction coverage, cluster stability, and
suppression.

## Current state

Strict aggregate hierarchy, density normalization, coverage and stability
controls, and suppressed ES-001 projection code are implemented in
`slopslingers-infra` PR 12. No governed claim schema, extractor, entailment
clusterer, fitted denominator registry, or protected benchmark exists.

## Architecture and boundaries

```text
approved matched corpus -> private claims/attribution -> bounded clustering
                        -> aggregate cluster counts and denominator
                        -> S8 components -> coverage/suppression
```

Synthetic bootstrap begins at aggregate counts and does not process text.

## Data contracts

An aggregate contains frame, period, eligible content units/tokens, extracted
claim count, unique claim clusters, unique perspective clusters, unique
attributable sources, extraction coverage, cluster stability, and deduplication
manifest. All counts are non-negative and unique counts cannot exceed their
eligible parent counts.

## Algorithm design

For each required family, density is unique eligible clusters per approved
content unit. Normalize against a frozen baseline reference and ceiling to
`[0,1]`. Required components are `claim_novelty`,
`perspective_novelty`, and `source_novelty`; synthetic S8 is their equal mean
times 100. Repetition ratio, extraction coverage, and cluster stability are
diagnostics. Missing denominator, low extraction coverage, or unstable
clustering suppresses the headline.

## Implementation tasks

1. Define aggregate claim, cluster, attribution, and denominator contracts.
2. Implement bounded density normalization and three components.
3. Implement logical-dedup, coverage, stability, and suppression checks.
4. Add repeated, distinct, contradiction, denominator, and low-coverage tests.
5. Freeze claim ontology and build deterministic baseline extractor.
6. Benchmark extraction and same-claim clustering on protected labels.
7. Run threshold, topic, event, genre, length, and source sensitivities.
8. Backfill private matched frames and complete G4/G5 evidence.

## Test and benchmark plan

Exact tests cover counts, densities, ceilings, bounds, and invalid hierarchy.
Properties cover permutation, duplicate/repetition behavior, distinct-claim
monotonicity, and finite outputs. Protected slices include paraphrase,
contradiction, specificity, event identity, attribution, and extraction misses.

## Operational design

Corpus, dedup, ontology, extractor, clusterer, denominator, baseline, and scorer
versions form the idempotency key. Metrics include extraction coverage,
clusters, repetition, stability, component densities, sensitivity deltas,
interval width, and suppression.

## Security, privacy, rights, and compliance

Claim spans and sensitive entity assertions remain restricted. Public outputs
contain thresholded counts and no raw claim text. Provider processing requires
source and provider approval.

## Release strategy

Move from synthetic aggregate fixtures to development extraction, frozen
candidate, protected evaluation, matched private backfill, G4 claims review,
and G5. Rollback restores one complete extraction/clustering/scorer bundle.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Extraction recall changes | frozen benchmark | Suppress | Roll back extractor |
| Cluster threshold unstable | sensitivity delta | Suppress | Recalibrate on development only |
| Topic/event mix changes | matched-frame coverage | Warn or suppress | Rebuild matched frame |
| Denominator missing | contract validation | Reject run | Recompute eligible units |

## Definition of done

- Synthetic contracts, density formulas, hierarchy checks, suppression, and
  property tests pass.
- Claim ontology, protected extraction/clustering benchmarks, baseline,
  sensitivities, privacy, monitoring, G4, and G5 evidence pass.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Claim ontology and denominator | Research lead | G2 |
| Cluster threshold and stability floor | Applied science lead | G2-G3 |
| Sensitive claim publication policy | Governance reviewer | G5 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap |
| Approved execution version | 0.1.0 bootstrap scope |
| Approved intent version | IS-014 v0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |
