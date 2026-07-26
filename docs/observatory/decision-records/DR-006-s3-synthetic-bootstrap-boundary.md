# DR-006: S3 Synthetic Bootstrap Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G1-G2 synthetic bootstrap only |
| Affected spec versions | IS-004 v0.1.0; IS-005 v0.1.0; ES-006 v0.1.0; ES-007 v0.1.0; ES-008 v0.1.0 |
| Supersedes | None |

## Decision

Approve synthetic-only implementation of the professional-writing corpus,
deterministic fallback feature families, and Language Homogenization formula.

The bootstrap boundary includes:

- explicit authored, quote, boilerplate, template, navigation, code, table,
  and unknown block roles;
- four allowlisted synthetic genre IDs and a versioned keyword topic fixture;
- deterministic event, exact, near-duplicate, syndication, and revision IDs;
- frozen baseline lexical vocabulary and hashed TF-IDF semantic fallback;
- transparent surface-syntax and authored rhetorical registries;
- Jensen-Shannon lexical and syntactic dispersion, cosine rhetorical and
  semantic dispersion, robust baseline scaling, contribution caps, and equal
  component weights;
- no-text corpus and feature manifests plus a contract-valid suppressed S3
  projection.

## Prohibited uses

This decision does not approve real sources, a production genre or topic
classifier, a syntactic parser, a semantic embedding model, historical
baseline weights, empirical drift thresholds, or an observed S3 result.

The surface-syntax and hashed semantic representations are fallback
diagnostics, not approved production substitutes. Every projected score remains
suppressed until the corpus, features, benchmark, baseline, and release gates
pass.

## Expansion gate

Real execution requires source decisions and an ES-006 corpus release. Feature
freeze requires approved parser and semantic artifacts with revisions,
licenses, checksums, offline runtime, and benchmark evidence. Score release
requires matched historical cells, protected evaluation, uncertainty,
sensitivities, and a non-fixture release registry row.

## Approval evidence

Ryan Cook's implementation instruction on 2026-07-25, constrained by DR-001
through DR-005.
