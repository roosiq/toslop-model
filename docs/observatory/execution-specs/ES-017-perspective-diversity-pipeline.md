# ES-017: Perspective Diversity Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic formula complete; taxonomy extraction blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-011 v0.1.0 bootstrap scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1-G5 |
| Start prerequisites | ES-001, ES-002 |
| Stage interfaces | ES-009 protected evaluation; ES-010 delivery |

## Implementation authorization

DR-009 authorizes a synthetic taxonomy, aggregate category-count formula, and
tests. Real-text extraction and public frame labels remain blocked.

## Outcome

Implement the S4 aggregate kernel and contracts for frame, argument, cause, and
action breadth with explicit unknown coverage and fail-closed release.

## Current state

The strict aggregate category model, capacity and unknown controls, diversity
kernel, and suppressed ES-001 projection are implemented in
`slopslingers-infra` PR 12. No governed real taxonomy, extraction runtime, or
protected S4 benchmark exists.

## Architecture and boundaries

```text
approved text -> private multi-label extraction -> matched category counts
              -> breadth/evenness components -> coverage and suppression
              -> ES-001 S4 output
```

The synthetic bootstrap starts at matched category counts and does not process
real text.

## Data contracts

Each aggregate identifies frame, period, category family, versioned label IDs,
weighted non-negative counts, eligible and unknown counts, and matched-control
coverage. Required families map to `frame_breadth`, `argument_breadth`,
`cause_breadth`, and `action_breadth`.

## Algorithm design

For each family, calculate normalized entropy and effective category count.
Normalize effective count as `(effective_count - 1)/(approved_capacity - 1)`.
The family component is the equal mean of normalized entropy and normalized
effective count. S4 is the equal mean of four family components times 100.
Unknown observations remain in coverage, not category shares. Missing family,
unknown rate over threshold, or unsupported capacity suppresses the headline.

## Implementation tasks

1. Define taxonomy, category-count, unknown, and coverage contracts.
2. Implement entropy, effective count, capacity normalization, and components.
3. Implement S4 aggregation and suppressed ES-001 projection.
4. Add monopoly, balanced, paraphrase-equivalent, unknown, and minority tests.
5. Draft and adjudicate the frame/argument/cause/action taxonomy.
6. Build deterministic baseline classifier and optional pinned LLM candidate.
7. Run protected benchmark, event/topic matching, and stability analyses.
8. Backfill private shadow frames and prepare G4/G5 evidence.

## Test and benchmark plan

Unit and property tests cover bounds, categories, capacity, unknowns,
permutation, duplication, and distinct-frame monotonicity. Protected tests
cover minority recall, multi-label agreement, event leakage, source/genre
slices, and taxonomy drift.

## Operational design

Taxonomy, extractor, topic, event, corpus, and scorer versions form the
idempotency key. Metrics include family coverage, unknown rate, effective
counts, entropy, minority support, benchmark drift, sensitivity deltas, and
suppression.

## Security, privacy, rights, and compliance

Evidence spans and speaker-level labels remain restricted. Sensitive labels
below disclosure thresholds are never published. Extraction providers receive
text only after source and provider review.

## Release strategy

Progress from synthetic taxonomy to development labels, frozen candidate,
protected evaluation, private shadow, G4 claims review, and G5. Taxonomy or
label changes require a new release and backfill.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Taxonomy misses emerging frame | unknown/drift rate | Suppress or warn | Review taxonomy and version |
| Topic/event confounding | matched-control delta | Suppress | Rebuild matched frame |
| Minority label disclosure risk | support threshold | Hide component | Aggregate or suppress |
| Extractor drift | frozen benchmark regression | Block release | Roll back extractor |

## Definition of done

- Synthetic contracts, exact formulas, and property tests pass.
- Taxonomy, annotation, protected benchmark, minority recall, matched controls,
  uncertainty, sensitivities, monitoring, G4, and G5 pass.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Taxonomy and approved capacities | Research lead | G2 |
| Multi-label weighting | Applied science lead | G2 |
| Unknown and disclosure thresholds | Governance reviewer | G3 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap |
| Approved execution version | 0.1.0 bootstrap scope |
| Approved intent version | IS-011 v0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |
