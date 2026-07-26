# Intent-Spec Index

Intent specs define the outcome and boundary of a work package. They do not
authorize implementation until the approval block records a named decision
owner, date, approved version, and evidence link.

The `Gating dependency` column contains approval prerequisites only. A
coordination interface may be designed in parallel and is documented inside the
intent; it does not block approval unless it is promoted to this column.

| ID | Intent | Status | Version | Gating dependency |
| --- | --- | --- | --- | --- |
| [IS-001](IS-001-score-ontology-and-reporting-semantics.md) | Score ontology and reporting semantics | Proposed | 0.1.0 | None |
| [IS-002](IS-002-public-job-posting-data-foundation.md) | Public job-posting data foundation | Proposed | 0.1.0 | IS-001 |
| [IS-003](IS-003-employer-ai-compulsion-scorer.md) | Employer AI Compulsion scorer | Proposed | 0.1.0 | IS-001, IS-002 |
| [IS-004](IS-004-professional-writing-corpus.md) | Professional-writing corpus | Proposed | 0.1.0 | IS-001 |
| [IS-005](IS-005-language-homogenization-scorer.md) | Language Homogenization scorer | Proposed | 0.1.0 | IS-001, IS-004 |
| [IS-006](IS-006-mvp-validation-benchmark.md) | MVP validation benchmark | Proposed | 0.1.0 | IS-001, IS-003, IS-005 |
| [IS-007](IS-007-mvp-research-dashboard.md) | MVP research dashboard | Proposed | 0.1.0 | IS-001, IS-003, IS-005, IS-006 |

## Approval order

The acyclic approval sequence is:

1. IS-001.
2. IS-002 and IS-004, in either order or in parallel.
3. IS-003 after IS-002; IS-005 after IS-004.
4. IS-006 after the two scorer intents freeze their benchmark obligations.
5. IS-007 after the scorer and benchmark intents are approved.

## Approval rule

Approval applies to one immutable semantic version. A material change to the
construct, sources, supported population, score meaning, prohibited
interpretations, or success criteria requires a new version and renewed
approval. Editorial corrections may increment the patch version without
changing the approved outcome.
