# ES-003: Job-Posting Collectors and Normalization

| Field | Value |
| --- | --- |
| Status | Synthetic-shadow implementation complete; real collection blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Data lead |
| Approved intent reference | IS-002 v0.1.0, foundation implementation scope |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G1, G2 |
| Start prerequisites | ES-002 storage readiness |
| Stage interfaces | Bootstrap records to ES-009; frozen corpus to ES-004 |

## Implementation authorization

Synthetic-shadow implementation is approved by DR-003 after IS-002 foundation
approval and ES-002 storage readiness. Each real collector remains disabled
until its source decision authorizes the exact access method, fields, purpose,
retention, and rate budget.

## Outcome

Provide versioned source adapters that collect bounded windows, retain immutable
observations, normalize eligible employer language, remove personal contact
fields and tracking data, deduplicate logical postings, resolve employer and
occupation identities, and emit corpus-release manifests.

## Current state

- The private project has HTTP, HTML extraction, Redis, RQ, PostgreSQL, and
  text-processing dependencies.
- `slopslingers-infra/services/worker/app/worker.py` runs generic RQ queues, but
  its ingest job is currently a placeholder.
- The existing Toslop crawl store and crawlers target AI-likeness page
  measurement, not a source-governed longitudinal job-posting corpus.
- No approved source adapters or job-posting canonical schema exist.

## Architecture and boundaries

```text
RQ scheduler
   |
   v
source adapter --> fetch envelope --> immutable raw object
                                       |
                                       v
                         parser + field minimization
                                       |
                                       v
                         canonical snapshot + quality
                                       |
                                       v
                    exact/near duplicate clustering
                                       |
                                       v
                    employer/occupation resolution
                                       |
                                       v
                             corpus release manifest
```

Implement the domain under
`slopslingers-infra/services/gateway/app/observatory/` and run an
`observatory-worker` Compose service from the same gateway image. Add `rq` to
the gateway's private dependencies. This keeps collector, normalization, and
repository code in one package while preserving the current generic worker.

Proposed modules:

- `collectors/base.py`
- `collectors/http.py`
- `collectors/<approved-source>.py`
- `jobs.py`
- `normalization/job_posting.py`
- `normalization/text.py`
- `dedup/exact.py`
- `dedup/near.py`
- `entities/employers.py`
- `entities/occupations.py`
- `corpora/job_postings.py`

## Data contracts

### Collector adapter

```python
class CollectorAdapter(Protocol):
    source_id: str
    collector_version: str

    def plan(self, window: CollectionWindow, decision: SourceDecision) -> list[FetchTask]: ...
    def fetch(self, task: FetchTask, client: BoundedHttpClient) -> FetchEnvelope: ...
    def parse(self, envelope: FetchEnvelope) -> list[SourceRecord]: ...
```

`BoundedHttpClient` enforces approved hostnames, schemes, redirect limits,
timeouts, body limits, request budgets, user agent, and robots refresh.

### Canonical job-posting snapshot

```json
{
  "schema_version": "observatory.job_posting_snapshot.v1",
  "snapshot_id": "snap:sha256:...",
  "logical_document_id": "job:...",
  "source_id": "source-alias",
  "source_native_id": "opaque-source-id",
  "canonical_url": "https://example.invalid/jobs/123",
  "observed_at": "2026-07-25T12:00:00Z",
  "published_at": "2026-07-20T00:00:00Z",
  "expires_at": null,
  "language": {
    "code": "en",
    "confidence": 0.99,
    "detector_version": "1.0.0"
  },
  "employer": {
    "raw_hash": "sha256:...",
    "entity_id": "employer:...",
    "resolution_status": "resolved",
    "confidence": 0.98,
    "registry_version": "1.0.0"
  },
  "occupation": {
    "taxonomy_id": "taxonomy:occupation:...",
    "status": "resolved",
    "confidence": 0.91,
    "taxonomy_version": "1.0.0"
  },
  "content": {
    "raw_object_id": "object:...",
    "normalized_object_id": "object:...",
    "content_sha256": "...",
    "normalized_sha256": "...",
    "word_count": 642
  },
  "dedup": {
    "exact_cluster_id": "exact:...",
    "near_cluster_id": "near:...",
    "logical_weight": 1.0,
    "dedup_version": "1.0.0"
  },
  "rights": {
    "source_decision_version": "1.0.0",
    "allowed_purposes": ["s7_research", "s7_aggregate_scoring"],
    "retention_until": "2027-07-25T00:00:00Z",
    "public_text_allowed": false
  },
  "quality": {
    "status": "eligible",
    "reasons": [],
    "pipeline_version": "1.0.0"
  }
}
```

