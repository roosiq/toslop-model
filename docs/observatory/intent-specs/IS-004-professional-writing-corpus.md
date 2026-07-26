# IS-004: Professional-Writing Corpus

| Field | Value |
| --- | --- |
| Status | Synthetic bootstrap implemented; real corpus blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Data lead |
| Decision owner | Program owner |
| Work packages | WP2.1-WP2.5, WP3.1 |
| Gates | G0, G1 |
| Approval prerequisites | IS-001 |

## Intent statement

Give researchers a rights-reviewed, longitudinal professional-writing corpus
whose genre, topic, source, entity, event, and duplication structure is explicit
enough to measure language convergence without confusing it with a changing
content mix.

## Problem and evidence

Writing naturally becomes more similar when documents cover the same topic,
follow one genre template, quote the same event, or come from duplicated and
syndicated sources. A corpus that does not preserve these controls can report
"homogenization" when the actual change is more job postings, more earnings
releases, one major news event, or a crawler shift.

The current Toslop system measures AI-likeness across a bounded public crawl.
Its public Worker lists platform, news, and social source segments in
`toslop/src/index.js`, while the private SQLite store records page-level crawl
measurements. Those assets do not provide the matched professional-writing
frame, immutable rights registry, topic/event controls, or balanced historical
samples required here.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Approve comparable genre, topic, entity, and time frames |
| Data lead | Admit sources and determine whether a period is complete enough to compare |
| Applied science lead | Build language features on stable, deduplicated, matched records |
| Governance reviewer | Approve collection, retention, publication, and deletion controls |
| Operations owner | Detect source, parser, topic, or composition drift |

## Scope

The MVP corpus supports English public professional writing from at least four
approved genres selected from:

- corporate newsrooms, public reports, and press releases;
- public employer career and policy writing admitted under IS-002;
- research titles and abstracts with an approved reuse basis;
- public professional or technical articles;
- public job postings;
- eligible public-web text from versioned snapshots where genre and publisher
  identity can be resolved.

Each logical document records:

- source, snapshot, document, entity, publisher, owner, and collection-run IDs;
- canonical URL or source-native key and content checksum;
- observed, published, first-seen, and last-seen dates when available;
- language, genre, subgenre, topic, event cluster, entity, and source family;
- title and body segment boundaries in the private store;
- quote, boilerplate, navigation, table, code, and template proportions;
- exact, near-duplicate, syndication, revision, and cluster identities;
- quality and eligibility state with exclusion reasons;
- rights, retention, publication, and deletion state;
- collector, parser, normalizer, topic model, taxonomy, and schema versions.

The target time frame begins in 2019 where admitted sources permit. Each
released analytical stratum needs a predeclared historical baseline,
transition-period coverage, and current-period coverage. The corpus supports
monthly feature extraction and quarterly reporting when monthly samples are too
sparse.

## Explicit exclusions

This intent does not authorize:

- inferring whether a document, author, or organization used an LLM;
- scraping sources that prohibit the proposed access, retention, or use;
- retaining personal contact details, private drafts, paywalled text acquired
  without permission, or user-specific browser data;
- treating one broad "web text" pool as comparable across all genres and years;
- balancing by copying or synthesizing missing historical documents;
- using publisher, source, or time identity as a hidden semantic or
  homogenization target;
- publishing restricted source text, document-level style labels, or entity
  rankings;
- implementing the S3 feature pipeline or score.

## Success measures

1. Every source has an approved decision record with access, rights, allowed
   use, retention, redistribution, deletion, rate, and substitute-source rules.
2. One canonical schema validates 100% of admitted records and rejects missing
   source, time, checksum, genre, rights, and transformation provenance.
3. Genre annotation reaches at least 0.90 macro F1 and topic assignment reaches
   at least 0.80 macro F1 or an approved clustering-quality equivalent on an
   adjudicated benchmark.
4. Exact duplicate detection is deterministic; near-duplicate and syndication
   clustering reaches at least 0.98 pairwise F1 on an adjudicated benchmark.
5. Boilerplate and quote removal preserves at least 0.95 of eligible authored
   sentences and removes at least 0.95 of labeled boilerplate on the final
   extraction benchmark.
6. Every released period reports document, entity, publisher, source-family,
   genre, topic, event-cluster, language-quality, and missing-field coverage.
