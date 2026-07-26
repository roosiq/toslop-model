# Publication Shift Lexical Baseline v1

**Model ID:** `publication-shift-lexical-v1-8bfb37991329`
**Decision:** **HOLD — research artifact only**
**Score:** `current_era_similarity`
**Required interpretation:** Similarity to matched current-era academic publication language.

> This score does not establish AI authorship.

## What was trained

A deterministic text-only logistic-regression baseline over:

- word TF-IDF 1–3 grams;
- character TF-IDF 3–5 grams;
- balanced class weights;
- vocabulary and IDF fitted on the training partition only;
- validation-selected decision threshold `0.4301355210826429`.

The model receives normalized abstract text only. Publication year, source, publisher, topic, author, DOI, OpenAlex ID, provenance, and the existing Toslop authorship score are not supplied as metadata features.

Training labels:

- pre-LLM era: 2018–2021;
- current era: 2023–2025.

Excluded from model fitting:

- historical placebo: 2014–2017;
- transition lane: 2022;
- forward lane: January–July 2026, balanced across months.

## Real corpus

The executed OpenAlex pilot contains 47,000 accepted English abstracts after global work-ID, DOI, exact-text, and deterministic near-duplicate-cluster deduplication:

| Lane | Rows |
|---|---:|
| Historical placebo, 2014–2017 | 8,000 |
| Pre-LLM core, 2018–2021 | 20,000 |
| Transition, 2022 | 2,000 |
| Current core, 2023–2025 | 15,000 |
| Forward, Jan–Jul 2026 | 2,000 |

The 2026 lane contains 286 rows/month for January–June and 284 for July.

## Primary held-out result

The primary source/publisher-held-out lane has zero source, publisher, work-ID, DOI, exact-text-hash, or near-duplicate-cluster overlap.

| Metric | Result |
|---|---:|
| Train / validation / test | 19,938 / 4,243 / 10,819 |
| ROC-AUC | 0.7938 |
| Grouped-bootstrap ROC-AUC 95% CI | 0.7842–0.8345 |
| PR-AUC | 0.8111 |
| Balanced accuracy | 0.7097 |
| F1 | 0.6928 |
| Brier score | 0.1791 |
| ECE | 0.0339 |
| Masked-content ROC-AUC | 0.7726 |

A separately retrained author-held-out lane reached ROC-AUC 0.8432 on 518 test rows, with ECE 0.1130. That calibration miss is one reason this remains a research artifact.

## Historical placebos

| Placebo | Test ROC-AUC |
|---|---:|
| 2014–2017 vs. 2018–2021 | 0.6459 |
| 2016–2018 vs. 2019–2021 | 0.6034 |

The primary test ROC-AUC exceeds the strongest historical placebo by 0.1479. The grouped-bootstrap 95% interval for this lift is 0.0835–0.1982.

## Transition and forward distributions

| Lane | Mean score | Median score |
|---|---:|---:|
| 2022 transition | 0.4580 | 0.4372 |
| Jan–Jul 2026 forward | 0.6439 | 0.6751 |

These are score distributions, not ground-truth authorship rates.

## Frozen artifact

- Joblib: `services/gateway/model_artifacts/publication_shift/publication_shift_lexical_v1.joblib`
- Size: 2,929,277 bytes
- SHA-256: `f47c35fa033a61600ee2fc2957bfdbd9b1db7d47c7a212d539378fc7deaf1d7a`
- Metadata: `model_metadata.json`
- Metrics: `metrics.json`
- No-text predictions: `heldout_predictions.jsonl`, `transition_2022_predictions.jsonl`, `forward_2026_predictions.jsonl`
- Checksums: `checksums.sha256`

## Why HOLD

This pilot clears the preregistered primary discrimination, calibration, masked-content, and placebo-lift gates. It is still **HOLD** because the full 252,000-row planned corpus and all preregistered candidate model families are not complete. The artifact must not replace or be blended into the existing Toslop authorship model without a separate reviewed release decision.
