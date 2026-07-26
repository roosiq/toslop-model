# Design

## Frozen subject

- Model ID: `infini-news-lexical_tfidf_logistic-v1-cca5838ac34f`
- Artifact SHA-256: `0ca8956726b101fd585ff663caf4119e4911d3ec2789cf25fab415669691d403`
- Threshold: `0.49690983649044096`
- INFINI final commit: `a31983b5653a8382840d4976756e6b08319ee5cc`

The evaluator must fail if model ID, artifact hash, threshold, vectorizer configuration, or selected-candidate metadata differs.

## January 2024 diagnostic

Read the frozen publisher/domain-held-out predictions. Compare January 2024 against December 2023, the remainder of 2024, and the overall test using only:

- hashed source/domain and author identifiers,
- topic,
- word-count bands,
- score distributions,
- error counts,
- duplicate-cluster IDs,
- missing-author status.

Do not inspect or publish article text. Do not alter v1.

## External corpus contract

Required fields:

- article body text,
- actual article publication timestamp/date,
- stable source/domain identity,
- stable article URL or source record ID,
- provenance and source revision/snapshot.

Reject records whose only temporal identity is crawl, WARC, archive, upload, or partition date. Normalize to UTC date, English-only, minimum 150 words, and globally deduplicate normalized URL, normalized-text SHA-256, and near-duplicate cluster.

Target windows:

- pre-LLM: 2018-01 through 2021-12, label 0;
- current era: 2023-01 through 2025-12, label 1;
- 2022 and 2026 remain evaluation-only if available.

Prefer month balance and a per-source-month cap. Raw text stays in a private local JSONL/SQLite artifact; public records contain document IDs, hashes, dates, source hashes, labels, scores, and diagnostics only.

## Evaluation

Use the unchanged artifact and threshold. Report:

- ROC-AUC, PR-AUC, accuracy, balanced accuracy, F1, Brier, and 10-bin ECE;
- specificity/FPR for pre-LLM and sensitivity/FNR for current era;
- year/month metrics with one-class semantics stated explicitly;
- source/topic/length/missing-author slices;
- masked-text evaluation where the same deterministic masking transform is applicable;
- source-only shortcut diagnostic when metadata support permits it;
- grouped bootstrap confidence intervals by source/domain.

## Gates

Full external PASS requires:

- ROC-AUC >= 0.85;
- balanced accuracy >= 0.80;
- masked ROC-AUC >= 0.75;
- pre-LLM FPR <= 0.15 overall;
- source-only AUC within 0.40–0.60;
- no supported month or major source below 0.70 accuracy without a documented, evidence-backed cause;
- rights/privacy/no-text/checksum/split-integrity gates all pass.

A pilot may end HOLD when sample size or temporal/source coverage is insufficient. It may not be called PASS.

## PR boundary

The PR packages research code, model artifacts, no-text evidence, specs, and tests. It does not deploy or wire production scoring.
