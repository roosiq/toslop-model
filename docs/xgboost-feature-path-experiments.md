# XGBoost Feature Path Experiments

Date: 2026-06-12

These experiments compare alternative feature paths for the optional XGBoost
authorship trainer. They use the same authorship corpus v2 supervised test,
HC3 wiki calibration holdout, HC3 QA calibration holdout, and defensive HC3
training slice as the current linear production candidate.

Recorded dependency versions: XGBoost 3.2.0, SciPy 1.17.1, NumPy 2.4.6.

## Added Feature Paths

- `markov_shape`: Markov features from the shape-state view only.
- `markov_posish`: Markov features from the POS-ish state view only.
- `markov_true_pos`: Markov features from the NLTK true-POS state view only.
- `markov_core`: shape + POS-ish + true-POS Markov features, excluding semantic, coarse, and motif views.
- `lexical_plus_core_markov`: lexical/style features plus `markov_core`.
- `lexical_shape_plus_core_markov`: lexical/style + shape n-grams plus `markov_core`.

The `include_views` path in `surface_markov_features` now excludes semantic
aggregate features unless the semantic view is explicitly included.

## Screen Run

The first pass used 120 XGBoost rounds to screen many paths quickly:

```bash
cd services/gateway
python run_authorship_corpus_v2_markov_everything.py \
  --output /tmp/toslop-xgboost-feature-screen \
  --min-frequency 8 \
  --max-features 30000 \
  --methods markov_surface,markov_core,markov_shape,markov_posish,markov_true_pos,lexical_plus_markov,lexical_plus_core_markov,shape_ngrams_plus_markov,lexical_shape,lexical_shape_plus_markov,lexical_shape_plus_core_markov \
  --trainer xgboost \
  --xgboost-rounds 120 \
  --xgboost-max-depth 4 \
  --xgboost-eta 0.06 \
  --defensive-calibration-train-ratio 0.25 \
  --defensive-calibration-wiki-max-per-label 1800 \
  --defensive-calibration-qa-max-per-label 450 \
  --edge-threshold 0.6 \
  --xgboost-nthread 8
```

At 120 rounds the combined models were undertrained relative to the 350-round
candidate, but the screen was useful for ranking feature families.

| Method | Vocab | Min AI Recall At 0.6 | Max Human FPR At 0.6 | Avg Accuracy At 0.6 |
|---|---:|---:|---:|---:|
| `shape_ngrams_plus_markov_xgboost` | 3,911 | 0.7204 | 0.3748 | 0.8214 |
| `lexical_shape_plus_markov_xgboost` | 30,000 | 0.7172 | 0.1679 | 0.8649 |
| `lexical_shape_plus_core_markov_xgboost` | 30,000 | 0.7164 | 0.1679 | 0.8675 |
| `markov_core_xgboost` | 1,962 | 0.7060 | 0.3482 | 0.7839 |
| `markov_posish_xgboost` | 1,278 | 0.7000 | 0.3510 | 0.7754 |
| `lexical_plus_markov_xgboost` | 30,000 | 0.6992 | 0.0949 | 0.8615 |
| `markov_surface_xgboost` | 3,481 | 0.6938 | 0.3463 | 0.7789 |
| `lexical_shape_xgboost` | 30,000 | 0.6890 | 0.1727 | 0.8552 |
| `lexical_plus_core_markov_xgboost` | 30,000 | 0.6885 | 0.1243 | 0.8516 |
| `markov_shape_xgboost` | 10 | 0.6422 | 0.7002 | 0.7207 |
| `markov_true_pos_xgboost` | 674 | 0.6008 | 0.3937 | 0.7389 |

## Final-Size Follow-Up

The second pass used 350 rounds on the two most useful follow-ups:

```bash
cd services/gateway
python run_authorship_corpus_v2_markov_everything.py \
  --output /tmp/toslop-xgboost-core-final \
  --min-frequency 8 \
  --max-features 30000 \
  --methods lexical_shape,lexical_shape_plus_core_markov \
  --trainer xgboost \
  --xgboost-rounds 350 \
  --xgboost-max-depth 4 \
  --xgboost-eta 0.06 \
  --defensive-calibration-train-ratio 0.25 \
  --defensive-calibration-wiki-max-per-label 1800 \
  --defensive-calibration-qa-max-per-label 450 \
  --edge-threshold 0.6 \
  --xgboost-nthread 8
```

Threshold 0.6 results:

| Model | Split | Accuracy | AI Recall | Human FPR |
|---|---|---:|---:|---:|
| Linear `lexical_shape_plus_markov` | supervised test | 0.9789 | 0.9730 | 0.0152 |
| Linear `lexical_shape_plus_markov` | HC3 wiki | 0.8885 | 0.8824 | 0.1066 |
| Linear `lexical_shape_plus_markov` | HC3 QA | 0.8743 | 0.8497 | 0.0844 |
| XGB `lexical_shape_plus_markov` | supervised test | 0.9772 | 0.9691 | 0.0146 |
| XGB `lexical_shape_plus_markov` | HC3 wiki | 0.9004 | 0.8233 | 0.0376 |
| XGB `lexical_shape_plus_markov` | HC3 QA | 0.8765 | 0.8446 | 0.0702 |
| XGB `lexical_shape_plus_core_markov` | supervised test | 0.9756 | 0.9664 | 0.0150 |
| XGB `lexical_shape_plus_core_markov` | HC3 wiki | 0.9019 | 0.8233 | 0.0350 |
| XGB `lexical_shape_plus_core_markov` | HC3 QA | 0.8758 | 0.8423 | 0.0683 |
| XGB `lexical_shape` | supervised test | 0.9748 | 0.9640 | 0.0143 |
| XGB `lexical_shape` | HC3 wiki | 0.8919 | 0.8085 | 0.0411 |
| XGB `lexical_shape` | HC3 QA | 0.8694 | 0.8412 | 0.0835 |

## Interpretation

Markov-only models are not strong enough for the target. POS-ish Markov carries
more signal than shape-only or true-POS-only Markov, but still needs lexical and
shape evidence.

The no-Markov `lexical_shape_xgboost` control passes the operating target at
350 rounds, which means XGBoost can learn a strong detector from lexical/style
and shape n-gram features alone. Adding core Markov improves HC3 wiki accuracy
and lowers HC3 QA human false positives, while keeping AI recall above 80% on
all required splits.

The best XGBoost path to investigate next is `lexical_shape_plus_core_markov`.
It excludes semantic/coarse/motif Markov views, has slightly lower HC3 false
positive rates than the full-Markov XGBoost candidate, and keeps essentially
the same HC3 wiki AI recall. It is still not edge-deployable until the gateway
or Worker has an XGBoost tree runtime.
