# ES-008: Language Homogenization Aggregation

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-005 v0.1.0, approval pending |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1, G2, G3, G4, G5 |
| Start prerequisites | ES-001, ES-006, and ES-007 candidate outputs |
| Stage interfaces | ES-009 protected-final pass; released scores to ES-010 |

## Implementation authorization

Implementation may begin on synthetic features after IS-005 approval. Real
backfills require approved ES-006 and ES-007 releases. Formula, baseline,
component weight, concentration cap, and interval decisions must be approved
before protected final evaluation.

## Outcome

Calculate reproducible S3 component dispersions and a baseline-centered
homogenization score from matched professional-writing cells, with
composition standardization, cluster-aware uncertainty, sensitivity analyses,
suppression, lineage, and release evidence.

## Current state

No S3 aggregation, baseline distribution, robust scaling artifact, component
weights, score tables, or release series exists. The current AI-likeness score
is a separate construct and is not an input.

## Architecture and boundaries

```text
S3 feature release + matched-frame index
                 |
                 v
per-cell component dispersion
                 |
                 v
baseline robust center and scale
                 |
                 v
cell convergence z-scores
                 |
                 v
baseline-composition standardization
                 |
                 v
component scores + top-level score + bootstrap
                 |
                 v
sensitivities + suppression + validated release
```

Proposed modules:

- `scorers/s3/dispersion.py`
- `scorers/s3/baselines.py`
- `scorers/s3/aggregate.py`
- `scorers/s3/uncertainty.py`
- `scorers/s3/sensitivity.py`
- `scorers/s3/release.py`

Use the generic score-run, result, sensitivity, and release-table contract
defined by ES-001. ES-005 and ES-008 may deliver the shared private migration in
either order, but neither scorer may create a construct-specific incompatible
variant.

## Data contracts

### Baseline scaling artifact

For every approved control cell `c` and component `k`, store:

- baseline ID, period, corpus, feature, control, and scorer versions;
- eligible baseline months and document counts;
- baseline cell weight `pi_c`;
- dispersion center `m_kc`;
- robust scale `s_kc`;
- scale method and fallback;
- concentration and coverage diagnostics;
- artifact checksum and approval state.

### Private cell result

```json
{
  "schema_version": "observatory.s3_cell_result.v1",
  "cell_id": "cell:...",
  "period_id": "2026-07",
  "document_count": 820,
  "effective_sample_size": 143.4,
  "entity_count": 112,
  "publisher_count": 85,
  "baseline_weight": 0.018,
  "dispersion": {
    "lexical": 0.221,
    "syntactic": 0.184,
    "rhetorical": 0.317,
    "semantic": 0.126
  },
  "convergence_z": {
    "lexical": 0.42,
    "syntactic": 0.11,
    "rhetorical": -0.08,
    "semantic": 0.55
  },
  "status": "eligible",
  "warnings": [],
  "versions": {
    "corpus": "1.0.0",
    "features": "1.0.0",
    "baseline": "1.0.0",
    "scorer": "1.0.0"
  }
}
```

## Algorithm design

### Contribution caps

Before dispersion:

1. select one contribution per logical duplicate or syndication cluster;
2. cap each entity at the approved share of a cell;
3. cap each publisher and owner at the approved share;
4. retain deterministic weighted sampling when a cap is exceeded;
5. record original and retained counts and weights.

The proposed default cap is 5% per entity and 10% per publisher owner. These
values remain blocked pending G2 approval.

### Component dispersion

For document vectors `x_i` with normalized document weights `w_i`:

**Lexical**

```text
p_bar = weighted mean of document lemma distributions
D_lex = sum_i w_i * JSD(p_i, p_bar)
```

Use base-2 Jensen-Shannon divergence and the ES-007 smoothing constant.

**Syntactic**

```text
q_bar = weighted mean of normalized syntactic distributions
D_syn = sum_i w_i * JSD(q_i, q_bar)
```

Features that are not probability distributions are excluded from this vector
or normalized in the frozen feature definition.

**Rhetorical**

Baseline-standardize each rhetorical feature, L2-normalize the document vector,
then:

