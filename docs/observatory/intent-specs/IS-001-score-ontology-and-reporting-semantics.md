# IS-001: Score Ontology and Reporting Semantics

| Field | Value |
| --- | --- |
| Status | Proposed |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Work packages | WP1.1, WP1.2, WP1.3, WP1.4 |
| Gates | G0 |
| Approval prerequisites | None |

## Intent statement

Give researchers, implementers, and public readers one governed definition of
each observatory score, including direction, evidence class, uncertainty,
warnings, and prohibited interpretations, so every later scorer and interface
communicates the same bounded claim.

## Problem and evidence

The program proposes eight related but non-interchangeable constructs. Without a
shared ontology, implementations can reverse score direction, hide low
coverage, treat confidence as causal certainty, or collapse distinct mechanisms
into a single headline number.

The current Toslop product already distinguishes an AI-likeness measurement
from authorship proof in
`docs/toslop-ai-likeness-measurement-contract.md` and the current Spec Kit
constitution. The observatory needs the same claim discipline while explicitly
remaining separate from the existing detector.

This intent is complete when an unfamiliar reader can answer, for every result:

1. What public phenomenon was measured?
2. What does a higher or lower value mean?
3. Which records, periods, and transformations support it?
4. How uncertain or incomplete is the estimate?
5. Is the finding descriptive, associative, or causal?
6. Which interpretations are prohibited?

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Approve constructs, baselines, evidence classes, and public claims |
| Applied science lead | Implement formulas and uncertainty without changing score meaning |
| Data lead | Determine whether coverage and lineage are sufficient to calculate a result |
| Product and UX lead | Present values, components, comparisons, warnings, and methods consistently |
| Governance reviewer | Block diagnostic, punitive, privacy-invasive, or causal-overreach uses |
| Public researcher | Decide whether a result is suitable for comparison or secondary analysis |

## Scope

This intent includes:

- canonical IDs, names, definitions, directionality, units, and version states
  for S1-S8;
- the analytical key `entity x topic x period x source`;
- historical baseline, current-period, absolute-change, and relative-change
  semantics;
- component, coverage, effective-sample-size, confidence, uncertainty,
  suppression, warning, lineage, and scorer-version fields;
- evidence classes `descriptive`, `exposure_association`, and
  `causal_estimate`;
- lifecycle states `experimental`, `validated`, `production`, and `retired`;
- a machine-readable output contract and warning-code registry;
- public wording rules for dashboards, APIs, exports, and reports;
- scorer release and backward-compatibility rules.

The ontology covers all eight scores even though the MVP implements only S7 and
S3.

## Explicit exclusions

This intent does not authorize:

- a single cross-construct public composite score;
- an individual cognitive, psychological, political, or clinical diagnosis;
- a "brainwashing", "mind-control", or individual susceptibility score;
- an AI-authorship verdict for a document, writer, employer, or publisher;
- a causal claim based only on temporal coincidence, model-language
  similarity, or before-and-after movement;
- a value judgment that every high score is bad or every low score is good;
- silent imputation of missing or suppressed scores;
- using confidence as the probability that an LLM caused the observed change;
- implementation of collectors, feature pipelines, scorers, studies, APIs, or
  dashboards.

## Canonical score semantics

| ID | Score | Higher value means | Lower value means |
| --- | --- | --- | --- |
| S1 | External Exploration | Broader observed use of external sources and public knowledge systems within the stated frame | Narrower observed exploration or lower use within the stated frame |
| S2 | Source Concentration | References are concentrated among fewer domains, publishers, or owners | References are more dispersed |
| S3 | Language Homogenization | Matched writing is more convergent across the approved lexical, syntactic, rhetorical, and semantic components | Matched writing is more dispersed |
| S4 | Perspective Diversity | More distinct validated frames, arguments, causes, or proposed actions are visible | Fewer distinct validated perspectives are visible |
| S5 | Model-Language Diffusion | Approved model-associated patterns are more prevalent in public writing | Approved patterns are less prevalent |
| S6 | Human Knowledge Contribution | More eligible public human Q&A, explanation, maintenance, or knowledge contribution is observed | Less eligible public contribution is observed |
| S7 | Employer AI Compulsion | Employer language is more mandatory, monitored, enforced, or economically coercive | Employer language is more optional or absent |
| S8 | Novel Information Density | More unique supported claims, perspectives, and sources appear per unit of content | Content volume contains less new supported information |

A score expresses only its named construct. It does not determine social value,
cause, intent, welfare, or an individual's condition.

## Evidence classes

| Class | Required meaning | Prohibited shorthand |
| --- | --- | --- |
| `descriptive` | A documented measurement changed in the observed sample | "LLMs caused the change" |
| `exposure_association` | A predeclared exposure measure is associated with the outcome after stated controls | "The effect of LLMs" unless a causal design supports it |
| `causal_estimate` | A separately reviewed design estimates an intervention effect under explicit assumptions | "Proven cause" or generalization beyond the study population |

An API response and chart series must carry exactly one evidence class. A
descriptive series must not inherit a causal label from accompanying prose.

## Confidence, uncertainty, and coverage

- `confidence` is a bounded evidence-sufficiency summary. It is not a posterior
  probability that the construct or causal story is true.
- `uncertainty_interval` describes statistical uncertainty in a named value and
  must identify its method and level.
