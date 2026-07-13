# INFINI-NEWS v1 split protocol summary (text-free)

This score does not establish AI authorship.

## Scope

- Assignment stage: `documents_assigned_before_features_or_chunks`
- Fit roles: `["current_core", "pre_llm_core"]`
- Evaluation-only roles: `["forward_2026", "historical_placebo", "transition_2022"]`
- Fit/calibration/threshold exclusion: `2022_transition_and_2026_forward_rows_excluded_from_fitting_calibration_and_thresholds`
- Row counts: `{"by_role": {"current_core": 108000, "forward_2026": 2000, "historical_placebo": 8000, "pre_llm_core": 144000, "transition_2022": 2000}, "excluded_role_counts": {"forward_2026": 2000, "historical_placebo": 8000, "transition_2022": 2000}, "fit_rows": 252000, "total": 264000}`

## Protocol counts and leakage audits

| Protocol | Support | Assignments | Counts | Overlap audit | Assignment hash | Limitations |
|---|---|---:|---|---|---|---|
| author_heldout | supported | 213763 | `{"test": 45237, "train": 149091, "validation": 19435}` | `{"author_hash": 0, "identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `f94e7a8e64360616a243c3232ec15a7f6a265700f4f489562a9a8b6a1e3591bb` | missing_author=38237 |
| forward_2026 | supported | 2000 | `{"evaluation_only": 2000}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `10869cca0ea5db582891d9935d479c294bc84fa98751faff6586866f45dac8ea` | none |
| historical_placebo | supported | 8000 | `{"evaluation_only": 8000}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `00de84abf0b4991f08b1d8533cecea59ab5647f131cf8cb5b40799382147e70c` | none |
| publisher_domain_heldout_primary | supported | 252000 | `{"test": 55383, "train": 169261, "validation": 27356}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "url_hostname": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `0a007825dbb00289a35fa82e5efe116d57fd1af5b0c15a11bbb84b051d804e06` | none |
| random_diagnostic | supported | 252000 | `{"test": 50751, "train": 176128, "validation": 25121}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `9bec565c81b2dd2150ce73ec5fe19286f6be7bac9675e7c502084f8f8ba8019e` | none |
| same_author_pre_post | supported | 0 | `null` | `null` | `dc6b5e1710881bf5575126aa6c9d972d8260c5febe3ee8888540485e6ac5054c` | same_author_pairs=5418 |
| source_sitename_heldout | supported | 252000 | `{"test": 50320, "train": 179640, "validation": 22040}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "sitename": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `167b6386648b71628d4ed7cb3ee10fe4fa9336cdad9f0525c22da8bef082a2b0` | none |
| topic_heldout | supported | 252000 | `{"test": 52617, "train": 172293, "validation": 27090}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "topic": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `0fa74e325a19e53583a4e460314ab526261c4ab4497a5eed89bad58898de1097` | none |
| transition_2022 | supported | 2000 | `{"evaluation_only": 2000}` | `{"identity_hash": 0, "near_duplicate_cluster_id": 0, "normalized_text_sha256": 0, "normalized_url_hash": 0, "warc_identity_hash": 0, "warc_payload_digest_hash": 0}` | `137f70fed2b65774a5086f403d492f38945907e0470d3364236e804aaf0c32e8` | none |

## Integrity notes

- WARC identity, payload digest, URL hash, text hash, and near-duplicate cluster overlap audits are computed across model-bearing partitions for each model-bearing protocol.
- Publisher/domain, source/sitename, topic, author, and random-diagnostic assignments use only document-level metadata and occur before any features or chunks are built.
- 2022 transition and January-April 2026 forward rows are written as evaluation-only protocols and are excluded from fitting, calibration, and threshold selection.
- Public artifacts contain IDs, hashes, counts, and protocol metadata only; no article text, title, preview, URL, or description is emitted.
