# INFINI-NEWS final publication-shift model v1

This score does not establish AI authorship.

- Decision: `PASS`
- Selected candidate: `lexical_tfidf_logistic`
- Model ID: `infini-news-lexical_tfidf_logistic-v1-cca5838ac34f`
- Model family: `infini_news_word_char_tfidf_logistic`
- Score: `current_era_similarity`
- Threshold: `0.49690983649044096`
- Production integration: `none`
- Calibration/threshold selection: validation only
- Runtime metadata inputs: none

## Primary frozen evidence

- Publisher/domain held-out ROC-AUC: `0.9484060296000801`
- Grouped-bootstrap ROC-AUC 95% CI: `0.9343468494317588` - `0.9602937818907181`
- Balanced accuracy: `0.8742950795308809`
- ECE: `0.053612653702012084`
- Masked ROC-AUC: `0.8543095216907752`
- Masking loss ROC-AUC: `0.0940965079093049`
- Strongest matched placebo: `pre_llm_2018_vs_2021`
- Main-minus-strongest-placebo ROC-AUC lift: `0.40130238836918986`

## Decision notes

- Ensemble attempted: `False`
- Ensemble reason: Only one candidate passed every component gate; predeclared ensemble precondition not met.
- The encoder candidate remained SMOKE-HOLD because no verified accelerator-backed full frozen-row run exists.
- The score estimates publication-era similarity only and must not be interpreted as AI authorship evidence.

## Rights and data boundary

Public artifacts contain IDs, hashes, aggregate metrics, model metadata, and no article body/title/URL/preview fields.
