# IS-003: Employer AI Compulsion Scorer

| Field | Value |
| --- | --- |
| Status | Proposed |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S7 |
| Work package | WP4.1 |
| Gates | G0, G1, G2, G3 |
| Approval prerequisites | IS-001, IS-002 |

## Intent statement

Give researchers and labor-market analysts a transparent longitudinal measure of
how strongly observed employer language makes AI-tool use optional, encouraged,
expected, required, monitored, or enforced, without inferring employee beliefs,
actual behavior, or organizational intent beyond the text.

## Problem and evidence

Employer language about AI use can range from optional access to explicit
requirements, monitoring, performance conditions, or economic consequences.
Counting the word "AI" cannot distinguish these mechanisms and is easily
confounded by role descriptions, product context, equal-opportunity language,
or general statements about technology.

No governed S7 scorer exists in the current public model package or private
gateway. The existing Toslop detector measures AI-likeness in writing and must
not be reused as a mandate classifier. S7 therefore needs its own construct,
rubric, benchmark, formula, and release evidence.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Determine whether observed employer pressure language is changing and which mechanisms drive it |
| Labor-market analyst | Compare approved occupations, industries, jurisdictions, and employer cohorts over time |
| Applied science lead | Diagnose extraction errors, drift, and component behavior |
| Governance reviewer | Confirm that outputs describe public employer language without worker diagnosis or accusation |
| Product owner | Decide whether S7 has enough evidence for experimental or validated release |

## Scope

S7 classifies eligible language into a mutually exclusive primary level plus
independent mechanism flags.

Primary levels:

| Level | Meaning |
| --- | --- |
| `none` | No eligible employer AI-use direction is present |
| `optional` | AI use is permitted or offered without stated expectation |
| `encouraged` | AI use is recommended or positively incentivized |
| `expected` | AI use is presented as a normal competency or performance expectation |
| `required` | AI use or AI-tool proficiency is an explicit condition or duty |
| `monitored_or_enforced` | Use is tracked, audited, tied to evaluation, access, discipline, compensation, or continued work |

Independent flags include:

- monitoring or audit;
- performance evaluation;
- compensation or promotion consequence;
- discipline or continued-employment consequence;
- mandatory training or certification;
- tool, vendor, or workflow specificity;
- explicit opt-out or accommodation;
- negation, quotation, historical report, or third-party attribution.

Supported analytical levels are employer, employer cohort, occupation, industry,
jurisdiction, source family, and period, subject to coverage and publication
rules. The MVP releases monthly and quarterly descriptive estimates. Exposure
associations or causal studies require separate reviewed analytical intents.

## Explicit exclusions

S7 does not:

- measure whether employees actually use AI tools;
- infer employee agreement, cognition, wellbeing, productivity, job security, or
  coercion experienced by an individual;
- determine whether a policy is legal, ethical, effective, or enforced in
  practice;
- count product-building requirements, customer AI features, or general AI
  market discussion as employee-use compulsion;
- score non-public employee handbooks, applicant records, private messages, or
  monitoring telemetry;
- rank or accuse a named employer in public without an approved entity-level
  publication policy and sufficient evidence;
- use an LLM's unbenchmarked judgment as the production label;
- combine S7 with other observatory constructs into a public composite;
- claim LLM causation from temporal movement.

## Success measures

1. A public label rubric defines every primary level, independent mechanism,
   positive example pattern, hard negative, ambiguity, and adjudication rule.
2. The frozen adjudicated benchmark contains at least 1,500 eligible passages,
   at least 200 examples from each non-`none` primary level where source
   availability permits, and documented source, occupation, industry, and time
   diversity.
3. At least two trained annotators label every benchmark item; weighted Cohen
   kappa is at least 0.75 before adjudication.
4. Primary-level macro F1 is at least 0.80 on the untouched final benchmark.
5. `required` precision is at least 0.90; `monitored_or_enforced` precision is
   at least 0.90 and recall at least 0.75.
6. Hard-negative precision is at least 0.95 for product requirements, AI-company
   descriptions, applicant personal use, negation, quotations, and
   equal-opportunity language.
