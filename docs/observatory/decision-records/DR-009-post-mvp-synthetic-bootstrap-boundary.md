# DR-009: Post-MVP Synthetic Bootstrap Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Version | 1.0.0 |
| Created | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G0 and G2 synthetic bootstrap only |
| Affected spec versions | IS-009-IS-014 v0.1.0; ES-015-ES-020 v0.1.0 |
| Supersedes | None |

## Decision

Authorize documentation, strict aggregate input contracts, deterministic
formula kernels, synthetic fixtures, property tests, suppressed score-contract
projections, and private development scaffolding for S1, S2, S4, S5, S6, and
S8.

This decision does not authorize:

- real source acquisition without a source-specific rights decision;
- model-provider calls or retention without provider review;
- processing of individual search histories or private contributor activity;
- use of unapproved taxonomies, ownership mappings, or protected labels;
- unsuppressed score release, entity publication, document authorship labels,
  causal claims, or production activation.

Provisional equal component weights are allowed only for synthetic invariants.
They are not research findings and must be replaced or explicitly approved at
G2 before any empirical score release.

## Context and evidence

The parent plan already defines all eight scores, but only S7 and S3 had
dedicated scorer intents and execution specs. The program owner instructed the
implementation agent to create todos for each spec and build them, then asked
specifically about the remaining models and designs. This record extends the
development authorization without fabricating unavailable source, benchmark,
or release evidence.

## Alternatives considered

| Alternative | Reason accepted or rejected |
| --- | --- |
| Leave the six scorers as bullets | Rejected because formulas and boundaries would remain underspecified |
| Implement real collectors immediately | Rejected because source rights and privacy decisions are unresolved |
| Build synthetic fail-closed kernels first | Accepted because it validates contracts and mathematical invariants without presenting empirical results |

## Consequences

- IS-009 through IS-014 are approved only for the stated bootstrap scope.
- ES-015 through ES-020 may implement synthetic contracts and formulas.
- Every score output remains suppressed until scorer-specific G1-G5 evidence
  passes.
- Source connectors, controlled model capture, and real-text extraction require
  narrower decisions and may be separate execution specs.
- No formula or synthetic fixture is evidence of web-scale impact.

## Revisit conditions

Supersede this record when a scorer receives real-source approval, freezes its
benchmark and formula, changes construct semantics, or is considered for public
release.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap; release gates retained |
| Approved version | 1.0.0 |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | Direct instruction to create todos for each spec and build the remaining models and designs |
