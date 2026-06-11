# How Toslop Scores AI-Likely Writing

Toslop measures how much AI-shaped writing appears in the public web crawl it watches. The number on the site is not produced by asking a general-purpose language model to judge a page. It comes from a small, deterministic authorship model trained to distinguish human-written text from AI-generated text using surface evidence in the writing itself.

That distinction matters. LLM-as-judge systems can be useful for qualitative review, but they are expensive, slower to run at crawl scale, and harder to reproduce. Toslop needs something closer to an instrument: the same input should produce the same score, the model should be cheap enough to run repeatedly, and the score should expose enough evidence to audit why it moved.

The current Toslop score uses the Corporate Slop authorship detector, specifically the `lexical_shape_plus_markov` candidate model. It turns a text sample into deterministic features, runs a logistic regression model, and reports the model's AI-generated probability as a 0-100 score.

## What The Score Means

The score is a likelihood-style measurement, not proof of authorship. A score of 80 means the model found strong AI-like authorship signals in that text. A score of 20 means the text looked more like the human-written side of the training data. A score near the middle means the evidence is mixed or weak.

For binary labels, the deployed detector uses a conservative threshold of `0.6`: probabilities at or above 60% are labeled `ai_generated`, and lower probabilities are labeled `human_written`. That threshold was chosen to reduce false AI accusations. Toslop also publishes aggregate measurements such as average score and AI-likely share; those are crawl-level summaries, not judgments about individual authors.

Long pages are handled by chunking. The detector was trained mostly on examples between 80 and 900 words, so Toslop splits extracted article text into roughly article-section chunks, uses normal chunks around 100-320 words for real-world calibration, and hard-caps normal production chunks around 600 model words. Each chunk is scored independently, then Toslop stores a word-weighted page score. That keeps a long article from being treated as one giant out-of-distribution sample.

## The Short Version

The production model is:

- model family: standardized logistic regression;
- primary method: `lexical_shape_plus_markov`;
- training rows: 21,005;
- supervised test rows: 8,993;
- calibration rows: 15,446 HC3 wiki rows and 3,618 HC3 QA rows;
- feature cap: 12,000;
- minimum feature frequency: 8;
- epochs: 160;
- learning rate: 0.1;
- L2 penalty: 0.02;
- production threshold: 0.6.

At the default 0.5 evaluation threshold, the combined model reached 97.93% accuracy on the held-out supervised test split. At Toslop's deployed 0.6 threshold, it reached 97.94% accuracy, with a 2.10% human false-positive rate and 97.99% AI recall.

## Training Data

The supervised training corpus was built from public AI/human authorship datasets and then filtered aggressively. The v2 corpus accepted 29,998 supervised examples, split into 21,005 training rows and 8,993 held-out supervised test rows. The split was deterministic and hash-audited: the saved report shows zero train/test overlap hash groups.

The supervised mix came from four sources:

