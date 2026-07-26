# ES-005: Employer Compulsion Aggregation

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-003 v0.1.0, approval pending |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1, G2, G3, G4, G5 |
| Start prerequisites | ES-001, ES-003, and ES-004 candidate outputs |
| Stage interfaces | ES-009 protected-final pass; released scores to ES-010 |

## Implementation authorization

Implementation may begin after IS-003 approval and draft work may use only
synthetic fixtures until ES-003, ES-004, ES-009, and the baseline and weighting
decision records pass their prerequisite gates.

## Outcome

Calculate reproducible monthly and quarterly S7 results from frozen document
labels, with baseline-standardized composition, employer clustering,
uncertainty, confidence inputs, suppression, sensitivity series, lineage, and
release evidence.

## Current state

No S7 score tables, formula, aggregation jobs, baseline registry, confidence
inputs, or release packet exist. The current public Toslop summary is an
AI-likeness series and remains separate.

## Architecture and boundaries

```text
frozen S7 document labels + corpus dimensions
                    |
                    v
eligible analytical cells
                    |
                    v
within-employer means
                    |
                    v
baseline-composition standardization
                    |
                    v
score + components + cluster bootstrap
                    |
                    v
suppression + confidence + contract validation
                    |
                    v
immutable S7 release
```

Proposed modules:

- `scorers/s7/aggregate.py`
- `scorers/s7/baselines.py`
- `scorers/s7/uncertainty.py`
- `scorers/s7/sensitivity.py`
- `scorers/s7/release.py`
- generic score-run and result repositories under `observatory/scores/`

## Data contracts

### Baseline registry

```json
{
  "schema_version": "observatory.baseline_registry.v1",
  "baseline_id": "s7-english-job-postings-pre-llm-v1",
  "score_id": "S7",
  "version": "1.0.0",
  "start": "2021-01-01",
  "end": "2022-11-29",
  "period_granularity": "month",
  "cell_dimensions": [
    "occupation_group",
    "industry_group",
    "jurisdiction_group",
    "source_family"
  ],
  "minimum_cell_documents": 20,
  "minimum_cell_employers": 10,
  "minimum_matched_weight": 0.8,
  "status": "proposed"
}
```

Dates are proposed and remain blocked by the IS-001 and IS-003 baseline
decision. The implementation accepts only an approved registry row.

### Aggregation tables

- `observatory.s7_document_predictions`: immutable ES-004 output.
- `observatory.score_runs`: run ID, score, period, frame, input manifests,
  config, status, timestamps, and failure.
- `observatory.score_results`: validated JSON contract plus indexed dimensions.
- `observatory.score_sensitivities`: named alternate result, config, and
  difference from primary.
- `observatory.score_release_members`: release ID and result IDs.

No score result stores or embeds raw text.

## Algorithm design

### Document severity

Map primary levels to fixed provisional severity:

```text
none=0, optional=1, encouraged=2, expected=3,
required=4, monitored_or_enforced=5
```

For eligible logical document `i`, normalized pressure is:

```text
d_i = severity_i / 5
```

The top-level S7 scale remains absolute and interpretable:

```text
S7 = 100 * standardized mean(d_i)
```

The ordinal mapping is frozen in the scorer release. Any weight change is a
major scorer version.

### Employer balancing

Within analytical cell `c`, calculate one mean per resolved employer:

```text
e_jc = mean(d_i for logical documents i from employer j in cell c)
p_ct = mean(e_jc for eligible employers j in period t)
```

This gives each employer equal weight within the cell. Exact and near-duplicate
logical documents already have one contribution. Unresolved employers do not
enter the primary employer-balanced score; their rate is a required coverage
field. If employer resolution coverage is below `0.80`, suppress the primary
score.

### Composition standardization

Let `pi_c` be the cell's approved share in the baseline frame. For period `t`:

```text
matched_weight_t = sum(pi_c for eligible cells c in t)
S7_t = 100 * sum(pi_c * p_ct for eligible cells c in t) / matched_weight_t
```

Suppress when `matched_weight_t < 0.80`. Cells require at least 20 logical
documents and 10 resolved employers unless the approved registry is stricter.

The primary result uses baseline cell weights. Required sensitivities are:

- current-composition employer-balanced;
- document-weighted;
- equal-source-family;
- fixed-employer panel;
- leave-one-source-family-out;
- leave-one-occupation-group-out.

### Components

Report:

- weighted primary-level shares for all six levels;
- `primary_level_pressure` using the formula above;
- prevalence of `required` or stronger;
- prevalence of `monitored_or_enforced`;
- each independent mechanism prevalence;
- ambiguous passage/document rate;
- unresolved employer rate;
- matched baseline weight;
- fixed-panel coverage.

Component shares use the same eligible cells and baseline weights as the
headline unless explicitly labeled sensitivity.

### Baseline and change

Baseline value is the mean of eligible monthly primary scores in the approved
baseline interval, using the same frozen cell weights and scorer version.

```text
absolute_change_t = S7_t - baseline_value
relative_change_t = absolute_change_t / baseline_value
```

`relative_change` is null when the baseline is zero. It is never substituted
with infinity or zero, and the result carries
`RELATIVE_CHANGE_UNDEFINED`.

### Uncertainty and trend

