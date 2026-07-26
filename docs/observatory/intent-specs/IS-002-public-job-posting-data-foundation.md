# IS-002: Public Job-Posting Data Foundation

| Field | Value |
| --- | --- |
| Status | Implementing under DR-001 and DR-002; collection blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Data lead |
| Decision owner | Program owner |
| Work packages | WP2.1, WP2.2, WP2.3, WP2.4, WP2.5 |
| Gates | G0, G1 |
| Approval prerequisites | IS-001 |

## Intent statement

Give the research and applied-science teams a rights-reviewed, longitudinal,
deduplicated, versioned corpus of public employer language that can support
Employer AI Compulsion measurement without redistributing restricted posting
text or obscuring source coverage.

## Problem and evidence

Employer AI requirements can appear in job postings, career pages, policy
statements, and annual reports. These sources differ in historical depth,
access terms, duplication, update behavior, and employer identity. A scorer
built on opportunistic scraping could measure collector changes instead of
employer behavior.

The private backend currently contains a bounded local Toslop crawler store in
`slopslingers-infra/services/gateway/app/toslop_storage.py`. Its two SQLite
tables support AI-likeness crawl jobs and measurements; they do not provide the
source rights registry, immutable snapshots, temporal identity, employer and
occupation resolution, or historical coverage required by this intent.

This work is needed before S7 can distinguish a real longitudinal change from
duplicate reposting, source outages, or a shifting employer mix.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Data lead | Admit, restrict, replace, suspend, or retire a source |
| Research lead | Determine which employer, occupation, industry, and period comparisons are defensible |
| Applied science lead | Build and evaluate mandate-language extraction on stable, leakage-safe records |
| Governance reviewer | Approve collection, retention, publication, access, and deletion controls |
| Operations owner | Detect collector failure, source drift, and incomplete backfills |

## Scope

Included source families are:

- public employer career pages and job-detail pages whose terms and robots
  policy permit the proposed collection;
- licensed or explicitly reusable public job-posting datasets;
- public employer policy statements and annual reports admitted by a
  source-specific decision record;
- public occupation and industry taxonomies used only for normalization;
- historical snapshots sufficient to establish an approved pre-LLM baseline
  and monthly or quarterly post-transition series.

The canonical corpus record includes:

- stable document, snapshot, source, employer, and collection-run IDs;
- canonical URL or licensed source key;
- observed, first-seen, last-seen, published, and expiration times when known;
- source family, document type, language, jurisdiction, occupation, industry,
  location, seniority, employment type, and remote status when permitted;
- normalized employer identity and resolution evidence;
- immutable content checksum and private snapshot pointer;
- raw, normalized, and near-duplicate checksums;
- rights, retention, access, publication, robots, and deletion state;
- collector, parser, schema, taxonomy, and normalization versions;
- quality, eligibility, deduplication, and exclusion reasons.

The target frame begins in 2019 where source coverage permits. A released S7
stratum requires at least 24 eligible pre-transition months and 12
post-transition months; unavailable historical coverage must remain an explicit
gap.

## Explicit exclusions

This intent does not permit:

- bypassing authentication, paywalls, CAPTCHAs, rate limits, robots
  restrictions, or technical access controls;
- collecting applicant records, resumes, applications, private recruiter
  messages, employee monitoring records, or non-public policies;
- treating public accessibility as automatic permission to retain or
  redistribute text;
- publishing restricted full text, snippets, personal contact details, or
  source-specific record-level labels;
- inferring protected traits, applicant suitability, employer intent beyond the
  observed language, or actual employee compliance;
- using collector-specific fields as hidden scorer features;
- filling missing historical months with synthetic postings;
- implementing S7 classification or scoring.

## Success measures

1. Every admitted source has an approved, versioned decision record covering
   owner, access method, terms, robots behavior, license, allowed fields,
   retention, redistribution, deletion, rate limits, and substitute source.
2. One canonical schema validates 100% of admitted documents and rejects
   records missing source, snapshot, checksum, temporal, rights, and
   transformation provenance.
3. Re-running an unchanged collector window produces no new logical documents
   and records a new collection-run manifest only when observations differ.
4. Exact duplicate detection has 100% precision and recall on deterministic
   checksum fixtures; near-duplicate clustering reaches at least 0.98 pairwise
   F1 on an adjudicated benchmark.
5. Employer resolution reaches at least 0.95 precision on an adjudicated
   benchmark and exposes unresolved or ambiguous identities rather than forcing
   a match.
6. Occupation and industry mapping record taxonomy version and mapping
   confidence; low-confidence mappings remain `unresolved`.
