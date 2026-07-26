# ES-002: Source Registry and Immutable Storage

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Data lead |
| Approved intent reference | IS-002 v0.1.0, approval pending |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1, G5 |
| Start prerequisites | ES-001 stable contract candidate |
| Stage interfaces | Storage readiness to ES-003 and ES-006 |

## Implementation authorization

Implementation may begin only after
[IS-002](../intent-specs/IS-002-public-job-posting-data-foundation.md)
is approved, ES-001 has a stable contract candidate, and the program owner
approves the production database, object-store provider, region, encryption,
retention, and source-decision workflow.

No source collection is authorized by this execution spec. Each source requires
its own approved decision record.

## Outcome

Provide an isolated private metadata database and content-addressed object store
for source policies, collection runs, immutable observations, normalized
snapshots, lineage, holds, deletion, and release manifests.

## Current state

- `slopslingers-infra/services/gateway/app/toslop_storage.py` creates a local
  SQLite database for two current Toslop crawl tables.
- `slopslingers-infra/docker-compose.yml` runs PostgreSQL 16 for GraphSlop and
  already includes `psycopg`.
- There is no observatory database, source-policy registry, object-store
  interface, lineage graph, retention service, or deletion propagation.
- Existing `.env` and local data volumes are private and must not become public
  replication artifacts.

## Architecture and boundaries

```text
approved source decision
          |
          v
PostgreSQL metadata catalog <----> private observatory services
          |                                |
          | lineage and object metadata    | encrypted content bytes
          v                                v
release manifests                  S3-compatible object store
          |
          v
public-safe manifest export to toslop-model
```

Use a dedicated PostgreSQL 16 database named `observatory`, not the current
Toslop SQLite file and not the GraphSlop schema. Local development uses an
`observatory-postgres` Compose service on a separate port. Production may use a
managed PostgreSQL service after an operations decision.

Use an `ObjectStore` interface with:

- private S3-compatible storage in production;
- a private content-addressed filesystem adapter for tests and local
  development;
- server-side encryption, object checksum verification, versioning, and
  lifecycle policies;
- no public bucket or direct browser access.

Proposed private code paths:

- `services/gateway/app/observatory/config.py`
- `services/gateway/app/observatory/db.py`
- `services/gateway/app/observatory/source_registry.py`
- `services/gateway/app/observatory/object_store.py`
- `services/gateway/app/observatory/lineage.py`
- `services/gateway/app/observatory/retention.py`
- `services/gateway/migrations/010_observatory_core.sql`
- `services/gateway/tests/observatory/`

## Data contracts

### Source decision

```json
{
  "schema_version": "observatory.source_decision.v1",
  "source_id": "career-pages-example",
  "source_family": "employer_career_page",
  "status": "approved",
  "decision_version": "1.0.0",
  "access_method": "https",
  "terms_url": "https://example.invalid/terms",
  "robots_url": "https://example.invalid/robots.txt",
  "license_id": "source-specific",
  "allowed_purposes": ["s7_research", "s7_aggregate_scoring"],
  "allowed_fields": ["url", "title", "body", "published_at"],
  "raw_retention_days": 365,
  "normalized_retention_days": 365,
  "public_text_allowed": false,
  "public_aggregate_allowed": true,
  "deletion_sla_hours": 72,
  "request_budget": {
    "requests_per_minute": 6,
    "max_concurrency": 1
  },
  "effective_at": "2026-08-01T00:00:00Z",
  "expires_at": "2027-08-01T00:00:00Z",
  "approvals": [
    {
      "role": "governance_reviewer",
      "decision": "approved",
      "evidence_id": "decision-record-id"
    }
  ]
}
```

Reserved source states are `proposed`, `approved`, `restricted`, `suspended`,
`retired`, and `deleted`.

### Core tables

The migration creates these schemas and tables:

