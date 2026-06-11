# Toslop Model Replication

This repository contains the public replication package for the Toslop AI-likely writing score.

It is intentionally smaller than the private infrastructure monorepo. It includes the detector code, training scripts, frozen model artifacts, evaluation summaries, source revision pins, and checksums needed to reproduce the scoring-method article. It does not include local `.env` files, unrelated infrastructure, or raw dataset text.

## What Is Included

- `docs/toslop-scoring-model-and-accuracy.md`: the public methods article.
- `services/gateway/app/corporate_markov_features.py`: surface Markov matrix implementation.
- `services/gateway/app/corporate_ai_authorship_feature_spike.py`: feature extraction, logistic regression, prediction, and evaluation helpers.
- `services/gateway/app/corporate_authorship_detector.py`: runtime detector wrapper used by Toslop.
- `services/gateway/scripts_build_authorship_corpus_v2.py`: deterministic v2 corpus builder.
- `services/gateway/run_authorship_corpus_v2_markov_everything.py`: ablation and model-training runner.
- `services/gateway/model_artifacts/corporate_authorship/`: frozen production candidate artifacts.
- `services/evals/corporate_sequence_model/**/method_comparison.json`: saved evaluation reports used by the article tables.
- `metadata/source_revisions.json`: pinned source dataset revisions and source-file hashes.
- `metadata/artifact_checksums.sha256`: checksums for committed replication artifacts and generated split artifacts from the original run.

## What Is Not Included

The repository does not redistribute the full source corpora or Toslop's generated JSONL train/test/calibration splits. Those files contain source dataset text. Reproduce them by downloading the pinned Hugging Face revisions and running the scripts below.

## Reproduce The Model

Install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install pandas pyarrow nltk huggingface_hub
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

Train and evaluate the model family:

```bash
python run_authorship_corpus_v2_markov_everything.py \
  --output ../evals/corporate_sequence_model/authorship_corpus_v2_lexical_shape_markov_candidate \
  --min-frequency 8 \
  --max-features 30000 \
  --epochs 160 \
  --methods lexical_style,shape_ngrams,shape_ngrams_plus_markov,markov_surface,lexical_shape_plus_markov \
  --export-edge-candidate lexical_shape_plus_markov \
  --edge-threshold 0.6
```

Compare generated files with `metadata/artifact_checksums.sha256`.

## Publication Note

This repo is the intended public artifact. Do not make the private `slopslingers-infra` repo public without a separate security and licensing audit.
