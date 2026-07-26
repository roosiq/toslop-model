# January 2024 frozen-prediction diagnostic (no-text)

This score does not establish AI authorship.

This is a post-hoc diagnostic of frozen predictions. It is not model selection, calibration, threshold tuning, retraining, or production scoring.

## Reviewed candidate and HOLD boundary

- Model ID: `infini-news-lexical_tfidf_logistic-v1-cca5838ac34f`
- Reviewed candidate artifact SHA-256: `0ca8956726b101fd585ff663caf4119e4911d3ec2789cf25fab415669691d403`
- Threshold: `0.49690983649044096` (unchanged)
- Release decision: `HOLD`; selected candidate/model: `null`; artifact freeze: `not_performed`.
- The candidate is reviewed-not-selected. Its candidate artifact is checksum-verified for provenance only and is not copied into the final package or used to rescore rows.
- Inputs: frozen publisher/domain-held-out primary predictions, reviewed-candidate metadata/artifact, and the HOLD decision packet.
- Public output: aggregates and already-hashed source/domain identifiers; no article body, title, URL, or raw/normalized article content.

## Time comparison

| Window | N | Correct | Errors | Accuracy | Mean score | Median score |
|---|---:|---:|---:|---:|---:|---:|
| December 2023 | 669 | 565 | 104 | 84.45% | 0.802327 | 0.924038 |
| January 2024 | 951 | 580 | 371 | 60.99% | 0.604491 | 0.630336 |
| February 2024 | 706 | 615 | 91 | 87.11% | 0.821293 | 0.949388 |
| Remainder of 2024 (Mar-Dec) | 6232 | 5464 | 768 | 87.68% | 0.818309 | 0.925682 |
| Overall frozen test | 55383 | 48748 | 6635 | 88.02% | 0.442480 | 0.345488 |

January 2024 recomputes to **580/951 = 60.99% accuracy** at the unchanged threshold.

## Dominant January error contributors

- Source hash: `01749ccf37ee4b7bce18df5a` (212 errors, 57.1% of January errors, 12.76% accuracy); `104cc9195ca721f03f030df2` (73 errors, 19.7% of January errors, 50.68% accuracy); `6974cdd6f5ec181f58149ef4` (19 errors, 5.1% of January errors, 72.06% accuracy)
- Domain hash: `01749ccf37ee4b7bce18df5a` (212 errors, 57.1% of January errors, 12.76% accuracy); `0659c67b41c23acaa724ae3c` (73 errors, 19.7% of January errors, 50.68% accuracy); `4392dbefdcb2bfc3b7517ae3` (19 errors, 5.1% of January errors, 72.46% accuracy)
- Topic: `economy_business_finance` (96 errors, 25.9% of January errors, 68.63% accuracy); `arts_culture` (59 errors, 15.9% of January errors, 40.40% accuracy); `sport` (42 errors, 11.3% of January errors, 67.94% accuracy)
- Word-count band: `500_749` (158 errors, 42.6% of January errors, 51.38% accuracy); `300_499` (108 errors, 29.1% of January errors, 61.43% accuracy); `150_299` (79 errors, 21.3% of January errors, 57.53% accuracy)
- Missing-author status: `missing` (288 errors, 77.6% of January errors, 45.04% accuracy); `present` (83 errors, 22.4% of January errors, 80.56% accuracy)
- Near-duplicate cluster: `ndc_005099a7cd8cd35a3f44` (1 errors, 0.3% of January errors, 0.00% accuracy); `ndc_024747c0f50f4e3feaaf` (1 errors, 0.3% of January errors, 0.00% accuracy); `ndc_0355ac617e9bc24efed7` (1 errors, 0.3% of January errors, 0.00% accuracy)

The JSON artifact includes top-by-error and top-by-support tables plus top-1/top-3/top-5 error-concentration shares for every dimension.

## Data-processing check

No data-processing defect was detected in the frozen no-text metadata and prediction fields. This diagnostic cannot assess an unseen article-text pipeline.

The checks cover date-field consistency, corpus-role/label consistency, source/domain/topic/length/cluster presence, January labels, duplicate identities, and duplicate normalized-content hashes. They do not inspect article content.

## Source-composition finding

The leading source appears in the frozen 2024 test only in January, accounts for more than half of January errors, and has missing author metadata on every January row. This supports a source-composition explanation for the monthly dip; it does not by itself establish a text-pipeline defect or justify source-specific tuning.

The leading source hash contributes 57.1% of January errors. It has 243 January rows, 12.76% accuracy, and 243 rows with missing author metadata. Its December, February, and March-December supports are 0, 0, and 0 respectively.

## Interpretation boundary

The observed January drop is diagnostic evidence only. No model, feature, threshold, split, prediction, or training/tuning input was changed.

This score does not establish AI authorship.