7. A released monthly stratum has at least 500 eligible logical documents, 50
   entities or publishers, and 2 independent source families. A released
   quarterly stratum has at least 1,500 documents. Stricter scorer thresholds
   may override these minima.
8. Each released genre has at least 24 eligible pre-transition months and 12
   post-transition months, or is explicitly excluded from longitudinal claims.
9. A fixed-composition matched panel can be constructed for at least 70% of
   released periods; unmatched results remain diagnostic and visibly labeled.
10. Event concentration, genre mix, topic mix, source mix, and entity mix
    crossing approved thresholds create warnings and matched sensitivity
    outputs.
11. Immutable snapshot and transformation manifests reproduce all public-safe
    corpus counts and checksums without exposing raw restricted text.
12. Deletion and source-suspension tests remove affected documents from future
    feature builds and preserve only permitted tombstones.

## Corpus semantics

An `eligible` corpus record means that a versioned document segment is permitted
for the named analysis and passes the approved quality and control rules. It
does not mean the text is representative of all professional writing, written
by one person, original, factually correct, or produced without AI assistance.

Corpus outputs distinguish:

- `observed`: collected but not admitted;
- `admitted`: permitted for the named processing purpose;
- `eligible`: admitted and passing the current quality frame;
- `restricted`: retained for a narrower approved purpose;
- `quarantined`: blocked pending review;
- `suppressed`: eligible record exists but cannot support the requested
  aggregate;
- `deleted`: content removed under policy with a permitted tombstone.

## Data boundaries

Raw and normalized text remain private. Public artifacts contain only approved
source aliases, counts, checksums, schemas, aggregate quality metrics,
benchmark metrics, and authored synthetic examples. Record-level topic, genre,
and dedup labels remain restricted unless their source decision permits
publication.

The corpus must support deletion by source-native key, canonical URL,
content-addressed ID, and snapshot lineage. Derived feature sets inherit the
most restrictive applicable source policy.

## Constraints

- Collection and normalization are idempotent and resumable.
- Time and genre labels cannot be inferred from filesystem paths alone.
- Topic and event assignments are versioned and may not be silently recomputed
  under a new model.
- Content features must be computed after boilerplate, quote, and duplicate
  controls.
- No live LLM call is required to reconstruct an approved corpus release.
- Existing Toslop AI-likeness collection and public routes remain unchanged.

## Dependencies

### Approval prerequisites

- [IS-001](IS-001-score-ontology-and-reporting-semantics.md)

### Coordination interfaces

- [IS-002](IS-002-public-job-posting-data-foundation.md) for shared employer
  records when job postings are included; otherwise the corpus can proceed
  independently.
- [IS-006](IS-006-mvp-validation-benchmark.md) supplies development-only
  corpus-quality and similarity fixtures after approval.
- Approved source, taxonomy, event-clustering, retention, and publication
  decisions

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Initial four genres and source list | Research lead and data lead | G1 |
| Historical baseline availability per genre | Data lead | G1 |
| Topic taxonomy versus unsupervised clustering policy | Research lead | G1 |
| Event-cluster definition and maximum concentration threshold | Applied science lead | G2 |
| Quote and syndication treatment for research abstracts and press releases | Research lead | G1 |
| Publisher ownership resolution depth | Data lead | G1 |
| Public entity-level corpus reporting | Governance reviewer | G5 |
| Multilingual expansion | Research lead | Out of MVP |

## Acceptance scenarios

1. **Given** the same press release is syndicated across 40 domains, **when**
   corpus normalization runs, **then** all observations retain lineage but one
   logical document contributes to language dispersion.
2. **Given** one event dominates a month's research abstracts, **when** a
   comparison is requested, **then** the output carries an event-concentration
   warning and includes a matched or event-excluded sensitivity result.
3. **Given** a genre has no admissible pre-transition history, **when** S3 asks
   for longitudinal movement, **then** that genre is excluded rather than
   assigned a fabricated baseline.
4. **Given** a source parser starts retaining navigation text, **when** quality
   monitoring detects the shift, **then** the affected partition is quarantined
   before scoring.
5. **Given** a document is deleted under source policy, **when** a corpus
   rebuild occurs, **then** all dependent eligible sets exclude it and record
   the permitted lineage change.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for explicit-role synthetic corpus only |
| Approved version | 0.1.0 synthetic scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-001 and DR-006 |

Real collection, classifier freeze, historical coverage, and corpus release
remain blocked by source-specific and G1-G2 decisions.
