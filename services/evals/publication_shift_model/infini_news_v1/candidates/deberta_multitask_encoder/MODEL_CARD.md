# INFINI-NEWS deberta_multitask_encoder candidate

This score does not establish AI authorship.

- Model ID: `infini-news-deberta_multitask_encoder-v1-6433a75b5e52`
- Model family: `infini_news_deberta_multitask_encoder`
- Runtime inputs: article text tokens only; metadata is not accepted by the model forward path.
- Tasks: era classification, publication-year regression, pairwise recency ranking.
- Training protocol: `publisher_domain_heldout_primary` train/validation rows only.
- Evaluation-only roles excluded from fitting/calibration/thresholds: `historical_placebo`, `transition_2022`, `forward_2026`.
- Production wiring: none
- Decision: `SMOKE-HOLD`
- Primary held-out ROC-AUC: `0.6666666666666667`
- Artifact SHA256: `c6d80a349380c250d3c132f6db9a2a7917e587c3d285edb34f9b7d1dacfd7e56`

Public artifacts contain IDs, hashes, metrics, and feature audits only; article text, titles, descriptions, URLs, and previews are excluded.