The private normalized object contains title, employer-authored body segments,
field boundaries, and offsets. It does not retain email addresses, phone
numbers, tracking query parameters, application tokens, or applicant data.

### Stable IDs

- `snapshot_id`: SHA-256 over source ID, native ID or canonical URL, observed
  time, and content checksum.
- `logical_document_id`: source-independent cluster identity assigned after
  exact and near-duplicate review.
- `collection_run_id`: source, window, collector version, and retry generation.
- Resolution IDs never depend on a mutable display name alone.

## Algorithm design

### Collection

1. Load one active source decision.
2. Plan an explicit time or cursor window.
3. Fetch through the bounded client.
4. Store response bytes before parsing.
5. Parse into source records and preserve parser errors as no-text diagnostics.
6. Record a complete or partial run manifest.

Retries reuse the same idempotency key. A retry does not create a new logical
observation unless bytes or source state changed.

### Normalization

1. Canonicalize URL by source-specific allowlisted rules.
2. Parse title and employer-authored content boundaries.
3. Remove navigation, cookie text, application UI, personal contacts, tracking
   parameters, and repeated boilerplate.
4. Normalize Unicode, whitespace, and line boundaries without paraphrasing.
5. Detect language and reject unsupported or low-confidence text.
6. Calculate raw and normalized hashes and quality metrics.
7. Persist normalized text privately only when the source policy allows it.

### Deduplication

1. Exact grouping by normalized content SHA-256.
2. Candidate generation using deterministic MinHash signatures over normalized
   token shingles.
3. Candidate confirmation with token Jaccard and length-ratio thresholds frozen
   from the benchmark.
4. Cluster revisions and cross-source reposts while retaining all observations.
5. Assign one logical contribution weight per approved aggregation policy.

Thresholds are tuned on the ES-009 development partition and frozen before the
final benchmark.

### Entity resolution

Employer resolution uses exact identifiers and reviewed aliases first, then
normalized name, registered domain, location, and parent/subsidiary evidence.
Auto-resolution requires the approved precision threshold. Ambiguous results
remain unresolved.

Occupation mapping uses title and eligible description fields against a pinned
taxonomy. Source, time, and S7 labels are not inputs.

## Implementation tasks

1. Define source-adapter and canonical-snapshot schemas and fixtures.
2. Implement bounded HTTP client, robots cache, rate budget, redirect, timeout,
   and byte-limit behavior.
3. Implement one synthetic adapter and end-to-end pipeline.
4. Implement source adapters one at a time after decision approval.
5. Implement text minimization, language, quality, and eligibility pipeline.
6. Implement exact and near-duplicate signatures, clustering, and versioning.
7. Implement employer registry, alias review, and resolution evidence.
8. Implement occupation taxonomy import, mapping, and unresolved state.
9. Implement job corpus release manifests and coverage reports.
10. Add RQ queues, schedules, retries, dead-letter state, metrics, and alerts.
11. Run a bounded one-month pilot, then one-year shadow backfill.
12. Freeze corpus 1.0.0 only after G1 and benchmark evidence pass.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | URL rules, robots state, field minimization, language, IDs, quality, source policy, parser fixtures |
| Property | Idempotent retry, deterministic normalization, URL tracking removal, contacts never survive normalization |
| Collector integration | Pagination, cursor resume, 304, 404, 429, 5xx, timeout, redirect, oversized body, parser drift |
| Dedup benchmark | Exact 100% and near-duplicate pairwise F1 at least 0.98 |
| Employer benchmark | Precision at least 0.95, unresolved behavior, parent/subsidiary cases |
| Occupation benchmark | Approved macro F1 or top-k threshold and low-confidence abstention |
| Database/object | Run to raw to normalized to cluster to release lineage |
| Privacy | Personal contact and tracking-token fixtures absent from durable normalized and public artifacts |
| Performance | Approved bounded source rate and one million-record dedup batch within the execution budget |