| Table | Primary purpose |
| --- | --- |
| `observatory.sources` | Stable source identity and family |
| `observatory.source_decisions` | Immutable versioned rights and operating policy |
| `observatory.collection_runs` | One source/window/collector execution |
| `observatory.raw_objects` | Object key, checksum, media type, size, encryption, retention, and status |
| `observatory.logical_documents` | Source-independent document identity |
| `observatory.document_snapshots` | One immutable observed representation and temporal state |
| `observatory.lineage_edges` | Directed input, output, and transformation relationships |
| `observatory.deletion_events` | Request, scope, status, deadline, and evidence |
| `observatory.release_manifests` | Immutable corpus, feature, benchmark, and score release roots |
| `observatory.audit_events` | Append-only security and governance actions |

Minimum database invariants:

```sql
UNIQUE (source_id, decision_version)
UNIQUE (source_id, collection_window_start, collection_window_end, collector_version)
UNIQUE (sha256, byte_size)
UNIQUE (source_id, source_native_id, observed_at, content_sha256)
CHECK (status IN (...approved enums...))
CHECK (retention_until IS NOT NULL OR legal_hold = true)
CHECK (content_sha256 ~ '^[a-f0-9]{64}$')
```

Database roles:

- `observatory_migrator`: schema changes only;
- `observatory_collector`: source, run, raw-object, and snapshot writes;
- `observatory_transformer`: normalized objects and lineage writes;
- `observatory_reader`: approved analysis reads;
- `observatory_api`: released aggregate and manifest reads only;
- `observatory_governance`: source state, hold, and deletion operations;
- `observatory_auditor`: read-only audit access.

### Object identity

Object keys are opaque and content-addressed:

```text
objects/sha256/ab/cd/<64-lowercase-hex>
```

The database stores source and temporal context. Object keys never contain a
source URL, employer name, personal identifier, secret, or original filename.

### Release manifest

Each manifest contains:

- release ID, type, semantic version, status, and created time;
- parent manifest IDs;
- source-decision versions;
- collection-run IDs;
- schema and transformation versions;
- included and excluded object counts;
- aggregate coverage and exclusion reasons;
- root content hashes;
- required gate results;
- public-safe artifact list;
- approval evidence and retirement state.

## Algorithm design

### Write path

1. Resolve one active source decision for the run time and purpose.
2. Refuse collection when the decision is missing, expired, suspended, or does
   not allow the requested fields and purpose.
3. Stream bytes while calculating SHA-256 and enforcing source-specific size
   limits.
4. Store bytes under the content-addressed key with checksum verification.
5. Insert object metadata and snapshot identity in one database transaction.
6. Record lineage from collection run to raw object and snapshot.
7. Commit a run manifest containing successes, duplicates, exclusions, errors,
   request counts, and policy version.

### Deletion path

1. Resolve all matching raw, normalized, feature, benchmark, and score lineage
   descendants.
2. Mark them `deletion_pending` so new releases cannot include them.
3. Delete eligible objects, revoke access, and write provider deletion
   evidence.
4. Rebuild or retire affected releases according to policy.
5. Retain only a permitted tombstone, hashes, counts, and audit event.
6. Alert when the source-specific SLA would be missed.

### Integrity

Nightly integrity sampling re-hashes at least 1% of active objects and every
object in a pending release. A checksum mismatch quarantines the object and all
dependent releases.

## Implementation tasks

1. Approve a database and object-store decision record.
2. Add observatory configuration with fail-closed secret and URL validation.
3. Add the dedicated local PostgreSQL service and least-privilege roles.
4. Implement forward-only core migration and migration rollback documentation.
5. Implement source-decision model, validation, state transitions, and expiry.
6. Implement filesystem and S3-compatible object-store adapters with streamed
   hashing and byte limits.
7. Implement collection-run, snapshot, lineage, and release-manifest
   repositories.
