# IS-012: Model-Language Diffusion Scorer

| Field | Value |
| --- | --- |
| Status | Synthetic bootstrap authorized; scorer release blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S5 |
| Work package | WP7.1-WP7.3 |
| Gates | G0, G1, G2, G3, G4, G5 |
| Approval prerequisites | IS-001, IS-004 |

## Intent statement

Give researchers a longitudinal measure of whether patterns distinctive to a
versioned controlled model-response corpus become more prevalent in matched
public writing, without classifying individual documents as AI-authored.

## Problem and evidence

Model-associated language can diffuse through direct use, editing, imitation,
templates, changing professional norms, or shared training data. Generic
phrases and post-period feature selection create false signals. S5 therefore
requires a predeclared prompt suite, model/version capture, held-out
distinctiveness tests, pre-LLM controls, matched corpora, and lag analysis.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Determine whether controlled model-associated patterns diffuse in matched public corpora |
| Applied scientist | Select stable patterns and test out-of-model, genre, topic, and time robustness |
| Governance reviewer | Enforce the prohibition on document-level authorship claims |
| Product owner | Decide whether diffusion evidence supports experimental release |

## Scope

S5 builds a versioned response corpus across approved models, prompts, sampling
conditions, and dates; selects patterns using development periods only; and
reports aggregate prevalence shifts and model-release lag relationships by
genre, topic, source, and period.

## Explicit exclusions

S5 does not:

- label a document, author, employee, student, or publisher as using AI;
- estimate a document-level probability of AI authorship;
- use one model family as a universal reference;
- select features on the same period used to claim diffusion;
- claim that similarity proves direct model influence;
- reuse the existing Toslop AI-likeness score without a separately benchmarked
  role and versioned decision.

## Success measures

1. The prompt suite, model identities, revisions, parameters, dates, and raw
   response manifests are reproducible.
2. Selected patterns pass pre-LLM prevalence, held-out distinctiveness,
   cross-model stability, and genre/topic confounder gates.
3. Placebo patterns and shuffled release dates produce null lag findings within
   approved error tolerance.
4. All outputs expose pattern-family components, matched controls, uncertainty,
   source coverage, and version lineage.
5. Feature selection is frozen before evaluation and protected periods are not
   exposed to candidate development.
6. Public copy and APIs make no document-level authorship assertion.

## Semantics

A higher S5 value means the approved model-associated pattern set is more
prevalent in matched public writing than in the approved baseline. A lower
value means it is less prevalent. The result is a diffusion/similarity
indicator, not proof of model use, copying, authorship, or causation.

## Data boundaries

Controlled model responses require provider terms, retention, and publication
review. Public-corpus text follows IS-004 or another approved corpus intent.
Restricted prompt outputs and source text remain private; public artifacts
contain aggregate pattern statistics, hashes, allowed examples, and methods.

## Constraints

- Prompt and model revisions are immutable release inputs.
- Feature selection and evaluation periods are separated.
- No individual-document score is persisted in a public store.
- Deterministic local feature extraction is preferred after pattern freeze.
- Provider changes trigger a new reference-corpus version.

## Dependencies

Approval requires IS-001 and IS-004. Execution uses ES-006/ES-007 corpus and
feature controls, ES-009 protected evaluation, and ES-010 delivery.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Model and prompt sampling frame | Research lead | G1 |
| Provider output retention and redistribution | Governance reviewer | G1 |
| Pattern families and distinctiveness thresholds | Applied science lead | G2 |
| Model-release event dates and lag windows | Research lead | G2 |
| Role of current Toslop detector | Research lead | Separate decision |

## Acceptance scenarios

1. **Given** a pattern is common before the model reference period, **when**
   selection runs, **then** it is rejected as non-distinctive.
2. **Given** a held-out public period, **when** S5 is calculated, **then** no
   feature is tuned using that period.
3. **Given** one document has high pattern density, **when** public output is
   requested, **then** no document-level authorship label is emitted.
4. **Given** shuffled release dates match the observed lag result, **when**
   validation runs, **then** the causal interpretation is rejected.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap only |
| Approved version | 0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |

Provider calls, reference-corpus capture, feature freeze, and release remain
blocked by their narrower gates.