```text
r_bar = normalized weighted centroid
D_rhet = sum_i w_i * cosine_distance(r_i, r_bar)
```

**Semantic**

Semantic vectors are already L2-normalized:

```text
s_bar = normalized weighted centroid
D_sem = sum_i w_i * cosine_distance(s_i, s_bar)
```

Lower dispersion means more within-cell convergence for every component.

### Robust baseline transformation

For each cell and component, use monthly baseline dispersions:

```text
m_kc = median(D_kc,baseline-month)
s_kc = 1.4826 * MAD(D_kc,baseline-month)
z_kct = clip((m_kc - D_kct) / s_kc, -5, 5)
```

Scale fallback order when MAD is zero:

1. `IQR / 1.349`;
2. sample standard deviation;
3. mark component-cell unavailable when all are zero or fewer than 12 eligible
   baseline months remain.

Positive `z` means more convergence than the cell's baseline center.

### Cell standardization and component scores

Let `pi_c` be the approved baseline weight for cell `c`.

```text
matched_weight_t = sum(pi_c for eligible cells c in t)
Z_kt = sum(pi_c * z_kct) / matched_weight_t
component_score_kt = clip(50 + 10 * Z_kt, 0, 100)
```

Suppress when matched weight is below `0.80`.

### Top-level score

The proposed MVP uses equal frozen weights:

```text
Z_t = 0.25*Z_lex,t + 0.25*Z_syn,t + 0.25*Z_rhet,t + 0.25*Z_sem,t
S3_t = clip(50 + 10 * Z_t, 0, 100)
```

The un-clipped analytical center is 50. A one-baseline-scale convergence
movement across the weighted components maps to 60; a one-scale dispersion
movement maps to 40. Because cell eligibility, robust cell centers, period
weights, and clipping can make the empirical approved-frame baseline differ
from 50, 50 is not asserted to be the observed baseline value. Clipping is
visible in components and warnings.

Any component weight or transformation change is a major scorer version.

### Change, uncertainty, and trend

Compute `B_S3` by running the exact frozen scoring pipeline over every eligible
approved baseline period and taking the approved period-weighted mean of the
resulting top-level scores. Store the baseline-period scores, weights, interval,
and checksum in the baseline release. `B_S3`, not the analytical center, is the
reported `baseline.value`.

```text
absolute_change_t = S3_t - B_S3
relative_change_t = absolute_change_t / B_S3
```

When `B_S3` is zero, relative change is `null` and the result carries the
`RELATIVE_CHANGE_UNDEFINED` warning.

Use 2,000 deterministic cluster-bootstrap replicates:

1. resample entities within cells;
2. retain all selected logical documents for a sampled entity;
3. reapply publisher and entity caps;
4. recompute dispersions, cell z-scores, components, and top-level score.

Report 5th and 95th percentiles as the 90% interval. Trend is increasing when
the entire change interval is above zero, decreasing when below zero, stable
when it includes zero, and insufficient when suppressed.

### Required sensitivities

- equal versus approved component weights;
- mean versus median within-cell dispersion;
- centroid versus deterministic sampled pairwise dispersion;
- fixed-entity and fixed-publisher panels;
- equal-source-family weighting;
- leave-one-genre, topic, event cluster, source family, and publisher owner out;
- alternate approved semantic representation;
- alternate baseline window;
- no event control, no template control, and no dedup control as benchmark-only
  negative ablations.

### Suppression

Suppress on any IS-004 or IS-005 minimum failure, plus:

- any required component unavailable;
- fewer than 500 logical documents, 50 entities or publishers, or 2 source
  families in a monthly frame;
- effective sample below the approved threshold;
- matched baseline weight below 0.80;
- fewer than 12 eligible baseline months for any required cell-component;
- concentration above the approved cap without a valid capped result;
- source, corpus, feature, benchmark, rights, lineage, or artifact failure;
- required sensitivity job failure.

## Implementation tasks