Use a cluster bootstrap with 2,000 deterministic replicates:

1. resample employers with replacement within each eligible cell;
2. retain all logical documents for each sampled employer;
3. recompute cell and standardized scores;
4. use the 5th and 95th percentiles for a 90% interval.

Seed is derived from scorer version, period, frame, and run ID manifest. It is
recorded, not chosen after results.

Trend relative to baseline:

- `increasing` when the entire change interval is above zero;
- `decreasing` when the entire change interval is below zero;
- `stable` when the interval includes zero;
- `insufficient` when suppressed.

This is descriptive statistical direction, not causal evidence.

### Suppression

Suppress on any of:

- fewer than 500 logical documents;
- fewer than 50 resolved employers;
- fewer than 5 occupation groups;
- fewer than 2 source families;
- effective sample below the approved threshold;
- employer resolution below 0.80;
- matched baseline weight below 0.80;
- incomplete baseline, source outage, rights restriction, benchmark regression,
  or lineage failure;
- confidence required inputs unavailable under the approved ES-001 policy.

## Implementation tasks

1. Freeze approved baseline and weighting registry.
2. Implement analytical cell builder and eligibility report.
3. Implement employer means and composition standardization.
4. Implement components, baseline, absolute and relative changes.
5. Implement deterministic cluster bootstrap and interval diagnostics.
6. Integrate ES-001 warnings, confidence inputs, suppression, and validation.
7. Implement all required sensitivities and difference report.
8. Implement score-run idempotency, result tables, manifests, and checksums.
9. Backfill synthetic, one-month, baseline, and current shadow windows.
10. Run benchmark and external-event validation.
11. Produce public-safe methods and release packet.
12. Hand approved released aggregates to ES-010.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Severity map, employer means, cell weights, matched weight, baseline, change, trend, suppression |
| Property | Permutation invariance, duplicate observation invariance, stronger-level monotonicity, finite outputs |
| Synthetic | All-none=0, all-enforced=100, equal mixes, missing cells, unresolved employers, source outage |
| Statistical | Bootstrap determinism and 90% empirical coverage target |
| Sensitivity | Source, occupation, employer, and document weighting shifts |
| Integration | Corpus and extractor manifests to validated score output and release |
| Regression | Frozen benchmark and prior scorer version |
| Performance | One monthly frame with one million documents completes in under 2 hours on the approved batch host |

## Operational design

- Monthly jobs start only after corpus closure and extractor completion.
- Quarterly jobs aggregate released monthly cells; they do not reclassify text.
- Idempotency key includes score ID, frame, period, corpus, extractor, baseline,
  and scorer versions.
- A rerun with the same key must produce the same manifest root.
- Metrics: run duration, cells, matched weight, unresolved rate, effective
  sample, score, components, interval width, warnings, suppression, and
  sensitivity deltas.
- Alerts: run failure, score change over 15 points without a reviewed event,
  sensitivity delta over 10 points, matched weight below 0.85, interval width
  over 20 points, or component distribution drift.
- Failed primary or sensitivity jobs block the period release.

## Security, privacy, rights, and compliance

Aggregation reads restricted predictions under the analysis role and writes
no-text results. Public-safe packets contain aggregate cell counts only when
they pass disclosure thresholds. Employer-level results remain private unless a
separate publication decision enables them.

## Release strategy

1. Synthetic formula fixtures.
2. One-month private shadow.
3. Baseline and twelve-month shadow backfill.
4. Compare sensitivities and external events.
5. Run protected benchmark and independent research review.
6. Freeze score, baseline, extractor, corpus, and contract versions in one
   release manifest.
7. Publish as `experimental`, then `validated` after all G3 evidence.
8. Public production requires ES-010/ES-011 and G5.
9. Roll back by reactivating the prior complete release; never mix component or
   baseline versions.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| One large employer dominates postings | Employer versus document sensitivity | Keep employer-balanced primary | Review fixed-panel and corpus |
| Baseline cells disappear | Matched-weight check | Suppress | Broaden approved reporting period or revise major version |
| Classifier drift changes level shares | Benchmark and canaries | Block release | Restore extractor or retrain under new version |
| Bootstrap too sparse | Effective sample and failed replicates | Suppress interval and score | Use broader approved frame |
| Source mix changes | Source sensitivity | Warn or suppress | Restore source or publish matched frame |
| Formula config differs from release | Manifest checksum | Fail run | Load approved immutable config |

## Definition of done

1. The exact IS-003 version in `Approved intent reference`, this exact
   execution-spec version, baseline, and weights are approved.
2. Formula and all components are documented and versioned.
3. Synthetic monotonicity, confounder, interval, and suppression tests pass.
4. Required benchmark thresholds and sensitivity tolerances pass.
5. Baseline and current shadow backfills complete with reproducible manifests.
6. No-text methods, benchmark, and release packet pass independent review.
7. Metrics, alerts, rollback, and period-release controls are active.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Final baseline dates | Research lead | G1 |
| Ordinal severity weights | Research lead | G2 |
| Baseline cell dimensions and minimums | Research lead | G2 |
| Effective-sample threshold | Applied science lead | G2 |
| Sensitivity warning and suppression tolerances | Research lead | G3 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval for this exact
execution version and the exact approved intent version.