- `coverage` describes observed source, time, entity, topic, and field coverage
  relative to the approved frame.
- `sample_size` counts eligible observations. `effective_sample_size` accounts
  for clustering, repeated entities, or weighting when applicable.
- `suppression` is a result state, not a score of zero.
- Confidence must decrease or a result must be suppressed when required
  coverage, benchmark, freshness, lineage, or sample gates fail.

The final confidence formula and minimum-sample defaults require a separate
approved decision record. No scorer may invent its own meaning for the shared
field.

## Required warning classes

The registry must include at least:

- `EXPERIMENTAL`
- `LOW_SAMPLE_SIZE`
- `LOW_EFFECTIVE_SAMPLE_SIZE`
- `BASELINE_INCOMPLETE`
- `SOURCE_OUTAGE`
- `SOURCE_MIX_SHIFT`
- `COVERAGE_SHIFT`
- `TOPIC_OR_GENRE_CONFOUNDER`
- `BENCHMARK_REGRESSION`
- `EXTRACTOR_DRIFT`
- `LINEAGE_INCOMPLETE`
- `LICENSE_RESTRICTED`
- `CONFIDENCE_UNAVAILABLE`
- `SUPPRESSED`

Warnings are additive and machine-readable. Human-readable explanations must be
generated from the versioned registry, not improvised per interface.

## Success measures

1. All eight score entries have a unique ID, construct definition, direction,
   unit, components, supported analytical levels, high/low semantics, and
   prohibited interpretations.
2. One versioned JSON Schema validates 100% of approved score fixtures and
   rejects fixtures missing score identity, period, evidence class, sample,
   coverage, confidence, components, lineage, warnings, or versions.
3. One warning registry produces the same code and explanation across batch
   outputs, API responses, dashboard views, and exports.
4. Every score fixture distinguishes baseline value, current value, absolute
   change, and relative change without using `0` for missing data.
5. Every evidence fixture is classified as descriptive, exposure association,
   or causal estimate, with no ambiguous default.
6. Suppression tests cover low sample size, incomplete baseline, source outage,
   benchmark failure, missing lineage, and rights restriction.
7. A plain-language interpretation review finds no individual diagnosis,
   authorship proof, single composite, or unsupported causal wording in the
   canonical examples.
8. Scorer version changes that alter meaning, formula, baseline, component
   weights, or supported frame require a major version and block automatic
   time-series comparison.
9. Additive output fields use a minor version; editorial or documentation-only
   corrections use a patch version.
10. The program owner, research lead, data lead, applied science lead, product
    lead, and governance reviewer record approval of version 1.0.0 before G0
    closes.

## Data boundaries

The ontology and examples are public-safe and contain no raw source text,
personal data, credentials, private storage paths, or protected benchmark
labels. Lineage identifiers may be public only when the corresponding source
decision record permits publication. Restricted source names may be represented
by stable public aliases.

Public results must minimize record-level disclosure. Entity-level scores
require a separately approved publication policy; the shared contract does not
make every analytical level public by default.

## Constraints

- All field names and enum values are stable ASCII identifiers.
- Scores are finite numbers in `[0, 100]` when present.
- Missing, not-applicable, and suppressed values remain distinct states.
- Formulas and versions must be reproducible without a live LLM call.
- Public methodology must be understandable without access to private raw text.
- Existing Toslop AI-likeness contracts and routes must not change under this
  intent.

## Dependencies

### Approval prerequisites

- [Parent project plan](../project-plan.md)
- Toslop Model Replication Constitution
- Approved G0
  [decision records](../decision-records/README.md) for baseline,
  confidence, minimum-sample, normalization, and publication policy

### Coordination interfaces

- IS-002 through IS-007 consume this ontology after approval; they are
  downstream consumers and do not block IS-001 approval.
- Later privacy, retention, source, and causal-review decisions must conform to
  this intent and record their narrower scope.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Exact historical and transition baseline registry for each scorer | Research lead | G0 |
| Shared confidence formula and calibration target | Applied science lead | G0 |
| Default minimum sample and effective-sample thresholds | Research lead and data lead | G0 |
| Public entity-level publication policy | Governance reviewer and program owner | G0 |
| Stable topic taxonomy ownership and versioning | Research lead | G1 |
| Whether score normalization is baseline-centered or absolute per construct | Research lead | G0 |
| Public methodology and benchmark URL structure | Product lead | G5 |

## Acceptance scenarios

1. **Given** an S7 result with a value of 80, **when** a public reader opens its
   explanation, **then** the product describes strong observed employer
   compulsion language in the stated sample and does not infer employee mental
   state, actual compliance, or causal LLM harm.
2. **Given** a source outage removes half of a monthly S3 frame, **when** the
   batch calculates the period, **then** the result is suppressed or explicitly
   warned according to the registry rather than shown as an ordinary decline.
3. **Given** a descriptive S6 trend and a separate causal study, **when** both
   appear in the API, **then** each retains its own evidence class and the
   descriptive series is not relabeled causal.
4. **Given** an implementation attempts to emit one aggregate across S1-S8,
   **when** contract validation runs, **then** the public composite is rejected.
5. **Given** a scorer formula changes component weights, **when** a release is
   prepared, **then** a new major scorer version and comparison warning are
   required.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval.
