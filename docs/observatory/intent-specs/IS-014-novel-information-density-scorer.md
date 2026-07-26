# IS-014: Novel Information Density Scorer

| Field | Value |
| --- | --- |
| Status | Synthetic bootstrap authorized; scorer release blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S8 |
| Work package | WP5.3 |
| Gates | G0, G1, G2, G3, G4, G5 |
| Approval prerequisites | IS-001 |

## Intent statement

Give researchers a longitudinal measure of how much distinct, attributable
claim and perspective content appears per unit of eligible public content,
without deciding whether claims are true or valuable.

## Problem and evidence

Content volume can rise while repeated, syndicated, paraphrased, or
source-poor material grows faster than distinct claims. Novelty is easily
confounded by topic, event, document length, extraction recall, and clustering
thresholds. S8 needs claim extraction, entailment-aware clustering, source and
perspective components, deduplication, and matched controls.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Compare distinct-information density within matched topic, event, and genre frames |
| Applied scientist | Evaluate claim extraction, clustering, attribution, and threshold sensitivity |
| Data lead | Monitor syndication, revision, source, and extraction coverage |
| Governance reviewer | Ensure novelty is not presented as truth or quality |

## Scope

S8 reports unique claim-cluster density, attributable-source density,
perspective contribution, repetition ratio, and syndication-adjusted volume by
approved topic, event, genre, source family, and period. Claims are clustered
within bounded comparable frames, not globally.

## Explicit exclusions

S8 does not:

- determine claim truth, importance, usefulness, originality rights, or
  plagiarism;
- treat lexical difference as a new claim;
- compare unrelated topics or events in one novelty denominator;
- infer document-level AI authorship;
- publish restricted claim text or sensitive entity assertions;
- claim LLM causation from descriptive density movement.

## Success measures

1. Claim extraction reaches at least 0.80 precision and 0.75 recall on the
   frozen, adjudicated benchmark.
2. Same-claim clustering F1 is at least 0.80, including paraphrase,
   contradiction, specificity, and event-identity slices.
3. Exact, near, syndication, and revision duplicates are handled before density
   aggregation.
4. Synthetic tests prove repeated identical claims reduce or preserve density,
   while adding an eligible distinct claim increases or preserves it.
5. Results expose extraction coverage, cluster stability, source attribution,
   denominator composition, uncertainty, and threshold sensitivities.
6. Low extraction coverage or unstable clustering suppresses the result.
7. Public methods explicitly distinguish novelty from truth and quality.

## Semantics

A higher S8 value means more distinct eligible claim, source, and perspective
content per normalized content unit in the stated frame. A lower value means
more repetition or lower distinct-information density. S8 does not mean the
content is more accurate, useful, creative, or human-authored.

## Data boundaries

Private extraction may use only source-approved text. Claim spans, sensitive
entities, and restricted text remain private. Public artifacts contain
thresholded cluster counts, densities, aggregate source categories, metrics,
methods, and immutable model/configuration versions.

## Constraints

- Claim comparison is bounded by topic, event, language, and time.
- Extraction and clustering versions are pinned within a release.
- Any LLM-assisted extraction is benchmarked, cached, and has a deterministic
  degraded mode.
- Denominators are explicit and length normalization is versioned.
- No real corpus processing before rights approval.

## Dependencies

Approval requires IS-001. Execution coordinates with ES-006 corpus controls,
IS-011/ES-017 perspective components when approved, ES-009 benchmarks, and
ES-010 delivery.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Claim unit and attribution ontology | Research lead | G2 |
| Entailment and clustering thresholds | Applied science lead | G2 |
| Content denominator and component weights | Research lead | G2 |
| Contradiction and specificity treatment | Research lead | G2 |
| Sensitive claim publication | Governance reviewer | G5 |

## Acceptance scenarios

1. **Given** ten copies of the same eligible claim, **when** S8 is calculated,
   **then** unique-claim density does not increase.
2. **Given** a distinct attributable claim in the same matched frame, **when**
   it is added, **then** unique-claim density rises or remains unchanged.
3. **Given** extraction coverage falls below threshold, **when** a score is
   requested, **then** it is suppressed.
4. **Given** a high S8 result, **when** it is described publicly, **then** no
   claim of truth, quality, originality, or human authorship is made.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap only |
| Approved version | 0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |

Real claim extraction, protected evaluation, and scorer release remain blocked.
