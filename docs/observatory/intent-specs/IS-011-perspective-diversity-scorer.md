# IS-011: Perspective Diversity Scorer

| Field | Value |
| --- | --- |
| Status | Synthetic formula bootstrap complete; empirical scorer blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S4 |
| Work package | WP5.2 |
| Gates | G0, G1, G2, G3, G4, G5 |
| Approval prerequisites | IS-001 |

## Intent statement

Give researchers a topic- and event-controlled measure of how many distinct
frames, causal explanations, arguments, and proposed actions remain visible in
public discourse, without rating which perspective is correct.

## Problem and evidence

Lexical variation is not perspective diversity: different words can express
the same frame, while similar language can support opposing arguments. A valid
S4 scorer needs a governed taxonomy, multi-label extraction, event controls,
semantic clustering, adjudication, and explicit handling of minority frames.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Compare frame breadth and balance within matched topics and events |
| Applied scientist | Evaluate taxonomy coverage, extraction quality, and clustering stability |
| Governance reviewer | Prevent viewpoint ranking, ideology inference, and speaker profiling |
| Product owner | Decide whether S4 is adequately benchmarked for release |

## Scope

S4 reports effective frame count, normalized frame entropy, pairwise semantic
dispersion, argument-role coverage, and minority-frame retention. It supports
approved news, forum, and professional-text frames with topic, event, language,
genre, source, and period controls.

## Explicit exclusions

S4 does not:

- decide whether a frame, claim, cause, or proposal is true or desirable;
- classify an individual's ideology, personality, cognition, or intent;
- treat sentiment, topic count, or embedding distance alone as perspective;
- use a changing LLM taxonomy without pinning and benchmarking it;
- publish sensitive speaker-level labels;
- infer LLM causation from descriptive convergence.

## Success measures

1. A versioned taxonomy defines frame, cause, argument, and action labels plus
   unknown, mixed, quoted, and unsupported states.
2. Double-labeled benchmark agreement reaches Krippendorff alpha of at least
   0.70 for primary frame families.
3. Macro F1 is at least 0.75 and minority-frame recall at least 0.70 on the
   frozen benchmark.
4. Synthetic tests prove permutation invariance and monotonic response to
   adding a genuinely distinct represented frame.
5. Topic, event, source, genre, and extraction-model sensitivities are exposed.
6. Unknown or low-taxonomy-coverage rates beyond threshold suppress S4.
7. Public explanations remain descriptive and do not rank viewpoints.

## Semantics

A higher S4 value means more distinct and more evenly represented perspectives
are visible in the eligible frame. A lower value means fewer perspectives,
greater dominance, or lower argument-role breadth. It does not mean the
discourse is more truthful, civil, intelligent, or fair.

## Data boundaries

Only source-approved public text may enter private extraction. Evidence spans
and sensitive speaker labels remain restricted. Public artifacts contain
aggregate frame counts above disclosure thresholds, no-text benchmark metrics,
taxonomy versions, and methods.

## Constraints

- Multi-label extraction with explicit unknown state.
- Taxonomy and extraction versions are immutable within a release.
- Conventional classifiers are preferred; any LLM extraction is pinned,
  cached, benchmarked, and replaceable.
- Minimum minority-frame support and disclosure thresholds apply.
- Languages require separate taxonomy and benchmark approval.

## Dependencies

Approval requires IS-001. Execution uses ES-002 storage, ES-006 controls where
applicable, ES-009 protected evaluation, and ES-010 delivery. Taxonomy review is
a separate G2 decision.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Frame taxonomy scope and granularity | Research lead | G2 |
| Multi-label aggregation and unknown treatment | Applied science lead | G2 |
| Minority-frame disclosure threshold | Governance reviewer | G3 |
| Cross-language comparability | Research lead | Out of initial scope |
| LLM-assisted extraction candidate | Applied science lead | G2 |

## Acceptance scenarios

1. **Given** balanced observations across four distinct approved frames,
   **when** S4 is calculated, **then** diversity exceeds a one-frame monopoly.
2. **Given** many paraphrases of one frame, **when** S4 is calculated, **then**
   lexical variety alone does not increase frame count.
3. **Given** taxonomy coverage falls below threshold, **when** a result is
   requested, **then** it is suppressed with a coverage warning.
4. **Given** a minority frame has too few observations for safe publication,
   **when** components are emitted, **then** it is folded into a protected
   aggregate or suppressed.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap only |
| Approved version | 0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |

Taxonomy freeze, real extraction, protected evaluation, and release remain
blocked.
