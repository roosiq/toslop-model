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