1. Approve baseline, cells, caps, formula, weights, and sensitivity tolerances.
2. Implement contribution selection and caps.
3. Implement four component dispersions and golden numerical fixtures.
4. Implement baseline center, scale fallbacks, and cell artifacts.
5. Implement composition standardization and component/top-level scores.
6. Implement deterministic cluster bootstrap and interval diagnostics.
7. Implement all sensitivities and benchmark-only ablations.
8. Integrate ES-001 confidence inputs, warnings, suppression, and validation.
9. Implement score-run, result, lineage, and release manifests.
10. Backfill synthetic, baseline, and current shadow periods.
11. Run external-event, null, and confounder validation.
12. Produce public-safe methods and release packet.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | JSD, cosine dispersion, caps, robust scale, fallbacks, z-score, clipping, weights, change, trend |
| Numerical | Golden vectors with exact expected dispersion and score tolerances |
| Property | Permutation invariance, duplicate invariance, monotonic convergence, finite bounded outputs |
| Confounder | Topic-only, genre-only, event-only, source-only, template-only, duplicate-only shifts within IS-005 tolerance |
| Statistical | Bootstrap determinism and empirical 90% interval coverage |
| Sensitivity | Required variants and leave-one-group-out differences |
| Integration | Feature release to cell artifact to validated score and release |
| Performance | One million documents and 2,000 replicates complete within 8 hours on the approved batch host |
| Regression | Prior scorer, baseline, and feature releases remain reproducible |

## Operational design

- Monthly runs begin after corpus and feature release closure.
- Idempotency key includes frame, period, corpus, features, baseline, formula,
  and scorer versions.
- Baseline artifacts are immutable and never refit from current data.
- Metrics: eligible cells, matched weight, concentrations, dispersions, z-scores,
  component and top score, interval width, clipped-cell count, sensitivities,
  warnings, and suppression.
- Alerts: score movement over 15 points, component disagreement over 25 points,
  sensitivity delta over 10 points, matched weight below 0.85, clipped cells
  over 5%, or interval width over 20 points.
- Any missing primary or required sensitivity result blocks period release.

## Security, privacy, rights, and compliance

Aggregation reads restricted vectors and writes no-text cell and score results.
Small cells are not exported publicly. Public evidence includes aggregate
dispersions only where disclosure thresholds pass. Feature and score releases
inherit source deletion and retirement lineage.

## Release strategy

1. Golden numerical and synthetic confounder fixtures.
2. One-month private shadow.
3. Baseline artifact fit and protected freeze.
4. Twelve-month shadow and sensitivity review.
5. Full approved backfill.
6. Protected final benchmark and independent research review.
7. Freeze release as `experimental`, then `validated` after G3.
8. Public production requires ES-010/ES-011 and G5.
9. Roll back by reactivating the prior complete S3 release; do not splice major
   versions.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Baseline scale is zero | Scale fallback | Use approved fallback or exclude cell | Broaden approved baseline or cell |
| Topic/event cells become sparse | Matched-weight and sample checks | Suppress | Report quarterly or broader frame |
| One publisher drives convergence | Caps and leave-one-out | Warn or suppress | Correct frame or cap policy |
| Semantic artifact changes | Checksum and dimension | Block run | Restore pinned artifact |
| Components cancel each other | Component spread | Show disagreement warning | Do not alter weights after observation |
| Pairwise sensitivity disagrees | Sensitivity delta | Block validation if over tolerance | Investigate centroid assumptions |

## Definition of done

1. The exact IS-005 version in `Approved intent reference`, this exact
   execution-spec version, baseline, caps, formula, and weights are approved.
2. Four component dispersions and score transformation are versioned.
3. Numerical, monotonicity, confounder, interval, and sensitivity tests pass.
4. Baseline and shadow backfills reproduce from immutable manifests.
5. Required benchmark thresholds pass with no protected-test tuning.
6. Public-safe methods and release packet expose components, disagreement,
   limits, and no causal or authorship claim.
7. Metrics, alerts, rollback, and deletion propagation are active.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Historical baseline dates | Research lead | G1 |
| Cell dimensions and baseline weights | Research lead | G2 |
| Entity and publisher caps | Research lead | G2 |
| Equal component weights | Research lead | G2 |
| Effective-sample and sensitivity thresholds | Applied science lead | G3 |

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
