# Proposal: sealed cross-corpus validation for INFINI publication-shift v1

## Goal

Determine whether `infini-news-lexical_tfidf_logistic-v1-cca5838ac34f` generalizes to independently sourced English news with verified article publication dates, without retraining, threshold changes, source routing, or test-set tuning.

## Why now

The frozen INFINI publisher/domain-held-out test passed, but January 2024 accuracy fell to 60.99%. The next scientific risk is corpus-specific formatting, publisher mix, or archive artifacts.

## Scope

1. Freeze v1 model identity, threshold, and INFINI test evidence.
2. Produce a no-text January 2024 diagnostic using existing frozen predictions only.
3. Select an external dated-news source that is independent of INFINI and OpenAlex.
4. Run a small provenance/date/schema pilot before scaling.
5. Build a deterministic, globally deduplicated external challenge set with balanced pre-LLM (2018–2021) and current-era (2023–2025) rows.
6. Score with the unchanged v1 artifact and generate no-text metrics, time groups, confound diagnostics, predictions, checksums, and PASS/HOLD/REJECT.
7. Package the completed research model and external-validation state in a GitHub PR.

## Non-goals

- No model retraining or calibration.
- No month/source-specific thresholds.
- No Toslop authorship-score features or production wiring.
- No Cloudflare deployment.
- No public raw or normalized article text.
- No claim that the score establishes AI authorship.

## Definition of done

- January 2024 diagnostic identifies the dominant no-text source/topic/length contributors and records whether a data-processing defect exists.
- External source revision and exact article-date field are pinned and verified against examples where crawl/archive dates differ when available.
- At least a real pilot is completed; target full challenge size is 20,000–50,000 if the source permits it without paid credentials or rights ambiguity.
- Unchanged model and threshold are verified by SHA-256 and prediction parity.
- Public artifacts contain hashes/aggregates only; local raw text is mode 0600 under `services/data`.
- Tests/checksums pass and the research PR is opened.

## Mandatory caveat

This score does not establish AI authorship.
