# Tasks: INFINI-NEWS publication-shift scale

## Phase 0 — source contract and real pilot

1. Implement `build_publication_shift_infini_news_corpus.py` with pinned revision/file identities, selective Parquet streaming, actual `publish_date` parsing, independent WARC-date audit, explicit-English validation, minimum length, source caps, global dedupe, restrictive local writes, resumable offsets, and no-text reporting.
2. Add focused offline tests using metadata-only/synthetic fixtures; raw source text must not enter fixtures or reports.
3. Run a real bounded pilot across 2016, 2018, 2022, 2025, and January–April 2026 and freeze public-safe evidence.
4. Verify publication-versus-WARC date divergence is preserved and sampling uses publication month only.

## Phase 1 — 264k corpus

1. Freeze the request/shard manifest at revision `5b78199b86a838a5634b2d3267d72b98b8f71721`.
2. Collect the exact year/month target matrix defined in `design.md`.
3. Run global identity, URL, payload, exact-text, and near-duplicate dedupe.
4. Freeze corpus-quality, rights, date-lag, language, length, rejection, and source-concentration reports without text.
5. Verify 252,000 core and 264,000 total accepted rows, file permissions, and ignored status.

## Phase 2 — splits and baselines

1. Freeze publisher/domain-, source-, author-, topic-, and random-diagnostic protocols plus same-author analyses where support is adequate.
2. Prove zero duplicate/identity overlap and exclusion of 2022/2026 from fitting, calibration, and threshold selection.
3. Train full lexical and stylometric candidates from training rows only.
4. Evaluate all held-out, masked, transition, forward, placebo, length, and confound lanes.
5. Save loadable artifacts, no-text predictions, metrics, configs, feature identities, and checksums.

## Phase 3 — multi-task encoder

1. Implement document-first ModernBERT or DeBERTa training with era classification, year regression, and pairwise recency ranking.
2. Pin model/tokenizer revisions, seed, chunking, hardware, and resumable checkpoints.
3. Smoke test, run a serious hardware-feasible candidate, and preserve failed runs honestly.
4. Evaluate on the same frozen protocols without final-test tuning.

## Phase 4 — frozen decision and QA

1. Calibrate on validation only and attempt an ensemble only after component confound gates pass.
2. Run one frozen candidate comparison and generate a no-text gate matrix/model card.
3. Update global checksums only for selected frozen artifacts.
4. Independently load/probe artifacts, recompute metrics, verify corpus/splits/permissions/checksums, and confirm authorship-runtime isolation.
5. Return PASS, HOLD, or REJECT. Do not deploy.
6. [x] Run the deterministic no-text evaluation-integrity audit and freeze its JSON, Markdown, and checksums. It returned **REJECT**: all four alternate test lanes overlap the primary model training IDs; both named placebo contrasts have no later-arm support; the encoder is a 160-row CPU smoke only; and four source groups plus two publication months fall below 70% accuracy.

Disposition correction completed without retraining or tuning: the finalizer now applies all required global gates, preserves only the primary lane as valid selection evidence, labels overlapping alternate lanes diagnostic-only, rejects substituted placebo evidence, validates exact artifact identity before a possible freeze, and emits `HOLD` with no selected/frozen release artifact on the current evidence. Remaining research work is to produce new leakage-safe alternate evaluations, supported placebo lift/CI, adequate encoder evidence, robust subgroups, passing external validation, and rights clearance.

## Verification baseline

```bash
PYTHONPATH=services/gateway python -m pytest services/gateway/tests/test_publication_shift_infini_news_corpus.py -q
PYTHONPATH=services/gateway python services/gateway/build_publication_shift_infini_news_corpus.py --help
sha256sum -c metadata/artifact_checksums.sha256
git diff --check
git status --short --branch
```

Every public result must state: **This score does not establish AI authorship.**