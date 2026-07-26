# IS-005: Language Homogenization Scorer

| Field | Value |
| --- | --- |
| Status | Proposed |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S3 |
| Work package | WP4.2 |
| Gates | G0, G1, G2, G3 |
| Approval prerequisites | IS-001, IS-004 |

## Intent statement

Give researchers a transparent longitudinal measure of within-context language
convergence across lexical, syntactic, rhetorical, and semantic components,
while controlling for topic, genre, event, source, entity, duplication, and
composition changes and making no document-level AI-authorship claim.

## Problem and evidence

Language similarity has many ordinary causes: shared subject matter, templates,
syndication, quotation, style guides, legal requirements, genre conventions,
and major events. A simple embedding similarity or vocabulary-diversity trend
would confound those causes and could be misrepresented as evidence of LLM
influence.

The current Toslop AI-likeness model is optimized for a different construct and
may not be used as S3. No governed longitudinal homogenization scorer, matched
professional-writing corpus, component benchmark, or baseline registry exists
in the current project.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Determine whether matched professional writing is becoming more or less convergent and which components move |
| Applied science lead | Select, validate, and version component features and controls |
| Data lead | Determine whether each stratum meets composition and coverage requirements |
| Product owner | Decide whether an experimental or validated S3 release is warranted |
| Public researcher | Inspect component trends, methods, uncertainty, and alternative specifications |

## Scope

S3 contains four separately reported components:

| Component | Construct |
| --- | --- |
| Lexical convergence | Reduced dispersion in word, lemma, phrase, and approved lexical-distribution features within matched strata |
| Syntactic convergence | Reduced dispersion in part-of-speech, dependency, sentence-shape, and approved construction distributions |
| Rhetorical convergence | Reduced dispersion in approved discourse, transition, stance, hedging, list, and paragraph-organization features |
| Semantic convergence | Reduced dispersion in topic-controlled semantic representations after duplicate, quote, and event controls |

The primary analytical unit is a matched
`genre x topic x event-control x source-family x period` stratum. Entity and
publisher clustering are accounted for in weighting and uncertainty. The MVP
supports monthly feature calculation and quarterly public reporting when
monthly evidence is insufficient.

Every result includes:

- each raw component dispersion and signed baseline change;
- top-level score and frozen component weights;
- baseline and current frames;
- matched and unmatched coverage;
- document, entity, publisher, source, topic, and event counts;
- sample and effective-sample size;
- uncertainty interval, confidence, suppression, and warnings;
- feature, control, corpus, embedding, and scorer versions;
- descriptive evidence class unless a separate study says otherwise.

## Explicit exclusions

S3 does not:

- determine whether a document or author used an LLM;
- estimate the percentage of AI-generated text;
- label linguistic diversity, conformity, clarity, quality, originality, truth,
  or social value;
- compare unmatched genres or topics as if they were equivalent;
- treat duplicate, syndicated, quoted, templated, or boilerplate text as
  independent writing;
- use publisher identity, source identity, period, or model metadata as a
  shortcut feature for convergence;
- hide component disagreement behind the top-level score;
- attribute a descriptive trend to LLM adoption without a separate reviewed
  exposure or causal design;
- collapse S3 with S2, S4, S5, or S8.

## Success measures

1. Every component has a versioned feature definition, unit, preprocessing
   rule, dispersion statistic, baseline transformation, weighting rule, and
   failure behavior.
2. Re-running a pinned corpus and scorer version produces byte-identical
   component aggregates and score outputs, excluding explicitly versioned
   timestamps.
3. Synthetic fixtures with progressively duplicated or standardized language
   move every targeted component monotonically toward greater convergence while
   unaffected components remain within their tolerance.
4. Topic-only, genre-only, event-only, source-only, and template-only synthetic
   shifts do not produce a released top-level homogenization change greater
   than 5 score points after the corresponding control is applied.
5. Removing duplicate, quote, and boilerplate controls from the same fixture
   produces a detectable benchmark regression, proving the controls are active.
6. A frozen human similarity-ranking benchmark reaches Spearman correlation of
   at least 0.70 for the combined lexical, syntactic, and rhetorical distance
   representation and at least 0.65 for the semantic representation.
