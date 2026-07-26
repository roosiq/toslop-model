# IS-013: Human Knowledge Contribution Scorer

| Field | Value |
| --- | --- |
| Status | Synthetic formula bootstrap complete; real collection blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S6 |
| Work package | WP6.2 |
| Gates | G0, G1, G2, G3, G4, G5 |
| Approval prerequisites | IS-001 |

## Intent statement

Give researchers a longitudinal measure of public human Q&A, maintenance, and
explanatory contribution across approved knowledge systems, without inferring
individual motivation or treating platform volume as knowledge quality.

## Problem and evidence

Public knowledge systems can change in contribution volume, contributor
breadth, response coverage, maintenance, and durable reuse. Platform policy,
spam controls, migrations, seasonality, repository mix, and automation can
produce the same movements. S6 needs human-eligible activity definitions,
cross-platform normalization, cohort controls, and bot/automation handling.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Assess whether contribution indicators move across comparable public knowledge systems |
| Data lead | Monitor API, dump, bot-resolution, and platform-break coverage |
| Applied scientist | Compare volume, contributor breadth, response, maintenance, and reuse components |
| Governance reviewer | Protect contributor privacy and prohibit motivation inference |

## Scope

S6 reports normalized eligible contributions, active contributor breadth,
response/answer coverage, maintenance activity, and durable reuse for approved
Stack Exchange, GitHub, Wikipedia, and forum frames. Platform components remain
visible and a fixed-platform panel is required.

## Explicit exclusions

S6 does not:

- infer why an individual contributed or stopped contributing;
- rate a contributor's expertise, effort, cognition, or employment status;
- treat commits, answers, edits, or posts as interchangeable without
  platform-specific eligibility rules;
- include detected bots in human-contribution components;
- claim LLM causation from a temporal decline;
- publish contributor-level histories or sensitive identifiers.

## Success measures

1. Each platform has a versioned activity ontology and human/bot eligibility
   rule with benchmark evidence.
2. Results expose platform components, unique contributors, eligible objects,
   rates, effective sample, coverage, uncertainty, and warnings.
3. Synthetic tests prove duplicate-event invariance and monotonic response to
   an added eligible contribution when denominators are fixed.
4. Platform breaks, migrations, mass imports, and source outages are detected
   and either adjusted with evidence or marked incomparable.
5. Fixed-platform, fixed-community, and leave-one-platform-out sensitivities
   pass approved tolerances.
6. Public outputs meet k-anonymity-style disclosure thresholds and contain no
   contributor profiles.

## Semantics

A higher S6 value means more or broader eligible public human contribution is
observed in the approved frame. A lower value means lower volume, contributor
breadth, response coverage, maintenance, or reuse. It is not a direct measure
of knowledge quality, individual effort, or cognitive engagement.

## Data boundaries

Only public dumps or APIs approved by source decisions may be used. Direct
identifiers are pseudonymized for private cohort analysis and are never
published. Deleted or restricted content follows source-specific retention and
lineage deletion. Public artifacts contain thresholded aggregates only.

## Constraints

- Platform-specific eligibility precedes cross-platform normalization.
- Bot and bulk-import handling is explicit and versioned.
- Stable pseudonyms are scoped to the minimum required analysis boundary.
- No private repository, private community, or user telemetry.
- Real collection is blocked until source rights decisions pass.

## Dependencies

Approval requires IS-001. Execution uses ES-002 storage, ES-009 benchmark
controls, and ES-010 delivery. Each platform collector requires a separate
source decision and connector execution boundary.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Platform activity ontologies | Research lead | G1 |
| Bot, automation, and bulk-import rules | Data lead | G2 |
| Cross-platform weights and baseline | Research lead | G2 |
| Contributor pseudonym retention | Governance reviewer | G1 |
| Durable-reuse definition | Applied science lead | G2 |

## Acceptance scenarios

1. **Given** a duplicated event in an upstream dump, **when** S6 is calculated,
   **then** it contributes once.
2. **Given** a mass automated import, **when** eligibility runs, **then** it is
   excluded from human-contribution components and reported in coverage.
3. **Given** one platform changes its API, **when** the next period runs,
   **then** the break is warned and cross-break trend is blocked.
4. **Given** a community has too few contributors, **when** public output is
   requested, **then** the result is suppressed.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap only |
| Approved version | 0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |

Real platform collection, identity resolution, benchmark tuning, and release
remain blocked.
