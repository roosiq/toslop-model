# IS-006: MVP Validation Benchmark

| Field | Value |
| --- | --- |
| Status | Proposed |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Applied science lead |
| Decision owner | Research lead |
| Work packages | WP8.1, WP8.2, WP8.3, WP8.5 |
| Gates | G0, G2, G3 |
| Approval prerequisites | IS-001, IS-003, IS-005 |

## Intent statement

Give scorer owners and reviewers a frozen, public-safe validation system that
can reject incorrect S7 and S3 implementations before formula tuning, release,
or public claims.

## Problem and evidence

S7 labels involve judgment about employer language, while S3 must distinguish
real convergence from topic, genre, event, template, duplicate, and source
changes. Tuning formulas on an evolving or repeatedly inspected final benchmark
would overstate performance and make release evidence non-reproducible.

The existing Toslop model package has strong no-text, source-blind, split
isolation, and promotion-gate rules for AI-likeness challengers. The observatory
needs an analogous benchmark contract for longitudinal constructs, without
reusing authorship labels or pretending that classifier accuracy validates
causal interpretation.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Applied science lead | Select candidate extractors and formulas without contaminating final evaluation |
| Research lead | Decide whether construct, confounder, and interpretation evidence meet G2-G3 |
| Data lead | Validate deduplication, identity, topic, genre, and coverage components |
| Governance reviewer | Verify privacy, rights, no-text publication, and claims-policy tests |
| Release owner | Approve HOLD, REJECT, SHADOW, VALIDATED, or RELEASED disposition |

## Scope

The MVP benchmark has six lanes:

1. **Schema and contract fixtures** for valid, missing, suppressed, warned, and
   version-incompatible score outputs.
2. **Synthetic monotonicity fixtures** with known S7 pressure changes and S3
   component changes.
3. **Synthetic confounder fixtures** for source, topic, genre, event, template,
   duplicate, quote, entity, and period composition shifts.
4. **Human-labeled S7 benchmark** with double annotation and adjudication.
5. **Human-ranked S3 benchmark** for lexical, syntactic, rhetorical, and
   semantic similarity and matched-frame validity.
6. **External-event and negative-control suite** where known collection or
   composition changes should trigger warnings rather than substantive trend
   claims.

Each learned or rule-based component uses development, validation, and final
partitions. Final labels remain protected from formula, threshold, feature,
weight, and prompt selection.

## Explicit exclusions

The benchmark does not:

- prove that S7 or S3 captures every real-world consequence of LLM adoption;
- validate individual AI authorship, worker experience, employer intent,
  linguistic quality, or causal effect;
- permit final-test labels to guide feature or formula selection;
- permit aggregate final-test results to guide another candidate evaluated on
  the same final partition;
- publish restricted source text or adjudication notes;
- treat synthetic success as a substitute for human or external validation;
- allow benchmark examples to enter training or production source aggregates;
- collapse component metrics into one pass/fail number without required safety
  gates;
- authorize production release by itself.

## Success measures

1. Benchmark version 1.0.0 is frozen before S7 and S3 formula tuning and records
   schema, source aliases, rights state, label rubric, split policy, checksums,
   counts, and no-text hygiene.
2. Document and logical-duplicate groups have zero overlap across development,
   validation, and final partitions.
3. S7 has at least 1,500 final benchmark passages and meets the class-balance,
   agreement, precision, recall, and macro-F1 thresholds in IS-003.
4. S3 has at least 1,000 ranked document pairs or triplets across at least four
   genres and meets the rank-correlation and synthetic-confounder thresholds in
   IS-005.
5. At least two trained annotators label every human benchmark item; conflicts
   are adjudicated by a third qualified reviewer or the research lead.
6. The packet reports raw agreement, per-class agreement, weighted kappa for
   S7, rank agreement for S3, adjudication rate, and unresolved rate.
7. Every required synthetic fixture has a declared expected direction,
   tolerance, warning, or suppression result; 100% pass before G2 closes.
8. Negative controls include unchanged-language/source-outage,
   unchanged-language/topic-shift, and unchanged-language/duplicate-inflation
   cases; all trigger the expected non-substantive result.
