# ES-006: Professional-Writing Corpus Pipeline

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Data lead |
| Approved intent reference | IS-004 v0.1.0, approval pending |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1, G2 |
| Start prerequisites | ES-002 storage readiness |
| Stage interfaces | ES-003 shared adapters; bootstrap records to ES-009 and corpus to ES-007 |

## Implementation authorization

Implementation may begin only after IS-004 approval and ES-002 storage
readiness. Each source adapter requires an approved source decision. Corpus
release is blocked until genre, topic, event, boilerplate, quote, deduplication,
and coverage benchmarks pass.

## Outcome

Build immutable, rights-aware professional-writing releases with stable genre,
topic, event, entity, publisher, quote, boilerplate, template, and duplicate
controls suitable for S3 feature extraction.

## Current state

- The current public report lists platform, news, and social sources, but its
  crawler frame is not an approved professional-writing corpus.
- IS-002 and ES-003 define reusable source, collection, normalization, and
  identity primitives for job postings.
- No shared professional-document schema, four-genre release, topic model,
  event clustering, authored-content extractor, or fixed matched panel exists.

## Architecture and boundaries

```text
approved source adapters
          |
          v
immutable raw observations
          |
          v
document-type parser + authored-content extraction
          |
          v
language + genre + topic + event + entity/publisher
          |
          v
quote/boilerplate/template + duplicate controls
          |
          v
eligible document snapshots
          |
          v
corpus release + matched-frame index
```

Reuse ES-002 storage and source governance and ES-003 collector interfaces.
Add:

- `normalization/professional_document.py`
- `classification/genre.py`
- `classification/topic.py`
- `clustering/events.py`
- `quality/authored_content.py`
- `quality/quotes.py`
- `quality/templates.py`
- `corpora/professional_writing.py`
- `corpora/matched_frames.py`

## Data contracts

### Professional document snapshot

```json
{
  "schema_version": "observatory.professional_document_snapshot.v1",
  "snapshot_id": "snap:...",
  "logical_document_id": "doc:...",
  "source_id": "source-alias",
  "source_family": "research_metadata",
  "document_type": "research_abstract",
  "canonical_url": "https://example.invalid/record/123",
  "observed_at": "2026-07-25T12:00:00Z",
  "published_at": "2026-07-20T00:00:00Z",
  "language": {
    "code": "en",
    "confidence": 0.99,
    "version": "1.0.0"
  },
  "genre": {
    "id": "research_abstract",
    "confidence": 0.98,
    "status": "resolved",
    "version": "1.0.0"
  },
  "topics": [
    {
      "id": "topic:...",
      "confidence": 0.91,
      "version": "1.0.0"
    }
  ],
  "event_cluster": {
    "id": "event:...",
    "status": "resolved",
    "version": "1.0.0"
  },
  "entity": {
    "id": "entity:...",
    "status": "resolved",
    "confidence": 0.97,
    "registry_version": "1.0.0"
  },
  "publisher": {
    "id": "publisher:...",
    "owner_id": "owner:...",
    "status": "resolved",
    "registry_version": "1.0.0"
  },
  "content": {
    "raw_object_id": "object:...",
    "normalized_object_id": "object:...",
    "authored_segment_object_id": "object:...",
    "content_sha256": "...",
    "word_count": 312,
    "authored_word_count": 284,
    "quote_ratio": 0.04,
    "boilerplate_ratio": 0.05,
    "template_ratio": 0.08,
    "code_ratio": 0.0
  },
  "dedup": {
    "exact_cluster_id": "exact:...",
    "near_cluster_id": "near:...",
    "syndication_cluster_id": "syndication:...",
    "revision_group_id": "revision:...",
    "version": "1.0.0"
  },
  "quality": {
    "status": "eligible",
    "reasons": [],
    "version": "1.0.0"
  },
  "rights": {
    "source_decision_version": "1.0.0",
    "retention_until": "2027-07-25T00:00:00Z",
    "public_text_allowed": false
  }
}
```

