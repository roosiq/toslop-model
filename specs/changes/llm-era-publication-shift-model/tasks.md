# Tasks: LLM-era publication shift model

## Phase 0 — source contract and vertical slice

1. Create `services/gateway/build_publication_shift_openalex_corpus.py` with typed source/schema contracts, deterministic abstract reconstruction, strict date/language/type/length validation, cursor pagination, API-key support, bounded retries, local-only text writes, and no-text manifests.
2. Add `services/gateway/tests/test_publication_shift_openalex_corpus.py` covering reconstruction order, invalid dates, partial 2026 role assignment, schema drift, quota errors, restrictive permissions, dedupe, and raw-text exclusion from reports.
3. Add a pinned pilot request manifest under `services/evals/publication_shift_model/openalex_pilot/` and collect a deterministic small sample from each required corpus role.
4. Verify the pilot’s year/month/topic/source distributions, parse/rejection rates, text hashes, and exact/near-duplicate counts without committing text.
5. Add `services/gateway/build_publication_shift_splits.py` and leakage tests for work ID, DOI, text hash, near-duplicate cluster, author-held-out, and source/publisher-held-out protocols.
6. Add `services/gateway/train_publication_shift_lexical.py`; run a small masked/unmasked lexical smoke baseline to expose obvious metadata or extraction leakage.

Verification:

```bash
PYTHONPATH=services/gateway python -m pytest \
  services/gateway/tests/test_publication_shift_openalex_corpus.py \
  services/gateway/tests/test_publication_shift_splits.py -q

PYTHONPATH=services/gateway python services/gateway/build_publication_shift_openalex_corpus.py \
  --pilot --output-root services/data/publication_shift/openalex_pilot \
  --report services/evals/publication_shift_model/openalex_pilot/report.json

PYTHONPATH=services/gateway python services/gateway/train_publication_shift_lexical.py \
  --corpus services/data/publication_shift/openalex_pilot \
  --output services/evals/publication_shift_model/lexical_pilot
```

Exit Phase 0 only when tests pass, the API probe is real, local raw text is ignored/restricted, audit outputs contain no text, and split overlap is zero.

## Phase 1 — reproducible corpus build

1. Freeze the OpenAlex request/source manifest, schema version, collection seed, target strata, and access/quota assumptions.
2. Collect and normalize at least 36,000 accepted documents per core year for 2018–2021 and 2023–2025.
3. Collect separate 2014–2017 placebo, 2022 transition, and month-matched 2026 forward lanes.
4. Run global exact/near dedupe, matching, and all group-safe split builders before any feature extraction.
5. Save no-text manifests and corpus-quality reports; verify raw text is absent from git status.

Verification:

```bash
PYTHONPATH=services/gateway python services/gateway/build_publication_shift_openalex_corpus.py \
  --manifest services/evals/publication_shift_model/openalex_source_manifest.json \
  --output-root services/data/publication_shift/openalex_v1 \
  --report services/evals/publication_shift_model/openalex_v1/report.json

PYTHONPATH=services/gateway python services/gateway/build_publication_shift_splits.py \
  --corpus services/data/publication_shift/openalex_v1 \
  --output services/evals/publication_shift_model/openalex_v1/splits

PYTHONPATH=services/gateway python -m pytest services/gateway/tests/test_publication_shift_ -q
```

## Phase 2 — lexical and stylometric baselines

1. Train word/character TF-IDF logistic models from training rows only.
2. Add `services/gateway/extract_publication_shift_stylometry.py` with versioned, deterministic features and focused tests.
3. Train LightGBM and CatBoost candidates with training-only preprocessing.
4. Evaluate random-diagnostic, source-, publisher-, topic-, and author-held-out lanes; same-author pairs; masking; 2022; 2026; and historical placebos.
5. Save coefficients/importances, no-text predictions, metrics, configs, and checksums.

Verification:

```bash
PYTHONPATH=services/gateway python -m pytest \
  services/gateway/tests/test_publication_shift_stylometry.py \
  services/gateway/tests/test_publication_shift_evaluation.py -q

PYTHONPATH=services/gateway python services/gateway/train_publication_shift_lexical.py --config services/evals/publication_shift_model/configs/lexical_v1.json
PYTHONPATH=services/gateway python services/gateway/train_publication_shift_stylometric.py --config services/evals/publication_shift_model/configs/stylometric_v1.json
```

## Phase 3 — neural multi-task encoder

1. Add `services/gateway/train_publication_shift_encoder.py` with document-first splitting, chunking, three objectives, resumable checkpoints, and pinned model/tokenizer revisions.
2. Smoke test a small encoder and confirm chunk aggregation and no final-test access.
3. Train serious ModernBERT and/or DeBERTa candidates within the local hardware constraint.
4. Run the same frozen evaluation lanes and shortcut diagnostics as the baselines.
5. Retain failed candidates and metrics as evidence; do not rewrite gates around results.

Verification:

```bash
PYTHONPATH=services/gateway python -m pytest services/gateway/tests/test_publication_shift_encoder.py -q
PYTHONPATH=services/gateway python services/gateway/train_publication_shift_encoder.py --config services/evals/publication_shift_model/configs/encoder_v1.json
```

## Phase 4 — calibration, ensemble, and frozen decision packet

1. Select calibration method and any decision thresholds using validation only.
2. Fit a simple component ensemble only if individual models pass confound diagnostics.
3. Require the ensemble to improve over the strongest individual model; otherwise promote the strongest passing component or HOLD.
4. Run one frozen final evaluation and generate a no-text decision packet with all gates, uncertainty intervals, subgroup results, model identity, artifact paths, and checksums.
5. Update `metadata/source_revisions.json` and `metadata/artifact_checksums.sha256` only for the selected frozen artifact.

Verification:

```bash
PYTHONPATH=services/gateway python services/gateway/evaluate_publication_shift_model.py \
  --config services/evals/publication_shift_model/configs/final_v1.json \
  --output services/evals/publication_shift_model/final_v1

sha256sum -c metadata/artifact_checksums.sha256
```

## Phase 5 — product integration, only after PASS

1. Add an isolated runtime loader in `services/gateway/app/publication_shift_model.py` with model-ID and checksum validation.
2. Add API schema and route tests using temporal-style language and the mandatory non-authorship limitation.
3. Verify real local inference on pre-LLM, transition/mixed, and current-era passages.
4. Write the public methods note from frozen evidence.
5. Open a separate production/deployment change; do not deploy from this research branch.

## HOLD rule

Any missing required lane, leakage, raw-text artifact, confound failure, unmet metric/calibration/placebo gate, checksum mismatch, or partial artifact identity results in **HOLD**. Continue research without changing authorship production behavior or presenting the candidate as a validated LLM-era shift model.