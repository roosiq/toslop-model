# Proposal: INFINI-NEWS publication-shift scale

## Goal

Build a separate, research-only temporal publication-shift model for English news/article prose using `ruggsea/infini-news-corpus`, replacing the abandoned OpenAlex scale-up. The model estimates whether passage language resembles matched pre-LLM-era versus current-era news publication language.

**This score does not establish AI authorship.**

## Source decision

- Dataset: `ruggsea/infini-news-corpus`
- Frozen revision: `5b78199b86a838a5634b2d3267d72b98b8f71721`
- Coverage used: August 2016 through April 2026.
- Date axis: parsed article `publish_date` only. `warc_date`, Hugging Face configuration year/month, retrieval time, and upload time are provenance—not labels.
- Rights: article bodies remain local and research-only under the stricter dataset-card/publisher-rights interpretation. No article text may be committed, redistributed, deployed, or used for a commercial production model from this change.

## Corpus target

Collect 264,000 accepted rows:

- Core pre-era: 36,000 per year for 2018–2021.
- Core current-era: 36,000 per year for 2023–2025.
- Historical placebo: 4,000 each for 2016 and 2017.
- Transition evaluation: 2,000 from 2022.
- Forward evaluation: 2,000 from January–April 2026.

Core years are balanced at 3,000 rows per publication month. Placebo, transition, and forward rows are additional to the 252,000-row core.

## Scope

1. Implement a resumable, selective INFINI-NEWS collector with pinned shard/source identities.
2. Validate actual publication dates, explicit English metadata, text length, and rights/provenance fields.
3. Globally deduplicate before document assignment or feature extraction.
4. Freeze source-, publisher/domain-, topic-, author-, and random-diagnostic protocols where the source fields support them.
5. Train scaled lexical, stylometric, and multi-task encoder candidates.
6. Evaluate current-era versus pre-era performance against matched 2016–2021 historical placebos and confound controls.
7. Produce no-text metrics, predictions, model cards, checksums, and PASS/HOLD/REJECT decision evidence.

## Non-goals

- No production integration, API route, Worker deployment, or commercial use.
- No changes to the existing Toslop authorship detector, model IDs, thresholds, or outputs.
- No claim that publication era identifies whether text was AI-written.
- No use of WARC capture dates as publication dates.
- No raw article text in Git, public reports, logs, predictions, or checksum manifests.

## Must not change

Existing authorship artifacts/runtime and the verified OpenAlex pilot baseline remain untouched. The partial 49,748-row OpenAlex scale corpus is preserved locally only as abandoned evidence and is not mixed into INFINI-NEWS training.