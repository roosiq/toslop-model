# Toslop Model Replication

This repository contains the public replication package for the Toslop AI-likely writing score.

It is intentionally smaller than the private infrastructure monorepo. It includes the detector code, training scripts, frozen model artifacts, evaluation summaries, source revision pins, and checksums needed to reproduce the scoring-method article. It does not include local `.env` files, unrelated infrastructure, or raw dataset text.

## What Is Included

- `docs/toslop-scoring-model-and-accuracy.md`: the public methods article.
- `docs/xgboost-feature-path-experiments.md`: optional XGBoost feature-path experiment notes.
- `services/gateway/app/corporate_markov_features.py`: surface Markov matrix implementation.
- `services/gateway/app/corporate_ai_authorship_feature_spike.py`: feature extraction, linear baseline, prediction, and evaluation helpers.
- `services/gateway/app/corporate_authorship_detector.py`: runtime detector wrapper used by Toslop.
- `services/gateway/scripts_build_authorship_corpus_v2.py`: deterministic v2 corpus builder.
- `services/gateway/run_authorship_corpus_v2_markov_everything.py`: ablation and model-training runner.
- `services/gateway/model_artifacts/corporate_authorship/`: frozen production candidate artifacts.
- `services/evals/corporate_sequence_model/**/method_comparison.json`: saved evaluation reports used by the article tables, including the current defensive HC3 and XGBoost candidate reports.
- `metadata/source_revisions.json`: pinned source dataset revisions and source-file hashes.
- `metadata/artifact_checksums.sha256`: checksums for committed replication artifacts and generated split artifacts from the original run.

## What Is Not Included

The repository does not redistribute the full source corpora or Toslop's generated JSONL train/test/calibration splits. Those files contain source dataset text. Reproduce them by downloading the pinned Hugging Face revisions and running the scripts below.

## Reproduce The Model

Install dependencies. The promoted model uses XGBoost for training; runtime scoring only needs the committed JSON artifacts.

```bash
python -m venv .venv
. .venv/bin/activate
pip install pandas pyarrow nltk huggingface_hub scipy xgboost
python -m nltk.downloader averaged_perceptron_tagger_eng
```

Download pinned source datasets:

```bash
./scripts/download_sources.sh
```

Normalize the Ateeqq, silentone, harsh/human-vs-llm, and optional sunorme raw-text sources:

```bash
PYTHONPATH=services/gateway \
  python services/gateway/app/corporate_corpus_ingest.py \
  --hf-root services/data/hf-corpora \
  --normalized-output services/evals/corporate_sequence_model/hf_normalized_corpus.jsonl \
  --max-docs-per-source 5000
```

Clean the normalized authorship corpus:

```bash
cd services/gateway

python scripts_clean_corporate_authorship_corpus.py \
  --input ../evals/corporate_sequence_model/hf_normalized_corpus.jsonl \
  --output ../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1.jsonl \
  --rejected ../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1_rejected.jsonl \
  --report ../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1_report.json \
  --min-words 30 \
  --max-words 900 \
  --test-ratio 0.25
```

Build the v2 train/test/calibration splits:

```bash
python scripts_build_authorship_corpus_v2.py \
  --min-words 80 \
  --max-words 900 \
  --supervised-test-ratio 0.25 \
  --andy-existing-ratio 3.0 \
  --output-dir ../evals/corporate_sequence_model/authorship_corpus_v2
```

Train and evaluate the current defensive HC3 XGBoost candidate:

```bash
python run_authorship_corpus_v2_markov_everything.py \
  --output ../evals/corporate_sequence_model/authorship_corpus_v2_xgboost_core_candidate \
  --min-frequency 8 \
  --max-features 30000 \
  --methods lexical_shape_plus_core_markov \
  --trainer xgboost \
  --xgboost-rounds 350 \
  --xgboost-max-depth 4 \
  --xgboost-eta 0.06 \
  --xgboost-subsample 0.9 \
  --xgboost-colsample-bytree 0.85 \
  --xgboost-min-child-weight 2.0 \
  --xgboost-reg-lambda 1.0 \
  --xgboost-reg-alpha 0.0 \
  --defensive-calibration-train-ratio 0.25 \
  --defensive-calibration-wiki-max-per-label 1800 \
  --defensive-calibration-qa-max-per-label 450 \
  --export-edge-candidate lexical_shape_plus_core_markov_xgboost \
  --edge-threshold 0.6
```

This run starts from the same supervised v2 train/test split, deterministically moves a capped 25% per-label slice of HC3 wiki and HC3 QA rows into training, and evaluates on the remaining HC3 holdout rows with a zero-overlap hash audit. The operating target is AI recall greater than 80% and human false-positive rate below 20% on the supervised test, HC3 wiki holdout, and HC3 QA holdout. Compare generated files with `metadata/artifact_checksums.sha256`.

## Linear Baseline

The previous production artifact was a linear JSON model on
`lexical_shape_plus_markov`. It remains useful as a baseline and rollback path:

```bash
cd services/gateway
python run_authorship_corpus_v2_markov_everything.py \
  --output ../evals/corporate_sequence_model/authorship_corpus_v2_defensive_hc3_candidate \
  --min-frequency 8 \
  --max-features 30000 \
  --methods lexical_shape_plus_markov \
  --trainer lr \
  --epochs 160 \
  --defensive-calibration-train-ratio 0.25 \
  --defensive-calibration-wiki-max-per-label 1800 \
  --defensive-calibration-qa-max-per-label 450 \
  --export-edge-candidate lexical_shape_plus_markov \
  --edge-threshold 0.6
```

The linear model remains in `services/gateway/model_artifacts/corporate_authorship/`.
The promoted XGBoost path is documented in
`docs/xgboost-feature-path-experiments.md`; it was chosen because it materially
reduced HC3 human false positives while preserving AI recall above the published
operating target.

## Publication Note

This repo is the intended public artifact. Do not make the private `slopslingers-infra` repo public without a separate security and licensing audit.
