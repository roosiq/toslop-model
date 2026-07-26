# IS-010: Source Concentration Scorer

| Field | Value |
| --- | --- |
| Status | Synthetic formula bootstrap complete; empirical scorer blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Research lead |
| Decision owner | Program owner |
| Score ID | S2 |
| Work package | WP5.1 |
| Gates | G0, G1, G2, G3, G5 |
| Approval prerequisites | IS-001 |

## Intent statement

Give researchers an auditable longitudinal measure of how strongly public links
and citations concentrate among destination domains, publishers, and ownership
groups in a controlled content frame.

## Problem and evidence

Domain counts can overstate diversity when many domains share one owner, and
raw link counts can be dominated by templates, syndicated content, crawlers, or
one prolific publisher. S2 needs canonical destinations, ownership resolution,
authored-link extraction, and composition controls.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Identify whether reference concentration changes within comparable topics and genres |
| Data lead | Evaluate domain, publisher, and ownership resolution coverage |
| Applied scientist | Compare HHI, top-k share, entropy, and effective-source components |
| Governance reviewer | Review entity publication and attribution risk |

## Scope

S2 measures authored outbound links and formal citations at domain, publisher,
and approved ownership-group levels. It reports HHI, top-1/top-5 shares,
normalized entropy, and effective source count by topic, genre, source family,
and period. Domain and ownership results remain separate components.

## Explicit exclusions

S2 does not:

- judge source truthfulness, political orientation, quality, or legitimacy;
- count navigation, advertising, social-share, tracking, or boilerplate links;
- infer audience exposure from the presence of a link;
- merge domains into owners without versioned evidence and confidence;
- accuse a publisher of coordination;
- claim LLM causation from concentration movement.

## Success measures

1. Authored-link extraction precision is at least 0.95 on the frozen benchmark.
2. Domain canonicalization and publisher resolution each reach 0.95 precision;
   unresolved ownership remains visible rather than guessed.
3. Synthetic equal-share, monopoly, duplicate, and ownership-merger fixtures
   match exact expected values.
4. Results expose all concentration components and resolved/unresolved shares.
5. Genre, topic, template, source-family, and syndication sensitivities are
   available for every release.
6. Ownership uncertainty beyond the approved threshold suppresses the
   ownership-level component without suppressing valid domain components.

## Semantics

A higher S2 value means eligible references are more concentrated among fewer
destinations in the stated frame. A lower value means references are more
evenly distributed. Missing and suppressed follow the shared contract.

S2 is not a source-quality score, a misinformation score, proof of editorial
coordination, or a measure of what any person read.

## Data boundaries

Eligible public documents, extracted links, citation identifiers, canonical
domains, and versioned publisher/ownership mappings require source and
redistribution approval. Public results expose aggregates and mapping coverage,
not restricted source text or private ownership evidence.

## Constraints

- Exact, deterministic concentration formulas.
- Template and syndication deduplication precedes aggregation.
- Domain and ownership estimates are never silently substituted.
- Mapping revisions require versioned recomputation.
- Entity-level publication is disabled by default.

## Dependencies

Approval requires IS-001. Execution coordinates with ES-002 storage, ES-006
professional-writing controls where applicable, ES-009 benchmarks, and ES-010
delivery.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Registrable-domain and platform-host rules | Data lead | G1 |
| Publisher and ownership evidence policy | Governance reviewer | G1 |
| Formula weights and source-unit weighting | Research lead | G2 |
| Self-links and reference-list treatment | Research lead | G2 |
| Public named-publisher drill-down | Program owner | G5 |

## Acceptance scenarios

1. **Given** all eligible references resolve to one domain, **when** S2 is
   calculated, **then** the domain concentration component is 100.
2. **Given** equal references to many domains, **when** S2 is calculated,
   **then** concentration declines as the domain count increases.
3. **Given** unresolved ownership, **when** results are emitted, **then** domain
   metrics remain available and ownership metrics are warned or suppressed.
4. **Given** a navigation template repeats on every page, **when** links are
   extracted, **then** those links do not enter the authored-reference frame.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic bootstrap only |
| Approved version | 0.1.0 bootstrap scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-009 |

Real mappings, collection, benchmark tuning, and release remain blocked.
