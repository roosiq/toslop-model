# ES-018: Model-Language Diffusion Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic formula complete; provider capture blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-012 v0.1.0 bootstrap scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1-G5 |
| Start prerequisites | ES-001, ES-006, ES-007 |
| Stage interfaces | ES-009 protected evaluation; ES-010 delivery |

## Implementation authorization

DR-009 authorizes synthetic prompt-response manifests, pattern statistics, lag
fixtures, and formula tests. Calls to real model providers and use of public
corpora require separate approval.

## Outcome

Provide reproducible contracts and a deterministic S5 aggregate kernel for
pattern prevalence, cross-domain diffusion, and temporal lead/lag, with no
document-level authorship output.

## Current state

The current Toslop detector remains a separate AI-likeness instrument. Strict
aggregate pattern inputs, prevalence, cross-domain, placebo-gated lag, and
suppressed ES-001 projection code are implemented in `slopslingers-infra` PR
12. No approved prompt suite, response corpus, pattern registry, or protected
benchmark exists.

## Architecture and boundaries

```text
prompt suite -> versioned model capture -> development-only pattern selection
             -> frozen aggregate extractor -> matched public prevalence
             -> diffusion/lag components -> suppressed ES-001 output
```

Only aggregate pattern counts cross the private extraction boundary.

## Data contracts

Reference manifests include prompt, model, provider, revision, parameter,
capture-time, rights, and response-object hashes. Frozen patterns include
family, extractor version, development evidence, pre-LLM prevalence, and
status. Aggregate observations contain bounded prevalence by domain and period,
coverage, and no document identifiers.

## Algorithm design

`pattern_prevalence` is a baseline-standardized bounded shift in frozen pattern
density. `cross_domain_diffusion` is the share of eligible domains showing a
positive shift above the approved noise threshold. `temporal_lead_lag` is a
bounded statistic comparing the predeclared model-release lag to shuffled-date
placebos. Synthetic S5 is their equal mean times 100. Missing placebo evidence,
pattern drift, or insufficient domains suppresses release.

## Implementation tasks

1. Define prompt-suite, capture, pattern, aggregate, and placebo contracts.
2. Implement bounded prevalence, domain diffusion, and lag components.
3. Implement no-document-output and suppression invariants.
4. Add preexisting-pattern, shift, domain, lag, shuffle, and leakage tests.
5. Approve provider/model/prompt frame and capture rights.
6. Build controlled corpus and development-only pattern selection.
7. Freeze candidate before protected-period extraction.
8. Run cross-model, genre, topic, pre-LLM, and shuffled-event validation.
9. Produce aggregate methods and release evidence.

## Test and benchmark plan

Tests cover bounds, baseline zero cases, domain support, permutation,
document-identifier rejection, feature-selection leakage, and placebo lag.
Protected evaluation includes held-out models, prompts, genres, topics, and
pre-LLM controls.

## Operational design

Capture manifests are immutable. A provider alias or revision change creates a
new corpus version. Pattern selection and protected extraction are separate
roles. Metrics include response coverage, rejected patterns, public-domain
coverage, shifts, placebo rank, drift, and suppression.

## Security, privacy, rights, and compliance

Provider credentials remain secret and responses follow approved retention.
No public or API artifact contains document-level pattern scores or authorship
labels. Restricted text and prompts stay private unless publication is allowed.

## Release strategy

Ship synthetic formulas first. Then approve capture, build the controlled
corpus, freeze patterns, run protected and placebo evaluation, complete G4
interpretation review, and activate under G5. Rollback restores a complete
pattern/corpus/scorer bundle.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Pattern common before model period | pre-LLM control | Reject pattern | Re-run development selection |
| Provider silently changes model | response drift/hash | Stop capture release | Start new corpus version |
| Genre/topic confounding | matched slice delta | Suppress | Reweight or reject pattern |
| Placebo lag is comparable | shuffled-date test | Reject lag claim | Report descriptive prevalence only |

## Definition of done

- Synthetic contracts, formulas, leakage tests, and no-authorship invariants
  pass.
- Provider rights, controlled corpus, frozen patterns, protected controls,
  uncertainty, monitoring, G4, and G5 are complete.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Prompt/model/provider frame | Research lead | G1 |
| Pattern thresholds and standardization | Applied science lead | G2 |
| Lag window and placebo family | Research lead | G2-G4 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap |
| Approved execution version | 0.1.0 bootstrap scope |
| Approved intent version | IS-012 v0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |
