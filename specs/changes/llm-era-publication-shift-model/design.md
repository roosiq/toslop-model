# Design: LLM-era publication shift model

## 1. Model boundary

The publication-shift model is a separate artifact family. Its score means “similarity to matched current-era publication language,” not “AI probability.” It must have independent modules, model IDs, thresholds, reports, API fields, and checksums. No authorship score may be an input feature.

## 2. Source and corpus contract

### OpenAlex collection

Use OpenAlex Works with a pinned collection configuration and recorded retrieval timestamps. Production collection must support an API key, identify itself with a contact address, retry bounded transient failures, and fail clearly on authentication, quota, schema, cursor, or rate-limit errors. A successful anonymous pilot is not a durable access contract.

Required source fields:

- stable work ID and DOI, when present;
- `publication_date` and `publication_year`;
- `language` and work type;
- `abstract_inverted_index`, reconstructed deterministically;
- stable author IDs;
- primary source/journal and publisher IDs;
- primary topic plus topic/domain hierarchy IDs;
- source/API revision or snapshot identity when available;
- retrieval timestamp and request/filter manifest.

Reject rows with absent/invalid dates, non-English language, non-abstract work types, failed abstract reconstruction, fewer than 150 words, or implausible metadata. Store original and normalized text only beneath ignored `services/data/publication_shift/` paths with restrictive permissions. Public artifacts contain hashes, counts, IDs/provenance where redistribution permits, and metrics—but no text or previews.

### Normalized record

Each local record must include `document_id`, `work_id`, optional DOI, original and normalized abstract, normalized-text SHA-256, SimHash/MinHash cluster ID, publication date/year/month, era/corpus role, source/journal ID, publisher ID, topic IDs, author IDs, word count, retrieval manifest ID, and split assignment. Metadata is for matching, splitting, and diagnostics, not runtime inference.

### Corpus roles and size

- Core: at least 36,000 accepted rows for each of 2018–2021 and 2023–2025 (at least 252,000 total), sampled/matched across month, topic, source family, work type, and length.
- Transition: 2022, excluded from training and threshold selection.
- Historical placebo: 2014–2017 plus the pre-LLM core, sized to support matched windows.
- Forward: partial-year 2026, excluded from training while incomplete and compared only against the same elapsed months in historical/current years.

Report every requested, accepted, rejected, duplicate, near-duplicate, and unmatched count by year, month, source, and topic. Partial-year or sparse strata must remain visible.

## 3. Deduplication, matching, and splits

Deduplicate globally before feature extraction using work ID, DOI, normalized-text SHA-256, and near-duplicate clusters. No exact or near-duplicate cluster may cross any train/validation/test lane.

Build separate reproducible evaluation protocols rather than pretending one split proves every control:

1. Document-random diagnostic split (non-promotable).
2. Source/journal-held-out split.
3. Publisher-held-out split.
4. Topic-held-out split.
5. Author-held-out split, assigning authors before works and dropping bridge works that would cross partitions.
6. Same-author pre/post matched analysis, kept separate from author-held-out evidence.
7. Forward-year and transition sets frozen before model fitting.

Matching uses metadata only to construct comparable cohorts. Runtime input is passage text only. Save deterministic no-text split manifests and assert zero prohibited overlap.

## 4. Models

### Lexical baseline

Fit balanced logistic regression on word TF-IDF 1–3 grams and character TF-IDF 3–5 grams, capped at 200,000 training-fitted features. Report coefficients and performance with/without masking. This is the primary interpretable baseline and leakage detector.

### Stylometric model

Extract training-versioned document features: sentence/paragraph length moments, lexical diversity, function words, POS rates, transition density, passive voice, nominalizations, dependency depth, punctuation, headings/lists, repeated phrases, adjacent-sentence similarity, and within-document sentence similarity. Fit LightGBM or CatBoost using training-only preprocessing. Exclude metadata and provenance features.

### Multi-task encoder

Fine-tune a small ModernBERT or DeBERTa encoder on 256–512-token chunks with three objectives:

1. pre-LLM versus current-era classification;
2. publication-year regression;
3. matched-pair newer-text ranking.

Split documents before chunking. Aggregate chunks with a declared, validation-selected method. Keep model revision, tokenizer, seed, objective weights, hardware, and training logs.

### Ensemble and calibration

Evaluate components first. If they pass diagnostics, fit a simple validation-only meta-model over component outputs, then use Platt or isotonic calibration selected without final-test access. Do not hand-tune weights on held-out lanes. The ensemble must beat the strongest component by a predeclared margin or remain unpromoted.

## 5. Confound and masking controls

Train diagnostic classifiers for source/publisher, topic, author where feasible, and publication year. Repeat evaluation after masking named entities, dates, numbers, URLs, citations, explicit AI terminology, and topic-specific nouns. Run source-only and metadata-only baselines to quantify dataset separability.

A candidate is blocked if success is explained primarily by source/topic imbalance, explicit year/AI tokens, extraction artifacts, or length. Inspect top lexical coefficients, stylometric importances, and neural attribution probes for these shortcuts.

## 6. Evaluation and claims

Report ROC-AUC, PR-AUC, balanced accuracy, F1, Brier score, ECE, calibration curves, bootstrap confidence intervals, and performance by year/month, topic, source/publisher, author-overlap status, and passage length.

Historical placebo comparisons must use matching and time gaps comparable to the main contrast. An unusual-shift claim requires both:

- publisher-held-out main ROC-AUC above the acceptance gate; and
- main-minus-strongest-placebo ROC-AUC lift of at least 0.05 with a grouped-bootstrap 95% confidence interval whose lower bound is above zero.

The 2022 score distribution should be reported as a transition curve, not forced into either class. Partial 2026 results are forward evidence only.

## 7. Artifact and API contract

Freeze:

- source/request manifest and accepted no-text corpus manifest;
- split/matching manifests;
- feature configuration and vocabulary hashes;
- model/tokenizer revisions and learned artifacts;
- calibration object and validation-selected thresholds;
- no-text predictions and aggregate metrics;
- environment/hardware metadata and SHA-256 checksums.

A future local API may return `temporal_style_score`, conservative `predicted_period`, calibrated confidence, component scores, matched-baseline descriptors, influential linguistic features, model ID, and limitations. It must always state that the score does not establish AI authorship. Default labels remain indeterminate until validation chooses thresholds.

## 8. Local hardware

The full pipeline must run on the Ryzen AI Max 395 with 128 GB memory. Use streaming/cursor collection, Parquet or DuckDB/Polars processing, sparse lexical matrices, cached stylometric features, resumable encoder training, and a small pilot before every scale increase.