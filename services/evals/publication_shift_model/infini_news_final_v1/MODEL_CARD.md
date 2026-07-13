# INFINI-NEWS publication-shift evidence review v1

**This score does not establish AI authorship.**

**MANDATORY HOLD NOTICE: This evidence is research-only. No model is selected, frozen for release, validated for deployment, or authorized for production use.**

- Final disposition: `HOLD`
- Selected candidate: `none`
- Reviewed candidate (not selected): `lexical_tfidf_logistic`
- Reviewed model ID: `infini-news-lexical_tfidf_logistic-v1-cca5838ac34f`
- Reviewed artifact SHA-256: `0ca8956726b101fd585ff663caf4119e4911d3ec2789cf25fab415669691d403`
- Reviewed threshold: `0.49690983649044096`
- Reviewed training identity: `cca5838ac34f170c53d1552ed8e8ca09fed187f9111b37c20f5e87cf9456e7b5`
- Artifact identity assertions: `PASS`
- Artifact copied/frozen into final package: `no`
- Production integration: `none`

## Valid primary frozen evidence (preserved)

- Publisher/domain-held-out ROC-AUC: `0.9484060296000801`
- Grouped-bootstrap ROC-AUC 95% CI: `0.9343468494317588` - `0.9602937818907181`
- Balanced accuracy: `0.8742950795308809`
- ECE: `0.053612653702012084`
- Masked ROC-AUC: `0.8543095216907752`
- Masking loss ROC-AUC: `0.0940965079093049`

## Why the disposition is HOLD

- Failed required gates: `declared_historical_placebos_supported, external_validation_gates, full_encoder_or_measured_hardware_hold, no_severe_subgroup_collapse, placebo_lift_minimum_and_ci, rights_clearance_for_promotion, valid_leakage_safe_alternate_lanes`
- Source/topic/author/random metrics are `invalid_for_selection`: their alternate test partitions were not kept disjoint from the primary artifact's training rows; critical review measured 62%-67% training-document reuse.
- Exact per-lane primary-training overlap cannot be recomputed from the committed package because primary train/validation document IDs were not frozen. This missing audit is itself a gate failure.
- The frozen historical-placebo files contain no late comparison class. Prior core-row substitutions are not accepted; placebo lift and its required 95% CI are unavailable.
- Encoder evidence is `SMOKE-HOLD` only, not a full frozen-row run or measured hardware HOLD.
- Severe source/month collapse count at >= 100 rows and < 0.70 accuracy: `6`.
- January 2024 is 580/951 = 60.99% accuracy; a 249-row source hash is 14.86% accurate overall (and its 243 January rows are 12.76% accurate in the frozen diagnostic).
- BBC external decision: `HOLD` (balanced accuracy `0.7609599957757686`).
- Multisource all-valid decision: `HOLD` (masked ROC-AUC `0.6937756499620906`).
- Multisource domain-matched decision: `HOLD` (balanced accuracy `0.76`, masked ROC-AUC `0.7185595567867036`).
- Primary and external data rights remain research-only/HOLD; there is no production authorization.

## Placebo claim boundary

- Strongest valid declared placebo: `None`
- Main-minus-placebo lift: `None`
- Lift 95% CI lower bound: `None`
- Therefore this package does not establish an unusual LLM-era publication shift; the evidence may reflect ordinary temporal/domain drift.

## Rights and interpretation boundary

Public artifacts contain IDs, hashes, aggregate metrics, and model metadata only. Article bodies, titles, descriptions, URLs, and previews are excluded.

**This score does not establish AI authorship.**
