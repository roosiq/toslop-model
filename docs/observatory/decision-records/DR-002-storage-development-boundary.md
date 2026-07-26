# DR-002: Observatory Storage Development Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Version | 1.0.0 |
| Created | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G1 development and shadow |
| Affected spec versions | IS-002 v0.1.0; ES-002 v0.1.0 |
| Supersedes | None |

## Decision

Authorize the ES-002 storage foundation under these boundaries:

- local and CI metadata use dedicated PostgreSQL 16 database `observatory`;
- local PostgreSQL binds to loopback port `55434`;
- local object bytes use a private content-addressed filesystem adapter;
- the production adapter is S3-compatible and requires HTTPS, server-side
  encryption, injected credentials, checksum metadata, and a private bucket;
- production PostgreSQL provider, region, object-store provider, bucket,
  backup retention, and credentials remain unset and fail closed;
- the default development object limit is 10 MiB, while every source decision
  must set a source-specific equal or stricter limit;
- no real source collection is authorized by this record.

Every real source requires its own approved decision covering access, terms,
robots behavior, license, allowed fields and purposes, retention, deletion,
rate budget, and public aggregation.

## Context and evidence

ES-001 is a stable contract candidate. ES-002 needs a testable database,
object-store interface, policy engine, lineage, retention, deletion, and
manifest boundary before collectors can be built safely.

The existing GraphSlop PostgreSQL database and Toslop SQLite store have
different ownership and semantics and are not reused.

## Alternatives considered

| Alternative | Reason accepted or rejected |
| --- | --- |
| Reuse GraphSlop PostgreSQL schema | Rejected because it breaks database and role isolation |
| Extend Toslop SQLite | Rejected because it cannot satisfy the specified role, migration, and production boundaries |
| Choose a production cloud provider now | Rejected because region, operations ownership, and credentials are unresolved |
| Build local PostgreSQL and filesystem plus injected S3 adapter | Accepted as a bounded implementation and shadow-test boundary |

## Consequences

- Production configuration fails closed until a provider decision supersedes
  or narrows this record.
- Filesystem storage is rejected outside development.
- Object keys contain only content hashes.
- Public manifests are generated from an allowlist.
- Source policy is evaluated before any future collector run.

## Revisit conditions

Supersede this record before the first real source pilot, production
provisioning, object-size increase, non-loopback local bind, backup policy
change, or provider/region selection.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for development and synthetic shadow storage |
| Approved version | 1.0.0 |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-001 implementation directive and ES-002 local migration test |