Allowed MVP genres are frozen in the approved corpus release. Unknown,
mixed-genre, low-confidence, or unsupported records remain observed but
ineligible for the primary S3 frame.

### Matched-frame index

Each row identifies:

- corpus release and period;
- genre, topic, event-control state, source family, and optional jurisdiction;
- eligible logical documents;
- unique entity, publisher, owner, and source counts;
- baseline cell weight;
- current and fixed-panel eligibility;
- missingness and concentration metrics;
- suppression and warning candidates.

The index contains IDs and counts, not text or feature vectors.

## Algorithm design

### Authored-content extraction

1. Parse source-specific structural fields.
2. Remove navigation, cookie, application, recommendation, related-content,
   footer, and repeated legal blocks.
3. Detect block quotes, explicit quotations, citations, code, tables, and
   machine-generated metadata.
4. Mark reusable templates using within-source repeated-block hashes.
5. Retain block offsets and labels privately.
6. Build the authored segment without rewriting or paraphrasing text.

A document is ineligible when:

- authored text has fewer than 100 words or more than the approved maximum;
- quote, boilerplate, template, code, or unknown-block ratio exceeds its frozen
  genre threshold;
- language confidence is below the approved threshold;
- publication time is unavailable for a time-sensitive comparison;
- source rights or lineage are incomplete.

### Genre classification

Use source-native type only when the source decision and parser contract make it
authoritative. Otherwise evaluate:

1. deterministic structural rules;
2. word and character TF-IDF logistic classifier trained on the development
   benchmark.

Select the simplest candidate meeting IS-004 macro F1. The classifier excludes
source ID, URL host, period, and publisher identity. Low-confidence output is
`unresolved`.

### Topic assignment

Use a versioned multi-label topic taxonomy approved by the research lead.
Implement one-vs-rest logistic regression over word and character TF-IDF
features, with thresholds selected per topic on validation to meet the approved
precision floor. Include `other` and `unresolved`; do not force a document into
the nearest topic.

Taxonomy labels and training examples are frozen by release. Topic assignment
is diagnostic and matching metadata, never a runtime shortcut for S7 or an
AI-use label.

### Event clustering

Within one topic and a rolling 30-day window:

1. generate candidate pairs using named-entity overlap, title-token MinHash,
   and publication-date proximity;
2. confirm pairs with cosine similarity over a training-frozen TF-IDF
   representation and a maximum date gap;
3. build connected components;
4. split components that exceed the approved diameter or span;
5. assign stable event IDs from sorted member content hashes.

Thresholds are selected on development data and frozen before final evaluation.
Unresolved event state remains a valid warning input.

### Deduplication and revisions

Reuse ES-003 exact and near-duplicate logic. Add:

- syndication clustering across publishers;
- revision grouping for one canonical URL or source-native record over time;
- one logical contribution per dedup cluster and approved period;
- a policy for selecting the latest complete snapshot before period closure.

### Coverage and matching

Create primary cells from approved combinations of genre, topic, source family,
and event-control state. Baseline cell weights use eligible logical documents
after entity and publisher caps. A current cell is matchable only when it meets
document, entity or publisher, source-family, and concentration thresholds.

## Implementation tasks

1. Freeze source, genre, taxonomy, authored-content, event, quality, and
   eligibility decisions.
2. Extend canonical source adapter and snapshot schemas.
3. Implement authored-content, quote, boilerplate, code, and template labeling.
4. Implement genre rules, candidate model, abstention, and artifact.
5. Implement topic taxonomy import, classifier, thresholds, and versioning.
6. Implement event candidate generation, clustering, split checks, and stable
   IDs.
