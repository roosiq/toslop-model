# ES-007: Language Feature and Control Pipeline

| Field | Value |
| --- | --- |
| Status | Synthetic fallback features implemented; feature release blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-005 v0.1.0 synthetic scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G2, G3 |
| Start prerequisites | ES-006 approved corpus release |
| Stage interfaces | Development and protected-final evaluation through ES-009; features to ES-008 |

## Implementation authorization

Synthetic deterministic fallback features are approved by DR-006. Real-corpus
execution requires an approved ES-006 release. A production semantic feature
remains blocked until its model, revision, license, checksum, runtime, and
benchmark decision is approved.

## Outcome

Create deterministic, versioned document-level lexical, syntactic, rhetorical,
and semantic representations plus matching-control metadata, without using
source, publisher, entity, period, or AI-likeness labels as content features.

## Current state

- The private gateway includes NLTK, spaCy, scikit-learn, transformers, and
  local model-loading patterns.
- Existing authorship stylometric and embedding features target AI-likeness and
  cannot be copied into S3 without a separate feature definition and benchmark.
- No S3 feature schema, baseline vocabulary, rhetorical registry, semantic
  artifact, or feature release exists.

## Architecture and boundaries

```text
eligible authored document segment
             |
             +--> lexical vector
             +--> syntactic vector
             +--> rhetorical vector
             +--> semantic vector
             |
             v
feature eligibility + quality + versions
             |
             v
private feature object + no-text manifest
```

Proposed modules:

- `scorers/s3/tokenize.py`
- `scorers/s3/lexical.py`
- `scorers/s3/syntactic.py`
- `scorers/s3/rhetorical.py`
- `scorers/s3/semantic.py`
- `scorers/s3/controls.py`
- `scorers/s3/feature_release.py`

Features are stored as typed arrays in private Parquet objects partitioned by
corpus release, period, and genre. PostgreSQL stores IDs, object pointers,
dimensions, versions, eligibility, checksums, and lineage, not large vectors.

## Data contracts

### Feature row

```json
{
  "schema_version": "observatory.s3_feature_row.v1",
  "logical_document_id": "doc:...",
  "snapshot_id": "snap:...",
  "corpus_release_id": "corpus:...",
  "period_id": "2026-07",
  "control_cell": {
    "genre_id": "research_abstract",
    "topic_ids": ["topic:..."],
    "event_cluster_id": "event:...",
    "source_family": "research_metadata",
    "entity_id": "entity:...",
    "publisher_id": "publisher:..."
  },
  "vectors": {
    "lexical": {
      "object_column": "lexical_vector",
      "dimension": 20001,
      "status": "available"
    },
    "syntactic": {
      "object_column": "syntactic_vector",
      "dimension": 512,
      "status": "available"
    },
    "rhetorical": {
      "object_column": "rhetorical_vector",
      "dimension": 96,
      "status": "available"
    },
    "semantic": {
      "object_column": "semantic_vector",
      "dimension": 384,
      "status": "available"
    }
  },
  "quality": {
    "authored_word_count": 284,
    "sentence_count": 15,
    "paragraph_count": 4,
    "parser_coverage": 0.99,
    "status": "eligible",
    "reasons": []
  },
  "versions": {
    "tokenizer": "1.0.0",
    "lexical": "1.0.0",
    "syntactic": "1.0.0",
    "rhetorical": "1.0.0",
    "semantic": "1.0.0",
    "control": "1.0.0"
  }
}
```

Control IDs are metadata for matching and aggregation. They are never appended
to content vectors.

### Feature release

Records corpus parent, feature definitions, vocabulary and registry checksums,
parser and model artifacts, vector dimensions and dtypes, eligibility counts,
missingness, drift diagnostics, benchmark results, object checksums, and
approval evidence.

## Algorithm design

### Shared preprocessing

- Use authored segments from ES-006.
- Normalize whitespace and Unicode only as already frozen in the corpus.
- Segment sentences and tokens using a pinned local NLP pipeline.
- Lowercase lexical lemmas but retain casing and punctuation only in explicitly
  named rhetorical or sentence-shape features.
- Exclude quoted, boilerplate, template, table, navigation, and code blocks.
- Do not remove content words based on period or class association.

### Lexical vector

Fit the baseline vocabulary on the approved training and baseline corpus only:

- 20,000 most frequent eligible lemmas after an approved minimum document
  frequency;
- one `other` bucket;
- per-document probability distribution with additive smoothing
  `epsilon=1e-12`;
- separate no-text scalars for type-token ratio using fixed 100-token windows,
  hapax rate, mean lemma frequency, and phrase repetition.

Vocabulary and frequency table are immutable artifacts. Current-period text
never changes the vocabulary of an existing feature version.

### Syntactic vector

Concatenate normalized distributions for:

- universal part-of-speech unigrams, bigrams, and trigrams;
- dependency relation unigrams and selected head-dependent pairs;
- sentence-length bins;
- punctuation-shape bins;
- passive, subordinate, coordination, nominalization-proxy, and clause-density
  features approved by the registry.

Rows require parser coverage at or above the approved threshold. Unknown parse
states do not map to zero.

### Rhetorical vector

Use a public-safe, versioned registry of deterministic counts normalized per
1,000 words or per paragraph:

- transition and discourse-marker families;
- hedges, boosters, stance, and uncertainty markers;
- first-, second-, and third-person reference;
- question, imperative, list, heading, and parenthetical structure;
- paragraph opening and closing patterns;
- repeated sentence-opening and phrase-template rates;
- sentence and paragraph length distribution summaries.

The registry stores category definitions and authored examples, not copied
source text. Any learned rhetorical classifier requires a new execution version
and benchmark.

