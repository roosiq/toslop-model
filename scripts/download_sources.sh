#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_DEST="$ROOT/services/data/hf-corpora/ai_human_detection"
CORP_DEST="$ROOT/services/data/hf-corpora/corporate_speak"

command -v huggingface-cli >/dev/null 2>&1 || {
  echo "huggingface-cli is required. Install with: pip install huggingface_hub" >&2
  exit 1
}

download_dataset() {
  local repo_id="$1"
  local revision="$2"
  local local_name="$3"
  local dest_root="$4"
  shift 4
  mkdir -p "$dest_root/$local_name"
  huggingface-cli download "$repo_id" "$@" \
    --repo-type dataset \
    --revision "$revision" \
    --local-dir "$dest_root/$local_name"
}

download_dataset \
  "andythetechnerd03/AI-human-text" \
  "0387d82c81d6af6caaa6d792b48c9d07afa704d7" \
  "andythetechnerd03__AI-human-text" \
  "$AI_DEST" \
  "data/test-00000-of-00001.parquet" "README.md"

download_dataset \
  "Ateeqq/AI-and-Human-Generated-Text" \
  "e0627b3f39fe0a27725889239067868797a4db40" \
  "Ateeqq__AI-and-Human-Generated-Text" \
  "$AI_DEST" \
  "train.csv" "test.csv" "README.md"

download_dataset \
  "silentone0725/ai-human-text-detection-v1" \
  "a303611a074f8f6736302126e8f06c51273f4562" \
  "silentone0725__ai-human-text-detection-v1" \
  "$AI_DEST" \
  "train.csv" "validation.csv" "test.csv" "README.md"

download_dataset \
  "rajendrabaskota/hc3-wiki-intro-dataset" \
  "58f59eb06ad91e4f8fad1a86d40877661f0d63d9" \
  "rajendrabaskota__hc3-wiki-intro-dataset" \
  "$AI_DEST" \
  "data/test-00000-of-00001-d5b50745903d93eb.parquet"

download_dataset \
  "pszemraj/HC3-textgen-qa" \
  "4cddc2b69948c9dba7ded91ed73f0a2b1a318340" \
  "pszemraj__HC3-textgen-qa" \
  "$AI_DEST" \
  "test.csv"

download_dataset \
  "phxdev/corporate-speak-dataset" \
  "e45ef4962cee017f22dabea6a36d30f04131355b" \
  "phxdev__corporate-speak-dataset" \
  "$CORP_DEST" \
  "data/train-00000-of-00001.parquet" \
  "data/test-00000-of-00001.parquet" \
  "data/validation-00000-of-00001.parquet" \
  "README.md"

echo "Downloaded pinned source datasets under $ROOT/services/data/hf-corpora"