- [`andythetechnerd03/AI-human-text`](https://huggingface.co/datasets/andythetechnerd03/AI-human-text), an Apache-2.0 Hugging Face dataset derived from a Kaggle AI-vs-human text dataset;
- [`Ateeqq/AI-and-Human-Generated-Text`](https://huggingface.co/datasets/Ateeqq/AI-and-Human-Generated-Text), an MIT-licensed AI/human academic abstract dataset;
- [`silentone0725/ai-human-text-detection-v1`](https://huggingface.co/datasets/silentone0725/ai-human-text-detection-v1), a CC BY 4.0 combined AI/human detection corpus.
- [`harsh4248/human_vs_llm`](https://huggingface.co/datasets/harsh4248/human_vs_llm), a labeled title-only human-vs-LLM corpus (mapped so `human` is human and all other model tags are treated as AI-generated).

An additional unlabeled text corpus, [`sunorme/human-vs-llm-text-corpus`](https://huggingface.co/datasets/sunorme/human-vs-llm-text-corpus), is available as optional raw text but is not currently included in the supervised mix because it does not provide explicit binary labels.

Two additional HC3-derived sets were kept as calibration data rather than training data:

- 15,446 rows from [`rajendrabaskota/hc3-wiki-intro-dataset`](https://huggingface.co/datasets/rajendrabaskota/hc3-wiki-intro-dataset);
- 3,618 rows from [`pszemraj/HC3-textgen-qa`](https://huggingface.co/datasets/pszemraj/HC3-textgen-qa), an Apache-2.0 dataset.

The builder rejected 4,999 v2 candidate rows after loading the primary sources. The largest rejection reasons were `too_short` (3,899), `placeholder_url` (440), `too_long` (423), `exact_duplicate` (176), `assistant_artifact` (125), and `url_heavy` (113). Exact duplicates were detected with a normalized SHA-256 text hash.

In the current committed run, the earlier normalized-corpus stage accepted 14,901 rows from 25,000 normalized inputs. It intentionally rejected the `phxdev/corporate-speak-dataset` rows as `corporate_speak_label_shortcut`, because those examples are useful for studying corporate slop style but too label-leaky for authorship training.

## Corpus Construction

The corpus pipeline has three reproducible stages.

First, downloaded Hugging Face files are normalized into a common JSONL schema. The normalizer reads Ateeqq CSV rows, silentone CSV rows, `harsh4248` title rows, optional `sunorme` raw chunks, and optional corporate-speak rows, then emits fields such as `doc_id`, `dataset`, `source_type`, `domain`, `doc_type`, and `text`.

Second, the normalized authorship corpus is cleaned. Rows are rejected if they are empty, too short, too long, URL-heavy, duplicate, mostly punctuation, mostly uppercase, repeated-token junk, or contain obvious assistant artifacts. At this stage, corporate-speak rows are excluded from supervised truth.

Third, the v2 corpus builder combines the clean Ateeqq/silentone/harsh title pool with the Andy dataset and keeps HC3 as calibration. It applies an Andy-to-existing source ratio target of 3:1, balances labels, and assigns train/test by hash bucket:

```text
bucket = int(text_hash[:8], 16) / 0xffffffff
split = "test" if bucket < 0.25 else "train"
```

Because the split is based on normalized text hash, duplicate text cannot land in both train and test unless the hash audit catches it. The saved report shows `supervised_split_hash_leakage_groups = 0`.

## Features

The final model combines three feature families.

The first family is lexical/style evidence. This includes word unigrams and bigrams, word count, character count, sentence count, punctuation count, average word length, lexical diversity, uppercase-token ratio, punctuation ratio, alpha ratio, and related surface statistics. This family captures much of the obvious signal: repeated function-word patterns, stock transitions, unusually regular sentence structure, and vocabulary distributions that differ between the AI and human sides of the corpus.

The second family is shape n-grams. Instead of looking only at words, the model maps text into abstract sequences: token types, rough part-of-speech-like buckets, and character shapes. For example, it tracks whether a token looks like lowercase text, title case, punctuation, a determiner, a modal, a preposition, or a noun-like word. It also tracks character-level shapes such as lowercase letters, uppercase letters, digits, spaces, and punctuation. These features help the detector see writing rhythm without memorizing only specific phrases.

The third family is the surface Markov layer. This is a set of Markov transition matrices stored in sparse form. The model maps text into several symbolic views and compares how likely those sequences are under AI-trained and human-trained transition matrices. The deployed logistic model uses matrix-derived features from the shape, coarse, true_pos, and motif views. For each view and order, it derives AI cross-entropy, human cross-entropy, total log-likelihood ratio, per-transition log-likelihood ratio, and transition count.

The Markov layer is intentionally shallow. It does not try to understand the document the way a large language model would. It asks a narrower question: does the sequence of surface states move like the AI examples or like the human examples?

## What The Markov Matrices Are

Yes: the model does use Markov matrices. They are not the whole detector, but they are a real part of the deployed `lexical_shape_plus_markov` model.

The Markov artifact lives in `surface_markov_models.json`. It stores each transition matrix as:

- `vocab`: the state labels for that view;
- `transition_counts`: sparse transition rows for `ai_generated` and `human_written`;
- `context_counts`: row totals for `ai_generated` and `human_written`;
- `alpha`: additive smoothing, currently `0.1`.

For an order-1 model, this is a normal transition matrix: `P(next_state | previous_state)`. For example, `shape_order1` has eight states, so it is effectively an 8x8 AI matrix plus an 8x8 human matrix. For an order-2 model, the row key is a two-state context: `P(next_state | previous_state_1, previous_state_2)`.

The stored probability is reconstructed as:

```text
P(next | context, label) =
  (transition_count(label, context -> next) + alpha)
  / (context_count(label, context) + alpha * vocab_size)
```

The artifact contains twelve Markov pairs: `shape`, `coarse`, `posish`, `true_pos`, `motif`, and `semantic`, each at order 1 and order 2. The candidate model trains all twelve, and the final 12,000-feature logistic vocabulary selected 30 direct Markov features from `shape`, `coarse`, `true_pos`, and `motif`. The semantic and posish Markov models remain in the artifact for ablations and compatibility, but their direct `markov::` features were not selected into the production candidate vocabulary.

One actual row from the deployed `shape_order1` matrix is the `WORD` context:

| Matrix | Context | Next state | Count | Smoothed probability |
| --- | --- | --- | ---: | ---: |
| AI | `WORD` | `FUNC` | 621,687 | 0.4518 |
| AI | `WORD` | `WORD` | 529,021 | 0.3844 |
| AI | `WORD` | `LONG` | 110,297 | 0.0801 |
| AI | `WORD` | `SHORT` | 88,937 | 0.0646 |
| Human | `WORD` | `FUNC` | 749,254 | 0.4754 |
| Human | `WORD` | `WORD` | 615,384 | 0.3905 |
| Human | `WORD` | `SHORT` | 123,983 | 0.0787 |
| Human | `WORD` | `LONG` | 61,062 | 0.0387 |

That row shows the kind of signal the Markov layer contributes. After a `WORD` state, AI examples moved into `LONG` nearly twice as often as human examples in this training corpus, while human examples moved into `SHORT` more often. The detector does not use that row directly as a standalone verdict. It scores the whole observed sequence against the AI and human matrices, then passes the resulting likelihood-ratio and cross-entropy features into the logistic regression.

Another row, from `coarse_order1`, shows the abstract rhetorical pattern the model sees:

| Matrix | Context | Next state | Count | Smoothed probability |
| --- | --- | --- | ---: | ---: |
| AI | `ABSTRACT` | `FUNC` | 69,410 | 0.5876 |
| AI | `ABSTRACT` | `CONTENT` | 38,329 | 0.3245 |
| AI | `ABSTRACT` | `PUNCT` | 3,092 | 0.0262 |
| AI | `ABSTRACT` | `ABSTRACT` | 3,089 | 0.0262 |
| Human | `ABSTRACT` | `FUNC` | 44,476 | 0.5918 |
| Human | `ABSTRACT` | `CONTENT` | 23,978 | 0.3190 |
| Human | `ABSTRACT` | `MODAL` | 2,469 | 0.0329 |
| Human | `ABSTRACT` | `PUNCT` | 1,906 | 0.0254 |

The differences are small per transition. That is why the model uses aggregate log-likelihood over the whole sequence. A single transition is weak evidence. A page-length sequence of transitions can be strong evidence.

## How Markov Features Become Model Inputs

For each text sample, the detector converts the text into state sequences. The main views are:

- `shape`: token shape such as `FUNC`, `WORD`, `LONG`, `SHORT`, `CAP`, `ALLCAPS`, `NUM`, and `PUNCT`;
- `coarse`: coarse semantic/rhetorical buckets such as `FUNC`, `CONTENT`, `ABSTRACT`, `MODAL`, `NEG`, `NUM`, `ENTITY`, `PRODUCT`, and `CLAIM_VERB`;
- `motif`: selected two-state rhetorical motifs such as `MODAL_CONTENT`, `ABSTRACT_ABSTRACT`, `NEG_CONTENT`, and `SPECIFIC_ENTITY_CONTENT`.

Each Markov pair computes:

```text
ai_logprob = sum(log P(next | context, ai_generated))
human_logprob = sum(log P(next | context, human_written))
llr_total = ai_logprob - human_logprob
llr_per_transition = llr_total / transition_count
ai_cross_entropy = -ai_logprob / transition_count
human_cross_entropy = -human_logprob / transition_count
```

Those values become numeric features like:

```text
markov::shape::order1::llr_total
markov::shape::order2::llr_per_transition
markov::coarse::order1::ai_cross_entropy
markov::motif::order2::human_cross_entropy
```

The final logistic model selected 30 such Markov features. The largest positive direct Markov weights point toward AI when the sample's sequence has a higher AI-vs-human likelihood ratio, especially in order-2 shape, coarse, and motif views. This is exactly the role we wanted: not a standalone detector, but a sequence-rhythm correction layered on top of lexical evidence.

## The Logistic Model

After feature extraction, the detector trains a logistic regression model. The vocabulary is built from feature keys that appear at least eight times in training, sorted by frequency and key name, then capped at 12,000 features.

For every selected feature, training stores a mean and standard deviation. At runtime, the detector computes:

```text
standardized_value = (raw_value - training_mean) / training_std
logit = bias + sum(standardized_value * feature_weight)
probability = sigmoid(logit)
```

The training loop is pure Python sparse logistic regression. It uses 160 epochs, learning rate 0.1, L2 penalty 0.02, and a clipped sigmoid for numerical stability. The model artifact stores `vocab`, `weights`, `bias`, `means`, `stds`, `min_frequency`, `max_features`, `epochs`, `lr`, and `l2`.

Because the model is linear, Toslop can show the strongest contributing features. Each active feature has a family, value, weight, contribution, and direction. This makes the detector easier to inspect than a black-box prompt response.

## Accuracy Against Internal Methods

On the 8,993-row supervised test split, the combined model was the strongest internal method we evaluated with the same corpus and metric.

| Method | Feature count | Supervised test accuracy | Human false positives | AI false negatives |
| --- | ---: | ---: | ---: | ---: |
| `lexical_shape_plus_markov` | 12,000 | 97.93% | 135 | 51 |
| `lexical_style` | 12,000 | 97.29% | 182 | 62 |
| `shape_ngrams_plus_markov` | 3,020 | 92.59% | 374 | 292 |
| `shape_ngrams` | 424 | 88.01% | 668 | 410 |
| `markov_surface` | 2,596 | 90.40% | 494 | 369 |

Those numbers use the standard 0.5 probability cutoff for apples-to-apples comparison. The deployed candidate uses a stricter 0.6 threshold for binary labeling. At that production threshold, the same model reached 97.94% supervised-test accuracy:

| Method | Threshold | Accuracy | Human false-positive rate | AI recall | Confusion |
| --- | ---: | ---: | ---: | ---: | --- |
| `lexical_shape_plus_markov` | 0.5 | 97.93% | 3.02% | 98.87% | 4,475 TP / 4,332 TN / 135 FP / 51 FN |
| `lexical_shape_plus_markov` | 0.6 | 97.94% | 2.10% | 97.99% | 4,435 TP / 4,373 TN / 94 FP / 91 FN |
| `lexical_style` | 0.6 | 97.40% | 2.87% | 97.66% | 4,420 TP / 4,339 TN / 128 FP / 106 FN |
| `shape_ngrams_plus_markov` | 0.6 | 92.37% | 6.27% | 91.03% | 4,120 TP / 4,187 TN / 280 FP / 406 FN |
| `shape_ngrams` | 0.6 | 88.00% | 9.63% | 85.66% | 3,877 TP / 4,037 TN / 430 FP / 649 FN |
| `markov_surface` | 0.6 | 89.98% | 8.44% | 88.42% | 4,002 TP / 4,090 TN / 377 FP / 524 FN |

That threshold choice is important. For Toslop, a false positive is worse than a false negative. Missing some AI-generated pages makes the aggregate estimate conservative. Accusing human writing of being AI-written damages trust. The 0.6 threshold was selected for that tradeoff.

## Calibration Results

The model was also checked against held-out HC3 calibration sets that were not part of training. This is where the story becomes more nuanced.

| Method | Supervised test | HC3 wiki calibration | HC3 QA calibration |
| --- | ---: | ---: | ---: |
| `lexical_shape_plus_markov` | 97.93% | 51.28% | 77.56% |
| `lexical_style` | 97.29% | 52.21% | 75.40% |
| `shape_ngrams_plus_markov` | 92.59% | 49.80% | 67.72% |
| `shape_ngrams` | 88.01% | 48.30% | 66.89% |
| `markov_surface` | 90.40% | 50.19% | 65.81% |

The combined model did not win every calibration slice. Lexical-style did slightly better on HC3 wiki, while lexical-style+Markov won HC3 QA. We still chose the combined candidate because it won the supervised mixture, improved the conservative-threshold operating point, and provided a richer set of interpretable signals. The calibration result is also a useful warning: AI-writing detection is domain-sensitive. A model that looks excellent on a supervised split can become much less certain on a different genre.

At the 0.6 production threshold, HC3 wiki accuracy for the primary candidate was 52.51%, with an 81.14% human false-positive rate and 92.54% AI recall. HC3 QA accuracy was 79.80%, with a 36.87% human false-positive rate and 90.38% AI recall. That is why Toslop treats the score as measurement, not identity. The public site should be read as "this crawl sample contains this much AI-like writing according to this detector," not "these pages were definitely written by AI."

## Why Not Use A Bigger AI Detector?

We tested several internal alternatives before landing on this model family. Pure Markov features were fast and interpretable but not accurate enough. Shape n-grams helped, but still missed too much lexical signal. WordNet-style features performed better than shape-only baselines, but not as well as the lexical/style family. The combined model kept the lexical strength while adding enough structure to reduce mistakes at the threshold we care about.

We have not made a same-corpus claim against commercial AI detectors or every published academic detector. Unless those systems are run on the exact same split under the same rules, their advertised numbers are not directly comparable. The comparison above is the one we can defend: the same data, same labels, same split, same metric, and saved prediction artifacts.

## How Toslop Uses It

The crawler fetches candidate articles and posts, extracts readable text, hashes the extracted content for duplicate detection, and sends the sample to the analysis API. If the content hash has already been measured, Toslop reuses the existing result. Otherwise, it chunks the text, scores each chunk, and stores the aggregate in D1.

The public site reads summary rows from the Antemuse API. It shows aggregate measurements: average score, AI-likely share, sample count, source rows, queue state, and recent active-crawl measurements. The site is currently a measurement surface, not a representative web index. The next major accuracy step is sampling design: which URLs enter the corpus, how often they are refreshed, and how source groups are weighted.

The model answers one question: does this text look like the AI-generated side of our authorship corpus? Toslop then asks a second question: what happens when we apply that same instrument consistently across a crawl?

The first question is a model problem. The second is a measurement problem. Keeping those separate is what makes Toslop useful.

## Replication Protocol

The public replication package is published at [`roosiq/toslop-model`](https://github.com/roosiq/toslop-model). It is a clean repo, not a public copy of the private infrastructure monorepo. The private repo contains unrelated infrastructure, local `.env` files, generated artifacts, and dirty worktree state, so making it public as-is would expose unrelated private material. The public replication repo contains only the detector code, corpus scripts, model artifacts, reports, checksums, and documentation needed to reproduce the article.

The replication repo includes:

- corpus normalization and cleaning scripts;
- `corporate_ai_authorship_feature_spike.py`;
- `corporate_markov_features.py`;
- `corporate_authorship_detector.py`;
- `run_authorship_corpus_v2_markov_everything.py`;
- the frozen `surface_markov_models.json` artifact;
- the frozen `lexical_shape_plus_markov_model.json` artifact;
- the frozen `lexical_shape_plus_markov_edge_candidate.json` artifact;
- `method_comparison.json` files for the ablation tables;
- corpus reports and checksum manifests;
- instructions for downloading source datasets from pinned Hugging Face revisions.

From a clean checkout, the reproduction flow is:

```bash
python -m venv .venv
. .venv/bin/activate
pip install pandas pyarrow nltk

# Download source datasets into services/data/hf-corpora.
# Use the pinned revisions listed below.

PYTHONPATH=services/gateway \
  python services/gateway/app/corporate_corpus_ingest.py \
  --hf-root services/data/hf-corpora \
  --normalized-output services/evals/corporate_sequence_model/hf_normalized_corpus.jsonl \
  --max-docs-per-source 5000

cd services/gateway

python scripts_clean_corporate_authorship_corpus.py \
  --input ../evals/corporate_sequence_model/hf_normalized_corpus.jsonl \
  --output ../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1.jsonl \
  --rejected ../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1_rejected.jsonl \
  --report ../evals/corporate_sequence_model/hf_normalized_authorship_clean_v1_report.json \
  --min-words 30 \
  --max-words 900 \
  --test-ratio 0.25

python scripts_build_authorship_corpus_v2.py \
  --min-words 80 \
  --max-words 900 \
  --supervised-test-ratio 0.25 \
  --andy-existing-ratio 3.0 \
  --output-dir ../evals/corporate_sequence_model/authorship_corpus_v2

python run_authorship_corpus_v2_markov_everything.py \
  --output ../evals/corporate_sequence_model/authorship_corpus_v2_lexical_shape_markov_candidate \
  --min-frequency 8 \
  --max-features 12000 \
  --epochs 160 \
  --methods lexical_style,shape_ngrams,shape_ngrams_plus_markov,markov_surface,lexical_shape_plus_markov \
  --export-edge-candidate lexical_shape_plus_markov \
  --edge-threshold 0.6
```

The public package should pin these source dataset revisions:

| Dataset | Revision used for reproduction |
| --- | --- |
| `andythetechnerd03/AI-human-text` | `0387d82c81d6af6caaa6d792b48c9d07afa704d7` |
| `Ateeqq/AI-and-Human-Generated-Text` | `e0627b3f39fe0a27725889239067868797a4db40` |
| `silentone0725/ai-human-text-detection-v1` | `a303611a074f8f6736302126e8f06c51273f4562` |
| `harsh4248/human_vs_llm` | `e2783b28b72aad5cd87f47715be737d82753d6bd` |
| `sunorme/human-vs-llm-text-corpus` | `62e8e0729acc6134569d125be337526bc937840c` |
| `rajendrabaskota/hc3-wiki-intro-dataset` | `58f59eb06ad91e4f8fad1a86d40877661f0d63d9` |
| `pszemraj/HC3-textgen-qa` | `4cddc2b69948c9dba7ded91ed73f0a2b1a318340` |
| `phxdev/corporate-speak-dataset` | `e45ef4962cee017f22dabea6a36d30f04131355b` |

The key local source-file hashes used in the current run are:

| Source file | SHA-256 |
| --- | --- |
| `Ateeqq/train.csv` | `33c5da151521acb7cb2ba32a972a162551c46284fff115a0a837d19fcc03c085` |
| `Ateeqq/test.csv` | `522d9bbf146e6292bab9920447745dcf01fbd5628fd3b189969dcdb238576dc4` |
| `silentone/train.csv` | `2d851c99faf7f2b42edb87973b6e66b0122add284e40e695a2eff59ff1f89002` |
| `silentone/validation.csv` | `96a4153bffd14f3dd703252e5b477e81ce8cb8ccb1a8d252d4875be8d5232652` |
| `silentone/test.csv` | `6d11a782e93320792ae0ef28b198f951de69db7ea8720ad6b841b2a81f85a8db` |
| `harsh/train-00000-of-00005.parquet` | `6d2fc57e3a58c9227e74ca01c57929b56b9397564875bbebc8dc3fded6dcbdca` |
| `harsh/train-00001-of-00005.parquet` | `f54eeee5d323aae195858d2cba8d7801162f8c929a686e708f4ced4ef4979494` |
| `harsh/train-00002-of-00005.parquet` | `3170720aef0c343731d8c443ff69ffb91fc588b7172ff5881f3a12a40bee87f6` |
| `harsh/train-00003-of-00005.parquet` | `2aa6ef7a23ff01e0fc8823663b62adea9184acbdc5c1ae4230ce32fb0cc4dbd7` |
| `harsh/train-00004-of-00005.parquet` | `cc078d87c2bc2d1b3339b4521381539e04823c884fc0245974b8628a21922bce` |
| `sunorme/text_chunk_0001.txt` | `94545c50801f4a99dfbe746de05bc898a6cdff32f581d523e931e6517f376505` |
| `sunorme/text_chunk_0002.txt` | `0cb6fdb4a7aec40087455569e94d35db7100bfd6bcea78359f4751c71c054413` |
| `sunorme/text_chunk_0003.txt` | `86f594a46f1a319bd7adbb4902555c316803132fcbf0f9a6fd2d9aab479a13ba` |
| `sunorme/text_chunk_0004.txt` | `3a759b99369f011dd9c5b44047ea30a956543e0d09b70029dd3ee31a25abd4d6` |
| `sunorme/text_chunk_0005.txt` | `f7c6f056fac8358eb9f95a641664b99e90cd429af075ef7be220593db755a017` |
| `sunorme/text_chunk_0006.txt` | `b574a9e9a08cd7b3cb820d62f276c3ae8716630ad39a429267a21225ab6bb901` |
| `andy/test parquet` | `3a465bec1d49c3a37dca52393aa4cd43085de6da8ba991505a7b3f3034583b69` |
| `HC3 wiki parquet` | `beb81dd0276732ef957f1874eea47e1f1c93cbcf93f6724e272377fbedeed61f` |
| `HC3 QA csv` | `48c7d3134af475362aa11d53a5492a167a6632ef956eaf1a6695fc8ba77eef39` |
| `phxdev/train parquet` | `384a521684fc9cee1891042caa87ff66961a93b5996ab80f2412ca620996f3a5` |
| `phxdev/test parquet` | `52dc32649ce55b9bdc2dd56cded604e5694b815c12d427134a5273bc2029c877` |
| `phxdev/validation parquet` | `98aed4a23f227c0ebfe426298e256491e4d4ec193d541b2493c44338ebb60db9` |

The key generated artifact hashes are:

| Artifact | SHA-256 |
| --- | --- |
| `supervised_train_mix.jsonl` | `4548b5922387ca837108095c4d968e0b04d3d985fed75e547cea5030f9e2e843` |
| `supervised_test_mix.jsonl` | `8a32f654f33bd716c441b6872494b65728187561b3901df12d7ba4fe4cdbaf55` |
| `calibration_hc3_wiki.jsonl` | `5dec28fd2446ad0d4d5500085e3a294e1ce7d2aaae9b3d71981c7b77ca700de7` |
| `calibration_hc3_qa.jsonl` | `0d157f533323c751eb29a40c1edcb13ad73a41921dbafbb7b5704ac8fb2de6f4` |
| `authorship_corpus_v2/report.json` | `af962c191f3f4a4d82155e8436d0beba9a316a1d09e8f49f5c201d0a7450c90c` |
| `method_comparison.json` | `f6a2019f0b0053db5eab973e41b4264fd38e111882a42aa882cadb720027f686` |
| `lexical_shape_plus_markov_model.json` | `ae37768fe01c98d9608630212026d8c29becd3a0a1b330a5f33eafab756a691c` |
| `surface_markov_models.json` | `01e0cedf41b484a36cbe186c50e76b9d75cf996a931466ef9bdcc63777ab2b13` |
| `lexical_shape_plus_markov_edge_candidate.json` | `82686f957bb3b791777a2ab6625b4f3e360fc1cd38f4985b5067078c121a4956` |

The public repo does not redistribute the frozen generated JSONL splits because those files contain source dataset text. Instead, it publishes the downloader, source revision pins, source-file checksums, and generated split checksums. That makes the method reproducible from public datasets and lets readers verify whether their regenerated files match the original run byte-for-byte.
