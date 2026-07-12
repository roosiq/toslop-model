# Acceptance criteria: LLM-era publication shift model

A candidate is not promotable unless every required gate passes. Missing evidence is a failure, not permission to weaken or skip the gate.

## Data and provenance

- [ ] At least 252,000 cleaned core abstracts are present: at least 36,000 per year for 2018–2021 and 2023–2025.
- [ ] 2022 is excluded from training, calibration, and threshold selection and retained as a transition evaluation.
- [ ] Incomplete 2026 data is excluded from training and evaluated only with month-matched historical/current controls.
- [ ] Historical placebo data covers 2014–2021; placebo, transition, and forward rows are additional to the core count.
- [ ] Every row has a valid OpenAlex work ID, actual `publication_date`, English-language contract, reconstructed abstract, word count of at least 150, and pinned retrieval/source-manifest identity.
- [ ] Requested/accepted/rejected counts, date parse failures, missing abstracts, topic/source concentration, and length distributions are reported by year and month.
- [ ] Raw abstract text exists only under ignored local data paths with restrictive permissions and never appears in public reports, predictions, manifests, docs, or checksums.

## Deduplication and split hygiene

- [ ] Exact work ID, DOI, normalized-text hash, and near-duplicate cluster overlap is zero across every train/validation/test protocol.
- [ ] Feature extraction and chunking occur only after document assignment.
- [ ] Author-held-out evaluation assigns authors before works and excludes bridge works that would cross partitions.
- [ ] Source/journal-, publisher-, topic-, and author-held-out lanes are explicit and reproducible.
- [ ] Same-author pre/post evidence is reported separately and does not substitute for author-held-out evaluation.
- [ ] Random document split results are labeled diagnostic and never used alone for promotion.

## Runtime-feature boundary

- [ ] Runtime input is passage text only.
- [ ] Source, publisher, journal, topic, author, publication date/year, DOI, URL, OpenAlex ID, dataset identity, and provenance are excluded from model features and routing.
- [ ] No existing Toslop authorship score, label, model output, threshold, or artifact is used as a feature.
- [ ] Source-only and metadata-only baselines and shortcut diagnostics are reported.

## Required models and experiments

- [ ] Reproducible word/character TF-IDF logistic baseline is complete.
- [ ] Reproducible stylometric LightGBM or CatBoost candidate is complete.
- [ ] Reproducible multi-task ModernBERT or DeBERTa candidate is complete for era classification, year regression, and pairwise recency ranking.
- [ ] Each model is evaluated on source-, publisher-, topic-, and author-held-out lanes; same-author pairs; 2022 transition; month-matched 2026 forward data; historical placebos; length strata; and masked content.
- [ ] Named entities, dates, numbers, URLs, citations, explicit AI terminology, and topic-specific nouns are masked in the robustness evaluation.
- [ ] Top lexical coefficients, stylometric importances, and neural attribution probes are inspected for source/topic/year/extraction shortcuts.

## Performance and calibration

On the frozen publisher-held-out primary lane:

- [ ] ROC-AUC is greater than `0.75`.
- [ ] Expected calibration error is less than `0.08`.
- [ ] ROC-AUC, PR-AUC, balanced accuracy, F1, Brier score, ECE, calibration curves, and grouped-bootstrap 95% confidence intervals are reported.
- [ ] Masked-content ROC-AUC remains above `0.70`, loses less than `0.10` absolute ROC-AUC versus unmasked evaluation, and still clears the historical-placebo claim gate.
- [ ] No required topic, publisher, source, year, or passage-length subgroup is omitted; severe collapses are promotion blockers even if pooled metrics pass.

## Historical-shift claim gate

- [ ] Placebos include matched 2014–2017 vs 2018–2021 and 2016–2018 vs 2019–2021 comparisons.
- [ ] The 2023–2025 versus 2018–2021 ROC-AUC exceeds the strongest matched historical-placebo ROC-AUC by at least `0.05`.
- [ ] The grouped-bootstrap 95% confidence interval for that main-minus-placebo lift has a lower bound above zero.
- [ ] The claim survives masking and source/topic/length matching.
- [ ] If these conditions fail, output is **HOLD** and may be described only as ordinary temporal/domain drift—not an unusual LLM-era publication shift.

## Ensemble and explanations

- [ ] Calibration and ensemble fitting use validation data only; final lanes remain unopened until frozen evaluation.
- [ ] Every ensemble component independently passes confound diagnostics.
- [ ] The ensemble beats the strongest passing individual component by the predeclared metric margin; otherwise the ensemble is rejected.
- [ ] Explanations identify specific linguistic characteristics and do not expose source metadata or imply causal AI authorship.
- [ ] User-facing labels and fields use `temporal_style_score`, `current_era_similarity`, or `LLM_era_shift_score`; they never use `AI probability`.
- [ ] Every output states: “This score does not establish AI authorship.”

## Reproducibility and artifact identity

- [ ] Source/request manifest, corpus schema, split/matching manifests, feature configuration, vocabulary hashes, model/tokenizer revisions, seeds, calibration object, thresholds, no-text predictions, metrics, environment, and hardware are frozen.
- [ ] Selected artifacts have recorded SHA-256 checksums and pass `sha256sum -c metadata/artifact_checksums.sha256`.
- [ ] A fresh pilot reproduction and a frozen-model inference probe return the declared model ID and expected schema.
- [ ] Focused tests pass without network access; separate integration tests prove a real OpenAlex API path.
- [ ] The complete pipeline is demonstrated on the Ryzen AI Max 395 with 128 GB memory.

## Isolation and operational safety

- [ ] Existing authorship detector files, model IDs, thresholds, outputs, and production behavior are unchanged.
- [ ] No private backend or public Worker deploy occurs from this change.
- [ ] No unrelated dirty work from the primary worktree is incorporated.

## Decision semantics

- **PASS:** every required gate passes on frozen artifacts.
- **HOLD:** any required gate is missing or fails; the artifact remains research-only.
- **REJECT:** leakage, raw-text exposure, invalid provenance, final-test tuning, source routing, or misleading authorship language invalidates the run and requires a clean rebuild.