7. Every aggregate exposes level shares, mechanism prevalence, raw weighted
   pressure, baseline, change, sample and effective-sample size, coverage,
   interval, confidence, warnings, and versions.
8. Synthetic tests prove monotonicity: replacing an eligible passage with a
   strictly stronger primary level cannot lower the raw pressure component when
   all else is fixed.
9. Repeated postings and repeated employers do not dominate the aggregate;
   document, employer, and source weighting are visible and sensitivity-tested.
10. A source-mix, occupation-mix, or employer-mix change beyond the approved
    threshold creates a warning and a matched-composition sensitivity series.
11. A score is suppressed when corpus, benchmark, lineage, sample, or freshness
    gates fail.
12. Public copy review finds zero claims about employee mental state, actual
    compliance, employer intent beyond the language, or causal LLM impact.

## Score semantics

A higher S7 score means that the eligible observed employer language in the
stated frame is more strongly weighted toward requirements, monitoring,
enforcement, or economic consequences. A lower score means language is absent,
optional, or less directive.

The score is not:

- the percentage of employees compelled to use AI;
- the probability that an employer enforces a policy;
- a legal or ethical judgment;
- evidence that a worker used AI;
- evidence that LLM adoption caused a labor outcome.

The top-level value must remain interpretable in absolute component terms. A
baseline-normalized view may be added, but it cannot replace the raw level and
mechanism shares.

## Data boundaries

S7 uses only records admitted under IS-002. Public evidence contains aggregate
counts, no-text benchmark metadata, rubric-authored examples, metrics,
checksums, and scorer artifacts permitted for release. Restricted source text,
personal data, credentials, and source-specific private labels stay in the
private boundary.

Record-level labels are accessible only to approved research and adjudication
roles. Entity-level public output is disabled by default.

## Constraints

- Production inference must be deterministic for a pinned scorer version.
- Conventional rules or ML are preferred. Any LLM-assisted candidate must be
  benchmarked against the same final set, pinned, cached, and replaceable by a
  non-LLM degraded mode.
- The primary label and mechanism flags must expose evidence spans internally
  for adjudication, but restricted source spans must not enter public artifacts.
- Monthly recalculation must be idempotent.
- The existing Toslop AI-likeness routes and model artifacts remain unchanged.

## Dependencies

### Approval prerequisites

- [IS-001](IS-001-score-ontology-and-reporting-semantics.md)
- [IS-002](IS-002-public-job-posting-data-foundation.md)
- Approved baseline, weighting, minimum-sample, and entity-publication
  decisions

### Coordination interfaces

- [IS-006](IS-006-mvp-validation-benchmark.md) implements the benchmark
  obligations frozen here and is approved afterward; it does not block this
  intent's approval.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Final primary-level weights and whether `none` participates | Research lead | G2, before formula freeze |
| Multi-label conflict rule for passages with several mechanisms | Research lead | G2 |
| Document, employer, and source weighting policy | Research lead and applied science lead | G2 |
| Public employer-level output | Governance reviewer and program owner | G5 |
| Multilingual scope | Research lead | Out of MVP unless separately approved |
| Treatment of AI-proficiency requirements for AI-specialist occupations | Research lead | G2 |
| Baseline period and matched-composition controls | Research lead | G1 |
| Benchmark source redistribution restrictions | Governance reviewer | G2 |

## Acceptance scenarios

1. **Given** a posting merely describes building an AI product, **when** S7
   classifies it, **then** it receives `none` unless separate language directs
   the worker to use an AI tool.
2. **Given** a policy says AI tools are available but optional, **when** it is
   classified, **then** the primary level is `optional` and no enforcement flag
   is set.
3. **Given** an eligible statement ties measured AI-tool use to performance
   evaluation, **when** it is classified, **then** the primary level is
   `monitored_or_enforced` and the relevant mechanism flags are set.
4. **Given** a monthly source outage removes a major posting feed, **when** the
   aggregate is calculated, **then** the normal release is suppressed or warned
   and a matched-source sensitivity result is available.
5. **Given** a high employer-level score with too few unique postings, **when**
   the public API is requested, **then** the entity result is suppressed and no
   employer accusation is emitted.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval and G1-G2 inputs
are available.
