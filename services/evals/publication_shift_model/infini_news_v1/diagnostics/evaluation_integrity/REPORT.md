# INFINI-NEWS evaluation-integrity audit (no-text)

This score does not establish AI authorship.

- Frozen-run decision: **REJECT**
- Production integration: **none**
- Public boundary: aggregate counts and hashes only; no article text, title, URL, or raw source name.

## Gate matrix

| Gate | Status | Finding |
|---|---|---|
| Alternate-lane split integrity | REJECT | 4 alternate lanes overlap primary training IDs. |
| Historical placebo support | FAIL | Emitted named contrasts have no later-arm support; ROC-AUC/lift are undefined. |
| Full multi-task encoder | HOLD | cpu_smoke_only; observed corpus rows: 160. |
| Required subgroup stability | FAIL | 4 source groups and 2 months are below 70% accuracy. |

## Exact alternate-test overlap with primary training IDs

| Alternate lane | Overlap / test | Fraction | Gate |
|---|---:|---:|---|
| `source_sitename_heldout` | 31,459 / 50,320 | 62.52% | REJECT |
| `topic_heldout` | 34,944 / 52,617 | 66.41% | REJECT |
| `author_heldout` | 30,197 / 45,237 | 66.75% | REJECT |
| `random_diagnostic` | 34,153 / 50,751 | 67.30% | REJECT |

The per-lane split manifests are internally disjoint, but the frozen candidates were trained once on the publisher/domain primary training partition. Reusing that model on alternate test partitions makes rows already seen in primary training part of the reported alternate test scores.

## Placebo support

Both named placebo files for every candidate contain only the early arm. The full lexical and stylometric files each contain 8,000 rows (4,000 from 2016 and 4,000 from 2017), all labeled 0, and zero rows from the promised later years. The encoder files are smoke subsets with null labels. These are unsupported substitutions, not two-arm matched placebos.

## Encoder status

- Status: `cpu_smoke_only` / `SMOKE-HOLD`
- Counts: `{"corpus_rows": 160, "test": 13, "train": 26, "validation": 25}`
- Accelerator verified: `false`; selected device: `cpu`
- Measured blocker preserved: `true`
- Runtime-input gate: `PASS` (token IDs and attention mask; no metadata runtime inputs)

## Source-group collapses

Frozen selected model threshold: `0.49690983649044096`. Listed groups have support >= 100 and accuracy < 70%.

| Source-group hash | Support | Correct | Accuracy |
|---|---:|---:|---:|
| `01749ccf37ee4b7bce18df5a` | 249 | 37 | 14.86% |
| `104cc9195ca721f03f030df2` | 170 | 89 | 52.35% |
| `1c1544646ec3c45118e4bc7c` | 116 | 71 | 61.21% |
| `a745402bc4b4920fb330b434` | 196 | 130 | 66.33% |

## Monthly collapses

| Publication month | Support | Correct | Accuracy |
|---|---:|---:|---:|
| `2023-04` | 598 | 414 | 69.23% |
| `2024-01` | 951 | 580 | 60.99% |

January 2024 independently recomputes to 580/951 correct (60.99%) at the unchanged frozen threshold.

## Reproduction

Run from the repository root with the private normalized corpus supplied explicitly:

```bash
PYTHONPATH=services/gateway python services/gateway/audit_infini_news_evaluation_integrity.py --corpus <private-normalized-rows.jsonl>
```

Expected private-corpus SHA-256: `66910e65a91c8b238846a491dbe8ebfa094157e7d365769a2043bdae082dfbc0`. The script verifies frozen row/role/protocol counts and tracked prediction assignment sets before writing evidence.

## Interpretation

Evaluation leakage invalidates the alternate-lane claims and triggers REJECT for this frozen run. Missing placebo arms, a smoke-only encoder, and severe subgroup collapses independently prevent promotion. No model, threshold, prediction, or production runtime was changed by this audit.