### Semantic vector

Use one approved local sentence/document embedding artifact. Requirements:

- fixed model and immutable revision;
- recorded license and permitted use;
- files and tokenizer checksum-verified;
- local offline inference;
- mean of sentence embeddings after excluding ineligible blocks, followed by
  L2 normalization;
- fixed truncation and batching policy;
- benchmarked against human semantic-similarity rankings and topic/event hard
  negatives.

The exact model is an open G2 decision. The no-network TF-IDF plus
TruncatedSVD representation is the mandatory deterministic fallback and
sensitivity representation, not an automatic production substitute.

### Feature eligibility

A top-level S3 feature row is eligible only when all four vectors are available
and finite, quality thresholds pass, and every artifact resolves. Missing
semantic inference does not silently create a three-component row.

### Drift

For each feature release and period, calculate:

- missing and eligibility rates;
- vocabulary out-of-vocabulary rate;
- parser coverage and tag distributions;
- rhetorical feature quantiles;
- embedding norm and centroid shift;
- per-genre and per-topic diagnostics.

Drift thresholds are set from baseline resampling before release.

## Implementation tasks

1. Freeze tokenization, vocabulary, syntactic, rhetorical, quality, and semantic
   decisions.
2. Implement typed feature schema and Parquet writer with checksums.
3. Implement shared preprocessing and golden token/sentence fixtures.
4. Implement lexical artifact fitting and extraction.
5. Implement syntactic extraction and parser coverage.
6. Implement rhetorical registry and extraction.
7. Benchmark semantic candidates and approve one artifact.
8. Implement local semantic extraction and deterministic fallback sensitivity.
9. Implement feature eligibility, quality, drift, and release manifests.
10. Run synthetic, labeled, performance, and reproducibility tests.
11. Build baseline and one-year shadow feature releases.
12. Publish public-safe feature definitions and benchmark packet.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Tokenization, smoothing, normalization, vector dimensions, finite values, registry counts |
| Golden | Fixed authored examples with exact tokens, POS/dependencies, rhetoric counts, and vector checksums |
| Property | Source/time/entity metadata invariance, document order invariance, deterministic batching |
| Synthetic | Lexical substitutions, syntactic template changes, rhetorical repetition, semantic paraphrase and unrelated-topic pairs |
| Human benchmark | IS-005 rank-correlation thresholds for combined surface and semantic representations |
| Drift | Baseline resampling false-alert rate and known artifact-change detection |
| Privacy | No text, tokens, or record vectors in public manifests |
| Performance | One million eligible documents complete within 24 hours on the approved batch host |
| Artifact | Offline load, checksum, revision, dimension, dtype, and dependency lock |

## Operational design

- Feature jobs run only against immutable corpus releases.
- Idempotency key includes document snapshot and every feature version.
- Parquet files use atomic temporary upload followed by checksum verification
  and manifest commit.
- Metrics: throughput, failures, vector availability, eligibility, parser
  coverage, OOV, feature quantiles, embedding norms, and drift.
- Alerts: dimension mismatch, NaN/Infinity, artifact checksum mismatch,
  eligibility drop over 10 points, parser coverage drop, OOV spike, or
  embedding centroid drift beyond the approved threshold.
- Failed or partial partitions cannot enter ES-008.

## Security, privacy, rights, and compliance

Feature objects are restricted derived data and inherit source retention and
deletion. Record-level vectors are not public and are protected against bulk
exfiltration. Learned model files load locally with checksum verification and no
arbitrary code execution. Public artifacts contain definitions, aggregate
statistics, metrics, and checksums only.

## Release strategy

1. Golden synthetic feature release.
2. Small approved corpus sample.
3. Human and confounder benchmark.
4. Baseline feature artifact fit.
5. One-year shadow extraction and drift review.
6. Full approved backfill.
7. Freeze feature release 1.0.0.
8. Roll back by activating the prior complete feature release; never mix vector
   definitions in one S3 series.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| NLP model version drift | Artifact checksum | Refuse extraction | Restore pinned files |
| Current text changes vocabulary | Vocabulary checksum | Block release | Use baseline artifact |
| Parser fails on one genre | Coverage and drift | Mark rows ineligible | Fix or approve genre-specific exclusion |
| Semantic model unavailable | Artifact load | Block primary row; run fallback diagnostic | Restore artifact |
| Vector contains non-finite values | Validation | Quarantine partition | Fix feature and rebuild |
| Public manifest leaks tokens | Hygiene scan | Block publication | Regenerate allowlisted manifest |

## Definition of done

1. The exact IS-005 version in `Approved intent reference`, this exact
   execution-spec version, and all feature decisions are approved.
2. All four feature families have immutable definitions and artifacts.
3. Golden, synthetic, human-ranking, metadata-invariance, and privacy tests
   pass.
4. Baseline and shadow releases complete within the batch budget.
5. Drift thresholds, metrics, and alerts are active.
6. Feature lineage and deletion propagation pass.
7. Public-safe methods and evidence packet reproduce checksums and metrics.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| NLP parser and exact revision | Applied science lead | G2 |
| Lexical vocabulary size and document-frequency floor | Applied science lead | G2 |
| Rhetorical registry contents | Research lead | G2 |
| Semantic model, license, dimension, and truncation | Research lead and applied science lead | G2 |
| Feature drift thresholds | Applied science lead | G3 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic deterministic fallbacks only |
| Approved execution version | 0.1.0 synthetic scope |
| Approved intent version | IS-005 v0.1.0 synthetic scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-001 and DR-006 |

Production parser and semantic artifacts, benchmark freeze, corpus extraction,
and feature release remain blocked.
