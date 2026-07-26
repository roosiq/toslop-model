# Proposal: LLM-era publication shift model

## Problem

The existing Toslop authorship detector estimates AI-likely writing. It cannot answer a different, narrower question: whether a passage resembles matched publications from before widespread LLM use or publications from the current LLM era. Reusing authorship labels, artifacts, thresholds, or product language would overstate what either model establishes.

## Goal

Build a separate, interpretable temporal-style model for English academic abstracts. It will estimate similarity to matched pre-LLM and current-era publication language, quantify historical placebo shifts, and return calibrated uncertainty without claiming that a specific passage was AI-generated.

Every user-facing result must state: “This score does not establish AI authorship.”

## Initial scope

- Domain: English academic abstracts.
- Source: OpenAlex Works, using actual `publication_date` and reconstructed `abstract_inverted_index`.
- Pre-LLM training era: 2018–2021.
- Transition evaluation only: 2022.
- Current-era training: 2023–2025.
- Forward evaluation: partial-year 2026, month-matched to the same months in prior years until 2026 is complete.
- Historical placebos: matched comparisons spanning 2014–2021.
- Minimum accepted abstract length: 150 words.
- Core training/evaluation corpus: at least 250,000 cleaned documents; transition, placebo, and forward-evaluation rows are additional.

## Hypothesis

After matching and controlling for topic, source, author, document type, length, dates, entities, citations, and explicit AI terminology, the 2023–2025 separation from 2018–2021 will be materially stronger than comparable pre-LLM historical separations. Failure to show that difference results in **HOLD**, not an “LLM-era shift” claim.

## Non-goals

- Do not infer or label AI authorship.
- Do not replace, recalibrate, ensemble with, or change the existing Toslop authorship detector.
- Do not use a generative LLM as the primary classifier.
- Do not treat OpenAlex metadata quality or publication year as ground-truth evidence of LLM use.
- Do not use source, publisher, journal, topic, author, year, DOI, URL, dataset identity, or provenance as runtime model features.
- Do not expose or commit downloaded abstract text in public manifests, reports, predictions, checksums, or documentation.
- Do not deploy or alter the private production backend or public Worker in this change.

## Approach

1. Define and test a pinned OpenAlex source contract, local raw-text boundary, normalized record schema, and no-text manifest.
2. Build a deterministic pilot that proves abstract reconstruction, date handling, deduplication, balancing, and leakage diagnostics before scaling.
3. Establish lexical and stylometric baselines before neural training.
4. Fine-tune a small multi-task encoder for era classification, publication-year regression, and matched-pair recency ranking.
5. Evaluate source-, topic-, and author-held-out lanes; masked-content robustness; 2022 transition behavior; 2026 forward behavior; and historical placebos.
6. Calibrate and ensemble only on validation data and only after individual components pass confound diagnostics.
7. Freeze model artifacts, split manifests, metrics, provenance, and checksums before any product-integration proposal.

## Affected paths

- `specs/changes/llm-era-publication-shift-model/`
- `services/gateway/build_publication_shift_openalex_corpus.py`
- `services/gateway/train_publication_shift_*.py`
- `services/gateway/evaluate_publication_shift_model.py`
- `services/gateway/app/publication_shift_model.py`
- `services/gateway/tests/test_publication_shift_*.py`
- `services/data/publication_shift/` for ignored local raw/normalized text
- `services/evals/publication_shift_model/` for public-safe no-text evaluation artifacts
- `services/gateway/model_artifacts/publication_shift/` for frozen artifacts
- `metadata/source_revisions.json` and `metadata/artifact_checksums.sha256` only when artifacts are frozen
- `docs/` only after evidence supports a public methods note

## Must not change

- Existing authorship model behavior, artifacts, IDs, thresholds, API output, or evaluation claims.
- `/home/ryan/slopslingers-infra` production model files or services.
- Public site/Worker behavior.
- Existing unrelated dirty work in the primary worktree.
- Raw-corpus redistribution boundaries.

## Decision state

This proposal authorizes an incremental local research build. Promotion remains **HOLD** until every gate in `acceptance.md` passes with frozen, auditable artifacts.