# Decision-Record Index

Decision records make approval-blocking choices immutable and linkable. A spec
may propose a default, but the choice is not resolved until an approved decision
record names the affected spec versions and supplies approval evidence.

Use [TEMPLATE.md](TEMPLATE.md). Name records
`DR-NNN-short-decision-name.md`; never renumber or overwrite an approved record.
Supersede it with a new record and link both directions.

## Registry

| ID | Decision | Status | Gate | Affected specs |
| --- | --- | --- | --- | --- |
| [DR-001](DR-001-implementation-directive.md) | Observatory implementation directive | Approved | G0 implementation start | IS-001-IS-008; ES-001-ES-014 |
| [DR-002](DR-002-storage-development-boundary.md) | Observatory storage development boundary | Approved | G1 development and shadow | IS-002; ES-002 |
| [DR-003](DR-003-synthetic-job-corpus-boundary.md) | Synthetic job-corpus implementation boundary | Approved | G1 development and G2 bootstrap | IS-002; ES-003 |
| [DR-004](DR-004-s7-bootstrap-extractor-boundary.md) | S7 bootstrap extractor boundary | Approved | G2 bootstrap only | IS-003; ES-004 |
| [DR-005](DR-005-s7-synthetic-aggregation-boundary.md) | S7 synthetic aggregation boundary | Approved | G2 formula bootstrap only | IS-003; ES-005 |
| [DR-006](DR-006-s3-synthetic-bootstrap-boundary.md) | S3 synthetic corpus, feature, and formula boundary | Approved | G1-G2 synthetic bootstrap only | IS-004; IS-005; ES-006; ES-007; ES-008 |
| [DR-007](DR-007-benchmark-synthetic-framework-boundary.md) | Benchmark synthetic framework boundary | Approved | G2 framework bootstrap only | IS-006; ES-009 |
| [DR-008](DR-008-delivery-fixture-boundary.md) | Observatory delivery fixture boundary | Approved | G3-G5 fixture and disabled-route bootstrap only | IS-007; ES-010; ES-011 |