9. Confidence and interval simulation meets the empirical coverage target in
   each scorer intent.
10. A benchmark regression in any required safety slice blocks release even
    when a pooled metric improves.
11. Public artifacts contain no raw restricted text, personal data, secret
    paths, provider credentials, or protected final labels that would enable
    contamination.
12. An independent reviewer can recompute all published metrics from permitted
    fixtures and no-text predictions using pinned code and manifests.
13. Each protected final partition evaluates one frozen scorer lineage once.
    After any final result is disclosed, later candidate qualification uses a
    newly sampled, non-overlapping benchmark major version.

## Benchmark semantics

Passing G2 means the test system is suitable for evaluating the approved MVP
constructs. Passing G3 means one scorer version met every predeclared required
threshold. Neither result establishes causal validity, universal coverage, or
permission to make claims beyond IS-003 or IS-005.

Allowed dispositions are:

- `HOLD`: evidence or a required decision is incomplete;
- `REJECT`: a frozen required gate failed;
- `SHADOW`: scorer may run privately for drift and operations evaluation;
- `VALIDATED`: G3 passed for the named frame and version;
- `RELEASED`: product, governance, operations, and G5 gates also passed.

## Data boundaries

Raw restricted benchmark text and adjudication notes remain in protected private
storage with role-based access. Public artifacts contain IDs, source aliases,
hashes, class counts, split counts, metrics, rubrics, authored synthetic
fixtures, aggregate disagreement, and no-text predictions where permitted.

Annotator identities are private. Public artifacts may report role,
qualification, and anonymized annotator IDs.

## Constraints

- Splits are deterministic and grouped by logical document and duplicate
  cluster.
- Final partitions are write-once and access logged.
- Benchmark runners do not require network access after dependencies and
  artifacts are pinned.
- Every candidate emits machine-readable predictions and gate results.
- Benchmark version changes that alter examples, labels, splits, or thresholds
  require a new major version and invalidate direct pass comparisons.
- Existing authorship-model benchmarks remain separate.

## Dependencies

### Approval prerequisites

- [IS-001](IS-001-score-ontology-and-reporting-semantics.md)
- [IS-003](IS-003-employer-ai-compulsion-scorer.md)
- [IS-005](IS-005-language-homogenization-scorer.md)

### Coordination interfaces

- [IS-002](IS-002-public-job-posting-data-foundation.md) and
  [IS-004](IS-004-professional-writing-corpus.md) supply admitted records after
  their data gates. Their approval is already transitive through IS-003 and
  IS-005; their execution completion gates human-label collection, not IS-006
  approval.
- Approved annotator, rights, protected-store, and independent-review
  procedures

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Annotator qualifications and training packet | Research lead | G2 |
| Final benchmark source mix | Data lead and governance reviewer | G2 |
| Protected final-label store and access owner | Governance reviewer | G2 |
| Whether S3 uses pairs, triplets, or both | Applied science lead | G2 |
| External-event and negative-control inventory | Research lead | G2 |
| Public release level for no-text predictions | Governance reviewer | G5 |
| Benchmark refresh cadence and contamination review | Research lead | G3 |

## Acceptance scenarios

1. **Given** two copies of one logical posting, **when** benchmark splits are
   built, **then** both copies remain in one partition.
2. **Given** a candidate improves pooled S7 macro F1 but misses the required
   enforcement precision, **when** gates run, **then** the disposition is
   `REJECT`.
3. **Given** an S3 formula reacts to a topic-only synthetic shift, **when** the
   confounder suite runs, **then** G2 or G3 fails despite other component gains.
4. **Given** final benchmark labels are unavailable to a developer, **when** a
   candidate is evaluated, **then** a controlled runner returns aggregate
   metrics and no-text predictions without exposing labels.
5. **Given** rights approval for a benchmark source expires, **when** release
   evidence is rebuilt, **then** the affected benchmark version is suspended
   and no new validation claim is made.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Benchmark construction and label collection are blocked until this table and
the relevant source and annotator decisions show approval.