7. Extend deduplication for syndication and revision groups.
8. Implement entity, publisher, and owner registries and resolution.
9. Implement quality and corpus eligibility.
10. Implement coverage reports and matched-frame index.
11. Run bounded source pilots, historical sample, and benchmark.
12. Freeze a private corpus release and public-safe no-text manifest.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Parsers, block labels, ratios, eligibility, genre/topic enums, event IDs, revision selection |
| Property | Deterministic normalization, source/time identity excluded from classifiers, repeated block removal |
| Extraction benchmark | Authored-sentence preservation and boilerplate-removal thresholds from IS-004 |
| Genre/topic benchmark | IS-004 macro F1, per-class precision, abstention, hard negatives |
| Event benchmark | Pairwise precision/recall, oversized-component split, date and topic controls |
| Dedup benchmark | Exact and near-duplicate pairwise F1 at least 0.98, syndication and revision slices |
| Coverage | Missing months, one-source cells, one-event dominance, publisher ownership concentration |
| Privacy/rights | Raw text remains private, source decision enforced, deletion propagation |
| Performance | One million documents normalized and classified within 24 hours on the approved batch host |

## Operational design

- Source collection and normalization use the ES-003 queues.
- Genre, topic, event, and corpus release use separate versioned jobs.
- Idempotency key includes snapshot and each classifier/control version.
- Parser, classifier, taxonomy, or threshold changes create new outputs; they
  never mutate prior releases.
- Metrics: authored yield, ratio distributions, genre/topic unresolved rate,
  event size and concentration, duplicate/syndication rate, publisher and owner
  concentration, matched-cell coverage, and period completeness.
- Alerts: authored yield drop over 20%, unresolved increase over 10 points,
  event cluster over approved size/span, one owner over approved weight, or
  matched-panel coverage below 0.80.
- Period closure is immutable; late documents enter a correction release.

## Security, privacy, rights, and compliance

Raw, normalized, and authored text are private and source-policy controlled.
Topic, event, entity, and publisher IDs may reveal source structure and are
public only in aggregate. Public manifests use approved aliases and disclosure
thresholds. Deletion traverses every control and corpus release lineage edge.

## Release strategy

1. Synthetic source and authored-content fixtures.
2. One source per proposed genre, one month, private-only.
3. Adjudicated extraction, genre, topic, event, and dedup benchmark.
4. Four approved genres, one year, shadow release.
5. Pre-transition sample and baseline coverage review.
6. Full approved backfill.
7. Freeze corpus 1.0.0 and matched-frame index.
8. Roll back by reactivating the prior complete corpus release; never mix
   classifier or taxonomy versions.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Parser retains navigation | Authored-yield and benchmark drift | Quarantine partition | Fix parser and rebuild new version |
| Topic taxonomy drifts | Version and class distribution | Keep old release; block mixed comparison | Approve new taxonomy and bridge study |
| Major event merges unrelated topics | Cluster diameter and review | Mark cells confounded | Split cluster and rebuild version |
| Publisher aliases false-merge owners | Ownership review | Remove ownership-weighted release | Correct registry and rebuild |
| Historical source lacks dates | Time eligibility | Exclude from longitudinal frame | Find approved dated source |
| Template blocks dominate | Template ratio | Exclude or warn | Improve block hashing and benchmark |

## Definition of done

1. The exact IS-004 version in `Approved intent reference`, this exact
   execution-spec version, and all source decisions are approved.
2. Four approved genres meet source and historical coverage thresholds.
3. Authored extraction, genre, topic, event, dedup, and resolution benchmarks
   pass.
4. Matched-frame index and coverage reports reproduce from immutable lineage.
5. Public-safe manifest contains no restricted text or private identifiers.
6. Shadow and baseline backfills complete with stable metrics.
7. Monitoring, deletion, correction release, and rollback are tested.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Initial genres and sources | Research lead and data lead | G1 |
| Topic taxonomy and precision floor | Research lead | G2 |
| Event similarity, date, size, and span thresholds | Applied science lead | G2 |
| Genre-specific quality ratio thresholds | Research lead | G2 |
| Publisher ownership depth and caps | Research lead and data lead | G1 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval for this exact
execution version and the exact approved intent version.