8. Implement retention, legal-hold, source-suspension, and deletion workflows.
9. Add audit events and metrics.
10. Implement public-safe manifest export with field allowlisting.
11. Run migration, restore, integrity, access-control, and deletion tests.
12. Write operations and incident runbooks.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Source-decision enums, expiry, purpose and field checks, object keys, checksums, state transitions |
| Property | Idempotent writes, duplicate bytes, arbitrary URLs never enter object keys, lineage acyclicity for release roots |
| Database | Constraints, role permissions, concurrent inserts, transaction rollback, migration from empty and prior version |
| Object store | Partial upload, timeout, checksum mismatch, duplicate upload, encryption metadata, missing object |
| Integration | Decision to run to object to snapshot to manifest; suspension and deletion propagation |
| Restore | Restore metadata and sampled objects into an empty environment and verify manifest roots |
| Security | SQL role isolation, SSRF-safe endpoint configuration, secret redaction, path traversal, oversized object |
| Performance | 1,000 object metadata writes per minute and 10 million-row lineage query plan under approved limits |

## Operational design

- Database migrations run once under the migrator role.
- Collectors use idempotency keys from source, window, and collector version.
- Failed object uploads never create an eligible snapshot.
- Retry transient object and database failures with capped exponential backoff;
  policy and validation failures do not retry.
- Dead-letter records include identifiers and error classes, not raw text.
- Metrics: active/expired/suspended sources, run status, bytes, checksum
  failures, orphan objects, retention backlog, deletion SLA, and lineage gaps.
- Alerts: source decision expiry within 14 days, checksum mismatch, orphan
  object, overdue deletion, failed backup, failed restore drill, and audit-log
  write failure.
- Backups: daily metadata backups and object-store versioning; quarterly restore
  drill.

## Security, privacy, rights, and compliance

- Secrets come from the existing private environment or secret manager and are
  never written to source decisions or manifests.
- TLS is required outside local development.
- Database and object-store encryption at rest are required.
- Raw text access is role-limited and audited.
- Source policy is checked at read and write time.
- Personal contact fields are excluded or redacted before durable normalized
  storage under ES-003.
- Public exports are generated from an allowlist, never from database row
  serialization.
- A rights incident suspends source use and dependent releases before
  investigation.

## Release strategy

1. Create local database and filesystem-store fixtures.
2. Run migration and restore tests.
3. Shadow-write synthetic source runs.
4. Run one approved bounded source pilot.
5. Verify deletion and source suspension end to end.
6. Freeze the first storage release manifest.
7. Enable production writes with read-only public export disabled.
8. Roll back by stopping writers, restoring the prior application image, and
   retaining forward-written data under the compatible schema.

Database downgrade is not automatic. Rollback uses forward-compatible
migrations or a reviewed restore.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Expired source decision | Pre-run policy check | Refuse run | Renew or retire decision |
| Object upload succeeds but DB write fails | Orphan scan | Object remains in quarantine | Reconcile or delete orphan |
| DB write succeeds but object is missing | Integrity check | Quarantine snapshot and dependents | Restore object or retire lineage |
| Checksum mismatch | Read or integrity hash | Block object and releases | Restore verified version and investigate |
| Deletion lineage incomplete | Deletion preflight | Block closure and new release | Repair lineage and rerun deletion |
| Backup restore fails | Quarterly drill | Block G5 | Fix backup process and repeat drill |

## Definition of done

1. The exact IS-002 version in `Approved intent reference`, this exact
   execution-spec version, and the infrastructure decisions are approved.
2. Dedicated database, roles, migration, and object-store adapters are
   implemented and documented.
3. Source-policy checks fail closed for missing, expired, suspended, or
   unauthorized decisions.
4. Write, lineage, manifest, retention, hold, suspension, and deletion flows
   pass integration tests.
5. Backup and restore drill reproduces manifest roots.
6. Public-safe export contains no restricted fields or text.
7. Metrics, alerts, runbooks, and rollback evidence exist.
8. An independent security and governance review passes.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Production PostgreSQL provider and region | Data lead | G1 |
| Production object-store provider and region | Data lead | G1 |
| Source-policy approval workflow and evidence system | Governance reviewer | G1 |
| Backup retention and recovery objectives | Operations owner | G5 |
| Maximum object size by source family | Data lead | G1 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval for this exact
execution version and the exact approved intent version.
