# Acceptance: INFINI-NEWS publication-shift scale

A candidate remains HOLD unless every required gate is evidenced.

## Source and rights

- [ ] Source is `ruggsea/infini-news-corpus` revision `5b78199b86a838a5634b2d3267d72b98b8f71721`.
- [ ] Every accepted row has a parseable original article `publish_date`; no WARC/capture/configuration date sets the label.
- [ ] `publish_date` and `warc_date` are preserved independently with lag diagnostics.
- [ ] Article bodies stay below ignored, mode-0700/0600 local research paths and never appear in tracked artifacts, logs, fixtures, predictions, checksums, or docs.
- [ ] Public evidence labels the corpus research-only and does not imply publisher-rights clearance or production authorization.

## Corpus

- [ ] Exactly 252,000 core rows exist: 36,000/year for 2018–2021 and 2023–2025, 3,000/publication month.
- [ ] Exactly 8,000 historical-placebo rows exist: 4,000 each for 2016 and 2017 using the available month coverage.
- [ ] Exactly 2,000 transition rows from 2022 are evaluation-only.
- [ ] Exactly 2,000 January–April 2026 rows are forward-evaluation-only.
- [ ] Total accepted corpus is 264,000 after global deduplication.
- [ ] Explicit-English, >=150-word, source-identity, date, rejection, source-cap, and month-distribution contracts pass.

## Leakage and features

- [ ] WARC identity, payload digest, URL, text hash, and near-duplicate overlap are zero across model-bearing partitions.
- [ ] Publisher/domain-, source-, topic-, and author-held-out protocols are frozen; unsupported metadata lanes are replaced only by predeclared training-only constructions and are not silently omitted.
- [ ] Documents are assigned before chunks/features.
- [ ] Runtime input is text only; source, date, URL, author, WARC, dataset, and existing Toslop model outputs are excluded.
- [ ] 2022 and 2026 are excluded from fitting, calibration, and threshold selection.

## Required models and evaluations

- [ ] Full word/character TF-IDF logistic baseline exists.
- [ ] Full CatBoost or LightGBM stylometric candidate exists.
- [ ] Full multi-task ModernBERT or DeBERTa candidate exists or a measured hardware blocker is documented as HOLD.
- [ ] Each candidate is evaluated on publisher/domain-, source-, topic-, author-, masking-, length-, transition-, forward-, and historical-placebo lanes where defined.
- [ ] Source-only/metadata-only shortcut diagnostics and feature/attribution audits are reported.

## Performance

On the frozen publisher/domain-held-out primary lane:

- [ ] ROC-AUC >0.75.
- [ ] ECE <0.08.
- [ ] Masked-content ROC-AUC >0.70 with absolute loss <0.10.
- [ ] Main contrast exceeds the strongest matched 2016–2021 historical placebo by >=0.05 ROC-AUC.
- [ ] Grouped-bootstrap 95% CI for main-minus-placebo lift has lower bound >0.
- [ ] No required source, topic, year, or length subgroup has an unreported severe collapse.

## Reproducibility and isolation

- [ ] Source/shard manifest, corpus/split hashes, seeds, model/tokenizer revisions, configs, no-text predictions, metrics, environment, hardware, artifacts, and SHA-256 checksums are frozen.
- [ ] Focused tests and both local/global checksum manifests pass.
- [ ] Existing Toslop authorship artifacts, thresholds, runtime, and production behavior are unchanged.
- [ ] No PR, deployment, commercial use, or production integration occurs from this research change.
- [ ] Every output states: “This score does not establish AI authorship.”

## Frozen evaluation-integrity audit (2026-07-13)

- [x] Deterministic public-safe evidence is frozen under `services/evals/publication_shift_model/infini_news_v1/diagnostics/evaluation_integrity/`; local checksums and focused tests pass.
- [ ] **FAILED — alternate-lane integrity:** the selected primary model was evaluated on alternate test sets containing primary-training rows: source `31,459/50,320`, topic `34,944/52,617`, author `30,197/45,237`, and random `34,153/50,751`.
- [ ] **FAILED — historical placebo support:** both named contrasts contain only early-arm rows (the full candidates have 8,000 label-0 rows and zero label-1/later-arm rows), so placebo ROC-AUC and main-minus-placebo lift are undefined.
- [ ] **HOLD — full encoder:** only a 160-row CPU smoke artifact exists (`26` train, `25` validation, `13` primary test); the unverified-accelerator blocker is measured and preserved, but no full 264,000-row candidate exists.
- [ ] **FAILED — subgroup stability:** four source hashes with support >=100 have accuracy below 70%; April 2023 is `414/598` (69.23%) and January 2024 is `580/951` (60.99%).
- **Recorded decision: REJECT this frozen evaluation run for final-test leakage.** The other failed/HOLD gates independently prevent promotion. No deployment or production wiring is authorized.

## Decision

- **PASS:** all gates pass on frozen evidence.
- **HOLD:** evidence is incomplete, rights remain research-only, or any required gate/model/lane is missing or fails.
- **REJECT:** publication-date provenance, leakage, no-text boundaries, final-test integrity, or construct language is invalid.

## Frozen v1 disposition correction

- [x] The prior `PASS` was withdrawn; the regenerated final packet and model card say `HOLD` and select no model.
- [x] Valid publisher/domain-held-out primary metrics are preserved separately from promotion eligibility.
- [x] Source-, topic-, author-held-out, and random-diagnostic metrics are marked `invalid_for_selection` because critical review found 62%–67% primary-training-document reuse and the committed package cannot reproduce an exact zero-overlap audit without frozen primary train IDs.
- [x] Unsupported declared historical-placebo files are reported without substituting primary/core rows; lift and lift-CI values remain unavailable.
- [x] The encoder remains `SMOKE-HOLD`; severe source/month collapses and all frozen BBC/multisource external `HOLD` results are promotion blockers.
- [x] Strict artifact/model ID/threshold/training identity/split identity/SHA-256 assertions pass for the reviewed lexical artifact before any copy decision.
- [x] The stale selected-artifact copy was removed from the final package because a `HOLD` cannot freeze a selected release artifact.
- [ ] Leakage-safe alternate lanes, supported placebo lift with CI, full encoder or measured hardware HOLD, subgroup robustness, external gates, and rights clearance remain unresolved.

Current frozen v1 disposition: **HOLD — research-only, no selected model, no production authorization.** This score does not establish AI authorship.