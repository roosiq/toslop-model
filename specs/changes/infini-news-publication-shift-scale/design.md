# Design: INFINI-NEWS publication-shift scale

## Construct and artifact boundary

This is a temporal news-publication-style model, not an AI-authorship detector and not the earlier academic-abstract model. Use a distinct corpus schema, model IDs, artifact directory, score field (`current_era_similarity`), model card, and decision packet.

Every result states: **“This score does not establish AI authorship.”**

## Frozen source contract

Source: `ruggsea/infini-news-corpus` at revision `5b78199b86a838a5634b2d3267d72b98b8f71721`.

Required local row fields:

- stable document ID derived from source revision plus WARC record/payload identity;
- original URL and normalized URL hash;
- `sitename`/hostname;
- article `publish_date` raw value and normalized ISO date;
- independent `warc_date` for lag/provenance audit only;
- WARC record ID, filename, target URI, and payload digest when present;
- explicit language metadata and validation result;
- original and normalized article text under ignored mode-0600 local paths;
- normalized-text SHA-256, URL hash, and near-duplicate cluster;
- author identity when present; topic/section fields when present;
- source revision, shard identity, row identity, retrieval time, and rights status.

Reject rows with missing/invalid `publish_date`, contradictory or non-English language metadata, fewer than 150 words, invalid source identity, impossible date ordering beyond the documented quarantine policy, or duplicate identity/text cluster.

## Sampling

Use actual `publish_date` to assign all roles and quotas. Hub `year_YYYY` and Parquet paths are WARC partitions used only to find candidate shards.

- 2016: 4,000 placebo rows across available August–December months, 800/month.
- 2017: 4,000 placebo rows distributed as evenly as possible across 12 months.
- 2018–2021 and 2023–2025: exactly 3,000 accepted rows/month.
- 2022: 2,000 transition rows distributed as evenly as possible across 12 months.
- 2026: 500 rows/month for January–April only.

Apply deterministic seeded ordering and a per-sitename monthly cap. Report source concentration and reject a frozen corpus where any source dominates a month beyond the predeclared cap. Do not route models or thresholds by source.

## Collection strategy

1. Query the pinned Hub file manifest.
2. Stream or download only enough pinned Parquet shards from relevant WARC partitions to satisfy publication-month quotas.
3. Persist shard checksums and resumable scan offsets before progressing.
4. Filter on `publish_date` after reading each row; never assume WARC partition alignment.
5. Write raw/normalized JSONL or Parquet only below ignored `services/data/publication_shift/infini_news_v1` with directory mode 0700 and files mode 0600.
6. Emit public-safe no-text manifests under `services/evals/publication_shift_model/infini_news_v1`.

## Leakage and confound controls

Deduplicate globally by WARC identity, URL, payload digest, normalized-text hash, and near-duplicate cluster before splitting. Split documents before chunks/features.

Required protocols:

- publisher/domain-held-out primary;
- source/sitename-held-out;
- author-held-out when author coverage is sufficient, dropping bridge works;
- topic/section-held-out when metadata is sufficient, otherwise a documented learned-topic clustering protocol fitted on training only;
- random-document diagnostic;
- same-author pre/post matched analysis when coverage permits;
- frozen 2022 transition and January–April 2026 forward evaluations.

Runtime input is passage text only. Source, dates, URL, author, WARC metadata, dataset identity, and existing Toslop scores are excluded from model features and routing.

## Model ladder

1. Word/character TF-IDF logistic baseline.
2. Deterministic stylometry with CatBoost or LightGBM.
3. Text-only ModernBERT or DeBERTa multi-task model for era classification, year regression, and pairwise recency ranking.
4. Validation-only calibration/ensemble only if every component passes confound diagnostics and the ensemble improves over the strongest component.

## Evaluation

Primary gates retain publisher/domain-held-out ROC-AUC >0.75, ECE <0.08, masked-content ROC-AUC >0.70, masked loss <0.10, and main-minus-strongest-placebo lift >=0.05 with grouped-bootstrap 95% CI lower bound >0. Historical placebos are redesigned for available coverage, including matched 2016–2017 versus 2018–2019 and 2017–2018 versus 2020–2021 contrasts. Severe per-source, topic, year, or length collapses remain blockers.

## Safety

INFINI-NEWS article bodies are research-only local inputs. Public artifacts contain IDs/hashes/counts/metrics but no text, titles, or previews. No product integration occurs unless a separate rights review and deployment change are explicitly approved.