7. Bootstrap or cluster-aware 90% uncertainty intervals attain empirical
   coverage between 0.85 and 0.95 on the approved synthetic and resampling
   suite.
8. Every released result reports all four components; a missing component
   suppresses the top-level score unless an approved degraded-mode version is
   explicitly requested.
9. Equal-weight, reliability-weighted, alternate-baseline, fixed-panel, and
   source-balanced sensitivity results are retained for release review.
10. No one source family, publisher, entity, topic, or event cluster contributes
    more than the approved maximum weight without a warning and sensitivity
    result.
11. A scorer release passes benchmark, source-mix, corpus-quality, embedding
    drift, and reproducibility gates before leaving `experimental`.
12. Public copy and fixture review contain zero AI-authorship verdicts or
    unsupported causal wording.

## Score semantics

A higher S3 value means approved within-context language features are more
convergent than their approved baseline after the stated controls. A lower value
means they are more dispersed. A value near the baseline center means no large
net movement under that scorer version.

The top-level score does not imply that all components moved together. The
dashboard and API must show component disagreement. A high score is not proof
of LLM mediation; a low score is not proof of unaffected human writing.

The intended scale is baseline-centered and bounded to `[0, 100]`, with a
documented baseline center and clipping rule. The final transformation and
component weights remain an approval-blocking research decision.

## Data boundaries

S3 uses only records admitted under IS-004. Raw and normalized text,
record-level vectors, evidence spans, and restricted source labels stay in the
private implementation boundary. Public artifacts contain no-text feature
definitions, source aliases, aggregate distributions, benchmark metrics,
checksums, model identifiers, and approved synthetic examples.

Embeddings and other learned artifacts must have recorded license, revision,
checksum, runtime requirements, and retirement policy.

## Constraints

- Deterministic features are preferred for lexical, syntactic, and rhetorical
  components.
- Any learned embedding or classifier is pinned, locally reproducible, and
  benchmarked. A provider-side model alias is not a valid version.
- A live LLM call is not required to calculate or reproduce S3.
- Feature extraction precedes aggregation; private document vectors are not
  exposed by the public API.
- Scoring must fit within approved batch cost and complete an incremental
  monthly window within 24 hours after corpus closure.
- Existing Toslop AI-likeness scoring remains independent and unchanged.

## Dependencies

### Approval prerequisites

- [IS-001](IS-001-score-ontology-and-reporting-semantics.md)
- [IS-004](IS-004-professional-writing-corpus.md)
- Approved baseline, component-weight, feature-model, matching, minimum-sample,
  and release decisions

### Coordination interfaces

- [IS-006](IS-006-mvp-validation-benchmark.md) implements the benchmark
  obligations frozen here and is approved afterward; it does not block this
  intent's approval.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Exact baseline center, robust scale, and clipping rule | Research lead | G2 |
| Equal versus reliability-derived component weights | Research lead | G2 |
| Semantic representation candidate and license | Applied science lead | G2 |
| Topic and event matching granularity | Research lead | G1 |
| Maximum entity, publisher, source, topic, and event weight | Research lead | G2 |
| Treatment of templated but substantively authored text | Research lead | G2 |
| Monthly versus quarterly public release by genre | Research lead and product owner | G3 |
| Whether a degraded three-component score is ever allowed | Program owner | G3 |

## Acceptance scenarios

1. **Given** a month contains duplicated copies of the same release, **when** S3
   runs, **then** the copies retain provenance but contribute one logical
   document to dispersion.
2. **Given** two periods cover different topics, **when** no valid matched frame
   exists, **then** the comparison is suppressed rather than interpreted as
   homogenization.
3. **Given** lexical convergence rises while semantic convergence falls,
   **when** the result is published, **then** both movements and their
   contribution to the top-level score are visible.
4. **Given** an embedding artifact changes, **when** a backfill is requested,
   **then** a new feature and scorer version is required and old and new series
   are not silently joined.
5. **Given** S3 rises after 2022, **when** the descriptive dashboard renders,
   **then** it says language convergence increased in the observed matched
   sample and does not say LLMs caused the increase.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval and G1-G2 inputs
are frozen.
