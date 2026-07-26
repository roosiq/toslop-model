# Release-Record Index

Release records authorize one immutable scorer, corpus, benchmark, contract, API,
or dashboard cutover. They link gate evidence and rollback instructions without
embedding private data.

Use [TEMPLATE.md](TEMPLATE.md). Name records
`RR-<artifact>-v<version>.md`. A released artifact must have one indexed record;
a retirement or rollback appends evidence or creates a superseding record
without rewriting the original authorization.

## Registry

| Record | Artifact and version | Disposition | Effective date |
| --- | --- | --- | --- |
| [RR-CONTRACT-v1.0.0](RR-CONTRACT-v1.0.0.md) | Observatory score contract 1.0.0 | Shadow candidate | Pending |