## Operational design

- Queues: `observatory-collect`, `observatory-normalize`,
  `observatory-resolve`, and `observatory-release`.
- Schedule source runs by decision record; no source has a global default rate.
- Transient HTTP and infrastructure failures retry with capped exponential
  backoff and jitter.
- Policy, robots, schema, checksum, and privacy failures quarantine without
  retry.
- Dead-letter payloads contain task IDs and error codes, not text.
- Metrics: request status, latency, bytes, run completeness, parse yield,
  eligibility, duplicates, unresolved employers and occupations, field
  missingness, source mix, and queue age.
- Alert on expired policy, robots change, 429 spike, parser yield drop over 20%,
  eligible-rate drop over 20%, contact-redaction failure, or queue age over the
  approved SLA.
- Backfills use explicit immutable windows and can pause without losing cursor
  state.

## Security, privacy, rights, and compliance

- Allowlisted HTTPS hosts only; DNS resolution and redirects are revalidated to
  prevent SSRF.
- Source credentials use secret storage and are unavailable to parser code when
  not needed.
- Robots and terms evidence are snapshotted as policy metadata where permitted.
- No applicant, resume, private recruiter, or monitoring data is collected.
- Personal contact removal runs before normalized persistence and has
  fail-closed tests.
- Public manifests contain aliases, counts, versions, and checksums only.

## Release strategy

1. Synthetic end-to-end run.
2. One approved source, one week, private-only.
3. One approved source, one month, benchmark and privacy review.
4. Two independent approved source families, one year, shadow corpus.
5. Historical backfill after source-mix and baseline review.
6. Freeze corpus release with checksums and coverage.
7. Roll back by suspending source jobs, retaining immutable evidence, and
   returning the previous corpus manifest to active status.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Source markup changes | Parse-yield and field drift | Quarantine affected run | Update parser, benchmark, and version |
| Robots or terms change | Policy refresh | Suspend collector | Governance review |
| Cursor skips or repeats | Window and source-ID audit | Mark run partial | Repair planner and rerun fixed window |
| Duplicate explosion | Cluster and logical ratio drift | Block release | Inspect templates and retune on development set |
| Employer false merge | Resolution review | Keep affected entities unresolved and retire bad mapping | Correct registry and rebuild |
| Contact data survives | Privacy test or scan | Quarantine objects and block release | Delete, fix minimizer, rerun |

## Definition of done

1. The exact IS-002 version in `Approved intent reference`, this exact
   execution-spec version, and the source decisions are approved.
2. Canonical snapshots validate and retain complete lineage.
3. Collectors are bounded, idempotent, policy-aware, and resumable.
4. Normalized durable text contains none of the prohibited personal or tracking
   fields in the final privacy benchmark.
5. Deduplication and resolution meet IS-002 thresholds.
6. Coverage reports and release manifests reproduce the corpus.
7. One-year shadow and required historical coverage pass G1.
8. Metrics, alerts, backfill, suspension, deletion, and rollback runbooks pass.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| First approved sources and adapters | Data lead and governance reviewer | G1 |
| Near-duplicate shingle and threshold policy | Applied science lead | G2 |
| Employer parent/subsidiary rollup policy | Research lead | G1 |
| Occupation taxonomy and version | Research lead | G1 |
| Source-specific request and byte budgets | Data lead | G1 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for synthetic-shadow implementation; real collection blocked |
| Approved execution version | 0.1.0 synthetic scope |
| Approved intent version | IS-002 v0.1.0 foundation implementation scope |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | DR-001, DR-002, and DR-003 |

Real adapters, source pilots, threshold freeze, and corpus release remain
blocked by their source-specific G1 decisions and ES-009 G2 evidence.