7. Every release frame reports monthly eligible count, unique employer count,
   unique posting count, source-family share, occupation share, jurisdiction
   share, missing-field rates, and collector health.
8. A publishable stratum has at least 500 eligible logical documents, 50 unique
   employers, 5 occupation groups, and 2 admitted source families per period,
   or uses a stricter scorer-specific threshold. Smaller strata are suppressed.
9. At least 24 historical months and 12 post-transition months meet the approved
   coverage gate before longitudinal S7 release.
10. Raw snapshots are immutable, encrypted, access logged, and recoverable from
    a manifest; public artifacts contain only permitted metadata, checksums, and
    aggregates.
11. Source suspension, deletion, legal hold, and retention expiry tests prove
    that restricted records stop flowing into new features and scores.
12. A source outage or source-mix shift creates a machine-readable warning and
    cannot silently appear as employer-language change.

## Corpus semantics

Corpus states are:

- `observed`: collected but not yet rights or quality reviewed;
- `admitted`: eligible for the named research and scoring purposes;
- `restricted`: retained for a narrower approved purpose but unavailable to the
  scorer;
- `quarantined`: excluded pending rights, integrity, or privacy review;
- `deleted`: content removed under policy while a permitted tombstone and audit
  event remain;
- `superseded`: replaced by a newer logical-document snapshot.

An admitted record proves only that eligible public employer language was
observed from a permitted source. It does not prove that a role was filled, that
the policy was enforced, or that a worker used AI.

## Data boundaries

- Raw and normalized text remain in the private implementation boundary.
- Public replication artifacts may contain source aliases, time ranges,
  counts, checksums, schema versions, aggregate coverage, and approved examples
  that are authored for documentation rather than copied from source text.
- Personal contact details and tracking parameters are removed before durable
  normalization.
- Access follows least privilege by role. Collector credentials and license
  files remain secret-managed and never enter manifests.
- Retention is source-specific. A source cannot be admitted with an unknown
  retention or deletion rule.
- Content and derived features must be traceable to a deletion tombstone so
  future rebuilds exclude removed material.

## Constraints

- Collection must be idempotent and resumable by source and time window.
- Source requests obey per-source budgets and identify the collector where
  required.
- Immutable objects use content-addressed IDs and cryptographic checksums.
- Transformations are deterministic for a pinned version.
- The MVP must operate on bounded source windows before any broad backfill.
- The existing Toslop SQLite store and public report continue unchanged.

## Dependencies

### Approval prerequisites

- [IS-001](IS-001-score-ontology-and-reporting-semantics.md)
- Approved source inventory and legal/governance review
- Employer and taxonomy reference data decision records

### Coordination interfaces

- Private object storage and metadata-store execution specs
- [IS-006](IS-006-mvp-validation-benchmark.md) supplies development-only
  deduplication and resolution labels after IS-002 approval; it is not an
  approval prerequisite for this data-foundation intent.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Initial source list and historical depth | Data lead and governance reviewer | G1 |
| Whether each source permits durable text retention | Governance reviewer | Before source admission |
| Production object-store provider and region | Data lead | Execution approval |
| Employer parent/subsidiary identity policy | Research lead and data lead | G1 |
| Occupation and industry taxonomy versions | Research lead | G1 |
| Source-specific deletion propagation period | Governance reviewer | G1 |
| Jurisdictions requiring additional collection restrictions | Governance reviewer | Before source admission |
| Feasibility of two-source-family coverage in historical months | Data lead | G1 |

## Acceptance scenarios

1. **Given** the same posting appears on an employer page and an admitted
   licensed feed, **when** normalization runs, **then** both observations remain
   in lineage but one logical document contributes to counts.
2. **Given** a source changes its terms or robots policy, **when** the next
   collector run starts, **then** collection pauses until the source decision
   record is reviewed.
3. **Given** an employer name matches two entities, **when** resolution cannot
   meet the precision policy, **then** the record remains unresolved and is not
   forced into an employer-level score.
4. **Given** a period falls below coverage thresholds, **when** S7 requests an
   aggregate, **then** the corpus reports the deficiency and the score is
   suppressed.
5. **Given** a deletion request is approved, **when** the deletion workflow
   completes, **then** raw and normalized content are removed, a permitted
   tombstone remains, and the next rebuild excludes the document.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for foundation implementation; real source collection pending source decisions |
| Approved version | 0.1.0 implementation scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-001 and DR-002 |

Foundation implementation is authorized. Collection remains blocked until each
source decision record shows approval.
