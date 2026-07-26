# IS-009: External Exploration Scorer

| Field | Value |
| --- | --- |
| Status | Synthetic bootstrap authorized; scorer release blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S1 |
| Work package | WP6.1 |
| Gates | G0, G1, G2, G3, G4, G5 |
| Approval prerequisites | IS-001 |

## Intent statement

Give researchers a longitudinal measure of whether public information-seeking
activity spans a broad and varied set of external knowledge systems, without
inferring the private search behavior, curiosity, or cognition of individuals.

## Problem and evidence

Changes in search, reference, and public knowledge-system activity may indicate
that external exploration is becoming broader or narrower. Raw traffic is not
enough: platform access, ranking changes, seasonality, topic demand, bots, and
source outages can all move activity independently of LLM use.

No governed S1 scorer currently separates breadth, source diversity, and public
knowledge-system activity from platform volume. A dedicated construct,
matched baseline, source controls, and negative controls are required.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Determine whether exploration indicators move consistently across approved source families |
| Applied scientist | Diagnose source-mix, topic-mix, seasonality, and platform-policy sensitivity |
| Governance reviewer | Verify that no individual search profile or mental state is inferred |
| Product owner | Decide whether S1 evidence is sufficient for experimental or validated release |

## Scope

S1 combines approved aggregate indicators of outbound-link breadth, effective
destination diversity, public reference activity, and knowledge-system
participation. Results are calculated by topic, source family, geography where
rights permit, and month or quarter. Every release retains source-family
components and a matched-source sensitivity series.

## Explicit exclusions

S1 does not:

- inspect or publish individual search histories, queries, browsing sessions,
  IP addresses, cookies, or user profiles;
- equate lower aggregate activity with reduced curiosity, intelligence, or
  independent thought;
- treat Google Trends values as absolute search counts;
- infer that an LLM caused a descriptive movement;
- combine S1 with other scores into a public composite;
- release a result based on one platform or an unmatched source outage.

## Success measures

1. At least three approved source families contribute to a reportable frame.
2. Source-family components, coverage, seasonality adjustment, topic controls,
   sample size, uncertainty, warnings, and versions are exposed.
3. Synthetic tests prove that adding distinct destinations cannot lower the
   breadth component when all other inputs are fixed.
4. Leave-one-source-out and fixed-source-panel sensitivities remain within the
   approved tolerance or trigger suppression.
5. Platform discontinuities and major outages create warnings and block trend
   interpretation across the affected break.
6. Public copy contains no individual-level or cognitive diagnosis.
7. A frozen benchmark and at least two external negative controls pass before
   validated release.

## Semantics

A higher S1 value means the approved public indicators show broader and more
varied external exploration in the stated frame. A lower value means observed
activity is more concentrated, less broad, or lower across the approved public
knowledge systems. Missing means no eligible frame exists. Suppressed means
coverage, rights, benchmark, comparability, or uncertainty gates failed.

S1 is not a measure of an individual's curiosity, autonomy, research quality,
or reliance on an LLM.

## Data boundaries

Only aggregate or de-identified public data admitted by a source-specific
decision may be used. Raw query logs, user identifiers, and session-level
traces are prohibited. Public artifacts contain aggregate counts, normalized
features, manifests, methods, and benchmark metrics. Retention and deletion
follow the source registry and descendant-lineage controls.

## Constraints

- Deterministic aggregation for pinned inputs and versions.
- Explicit source-break and seasonality handling.
- No dependence on a single commercial API.
- Conventional statistical components are preferred.
- No real collection before source rights and terms are approved.

## Dependencies

Approval requires IS-001. Execution uses ES-001 contracts, ES-002 storage,
ES-009 benchmark controls, and ES-010 delivery. Source-specific collectors are
separate approval and implementation boundaries.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Source families and baseline interval | Research lead and data lead | G1 |
| Topic and seasonality controls | Applied science lead | G2 |
| Source-family weights and minimum coverage | Research lead | G2 |
| Geographic publication granularity | Governance reviewer | G5 |
| Platform methodology discontinuities | Data lead | G3 |

## Acceptance scenarios

1. **Given** destination activity spreads evenly across more approved domains,
   **when** S1 is calculated, **then** breadth rises or remains unchanged.
2. **Given** one source family is unavailable, **when** a period is processed,
   **then** the primary result is suppressed or explicitly marked incomparable.
3. **Given** only individual-level search logs are available, **when** source
   admission is evaluated, **then** the source is rejected.
4. **Given** a descriptive decline, **when** the result is published, **then**
   the copy does not claim reduced curiosity or LLM causation.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap only |
| Approved version | 0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |

Real-source collection, benchmark tuning, causal interpretation, and release
remain blocked by G1-G5.
