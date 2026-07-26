# ES-010: Observatory Read API and Worker Proxy

| Field | Value |
| --- | --- |
| Status | Fixture and disabled-route implementation complete; activation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Backend lead |
| Approved intent reference | IS-007 v0.1.0, fixture boundary approved by DR-008 |
| Repositories | `slopslingers-infra`, `toslop` |
| Gates | G3, G5 |
| Start prerequisites | ES-001 stable contract candidate |
| Stage interfaces | Released ES-005/ES-008 scores; fixture and live routes to ES-011 |

## Implementation authorization

Fixture and disabled-route implementation is authorized by DR-008.
Production data routes remain disabled until at least one S7 or S3 release is
approved for public access and the public entity/filter policy is approved.

## Outcome

Provide a read-only private FastAPI service for released observatory aggregates
and a same-origin Cloudflare Worker proxy that authenticates upstream, validates
and minimizes responses, caches safe GET requests, supports bounded JSON/CSV
exports, and never exposes private credentials or diagnostics.

## Current state

- `slopslingers-infra/services/gateway/app/main.py` composes FastAPI routers.
- Private product routes already require gateway authentication patterns.
- `toslop/src/index.js` proxies the current summary and scoring services and
  includes strict bounded-response handling and public regression tests.
- `toslop/wrangler.jsonc` is the public Worker source of truth.
- Private release-only routes, query policy, signed pagination, ETags, metadata,
  coverage, health, and an empty-by-default store now exist.
- The Worker proxy now enforces exact routes and queries, upstream
  authentication, bounded reads, shared-contract validation, aggregate
  minimization, public-safe errors, and JSON or CSV output.
- `OBSERVATORY_API_ENABLED` defaults to `false`; no public score is activated.

## Architecture and boundaries

The diagram below is the proposed private-API plus same-origin Worker option. It
does not resolve IS-007's API-versus-static-artifact decision. Execution
approval must link a decision record accepting this topology or revise this spec
to the approved static or hybrid topology.

```text
browser
  |
  v
toslop Worker /api/observatory/v1/*
  |  allowlist query, cache, timeout, size, schema, redaction
  |  private service credential
  v
model-api private gateway /observatory/v1/*
  |  release-only database role
  v
released score and manifest tables
```

Private paths:

- `services/gateway/app/observatory/api.py`
- `services/gateway/app/observatory/api_models.py`
- `services/gateway/app/observatory/queries.py`
- `services/gateway/tests/observatory/test_api.py`

Public paths:

- `toslop/src/observatory-api.js`
- `toslop/scripts/check-observatory-api.mjs`
- mirrored contracts under `toslop/public/observatory/contracts/`

The public browser never calls the private gateway directly.

## Data contracts

### Private endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /observatory/v1/scores/{score_id}` | One released result by full analytical key |
| `GET /observatory/v1/series/{score_id}` | Bounded time series |
| `GET /observatory/v1/coverage/{score_id}` | Public-safe coverage and freshness |
| `GET /observatory/v1/releases/{score_id}` | Released scorer and comparability metadata |
| `GET /observatory/v1/methodology/{score_id}` | Versioned methods and benchmark links |
| `GET /observatory/v1/health` | Dependency and release freshness for the Worker |

Allowed series query parameters:

- `entity_type`, `entity_id`;
- `topic_id`;
- `source_frame_id`;
- `period_start`, `period_end`;
- `granularity`;
- `release_state`;
- `limit` in `[1, 500]`;
- opaque `cursor`.

Only allowlisted public dimensions are accepted. Unknown parameters return 400.
Entity parameters return 404 unless the publication registry permits them.

### Series response

```json
{
  "schema_version": "observatory.series.v1",
  "score_id": "S7",
  "query": {
    "entity_type": "global",
    "entity_id": "global",
    "source_frame_id": "s7-public-job-postings",
    "granularity": "month"
  },
  "results": [],
  "next_cursor": null,
  "release": {
    "id": "release:...",
    "version": "1.0.0",
    "last_successful_calculation": "2026-07-25T12:00:00Z"
  }
}
```

Every result validates against ES-001. The Worker returns a reduced allowlisted
copy, not the raw private JSON object.

### Public routes

- `/api/observatory/v1/scores/{score_id}`
- `/api/observatory/v1/series/{score_id}`
- `/api/observatory/v1/coverage/{score_id}`
- `/api/observatory/v1/releases/{score_id}`
- `/api/observatory/v1/methodology/{score_id}`
- `/api/observatory/v1/exports/{score_id}.json`
- `/api/observatory/v1/exports/{score_id}.csv`

The public health view is folded into `/health` and exposes no private
dependency names.

### Errors

```json
{
  "schema_version": "observatory.public_error.v1",
  "status": "unavailable",
  "code": "UPSTREAM_UNAVAILABLE",
  "message": "Observatory data is temporarily unavailable.",
  "request_id": "public-opaque-id",
  "last_successful_calculation": "2026-07-25T12:00:00Z"
}
```

Public errors do not echo an upstream body, URL, status text, stack trace,
header, SQL, object key, or request query.

## Algorithm design

### Private query path

1. Validate query with strict Pydantic models.
2. Resolve one public release and allowed dimension policy.
3. Query through the read-only `observatory_api` database role.
4. Validate stored score JSON against ES-001.
5. Return stable sort by period, analytical key, and result ID.
6. Build opaque HMAC cursor from sort key and query hash.
7. Set `ETag` from response release ID and canonical query.

No endpoint accepts arbitrary SQL, filter expressions, field selection, or
sort expressions.

### Worker proxy

1. Match exact method and path.
2. Reject bodies on GET and unknown parameters.
3. Normalize and bound query values.
4. Add private `OBSERVATORY_API_KEY` server-side.
5. Fetch with 10-second timeout, redirect disabled, and 1 MiB response limit.
6. Parse JSON through a bounded streaming read.
7. Validate schema, registry, evidence, and public fields.
8. Return same-origin response with security, cache, ETag, and CORS policy.
9. On failure, return the bounded public error and optionally serve an approved
   stale cache entry.

### Caching

- Cache only public GET 200 responses.
- Proposed TTL: 15 minutes, stale-if-error 24 hours.
- Cache key includes path, canonical query, contract version, and public release
  ID.
- `ETag` and `If-None-Match` support 304.
- Never cache private upstream errors, headers, credentials, or unvalidated
  bytes.
- A release retirement or rights suspension purges affected keys.

### Exports

Exports use the same query and released rows as series:

- maximum 5,000 result rows and approved period range;
- stable column order;
- UTF-8, RFC 4180 CSV with formula-injection-safe cells;
- JSON export includes contract and query metadata;
- licensing and methods link in headers or sidecar metadata;
- no suppressed score converted to zero.

## Implementation tasks

1. Approve public query, dimension, entity, cache, export, and stale-data
   policies.
2. Implement release-only database views and role grants.
3. Implement private models, queries, cursors, ETag, and endpoints.
4. Add private auth and rate limits.
5. Mirror ES-001 contracts into `toslop` with checksum validation.
6. Implement Worker route allowlist, bounded fetch, schema validation,
   minimization, cache, and public errors.
7. Implement bounded JSON and CSV exports.
8. Add unit, integration, security, and current-route regression tests.
9. Shadow against synthetic and released fixture data.
10. Add metrics, alerts, cache purge, and rollback runbooks.
11. Deploy private API disabled, then Worker routes disabled.
12. Enable per approved score release.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Private unit | Query validation, publication policy, cursor, stable sort, ETag, release resolution |
| Private integration | PostgreSQL views and least-privilege role, score validation, pagination |
| Worker unit | Path/query allowlist, timeout, size, redirect, JSON, unknown field, public error |
| Contract | All ES-001 positive and negative fixtures at both boundaries |
| Export | CSV escaping and injection, stable columns, row limits, suppressed nulls |
| Security | Missing/wrong secret, key never returned, diagnostic redaction, cache isolation, hostile query |
| Performance | Cached p95 under 500 ms; uncached private series p95 under 1 second for 120 points |
| Regression | Existing `/`, `/summary.json`, `/model/`, `/health`, and score routes |

## Operational design

- Private metrics: request count, latency, query rows, validation errors,
  publication-policy denial, cursor errors, release and database freshness.
- Worker metrics: cache hit, upstream latency, timeout, oversized response,
  schema rejection, stale serve, and public error code.
- Alerts: validation rejection, credential failure, stale data over 24 hours,
  release mismatch, 5xx rate over threshold, or cache purge failure.
- Rate limits apply by public client IP hash and route without retaining raw IP
  beyond operational policy.
- Backfill publication is atomic by release ID.

## Security, privacy, rights, and compliance

- `OBSERVATORY_API_KEY` is a Worker secret and private gateway secret.
- Private routes use TLS and an allowlisted service identity.
- Public data comes from release-only views with disclosure thresholds.
- Unknown dimensions and entity IDs fail closed.
- CSV values beginning with `=`, `+`, `-`, or `@` are prefixed safely.
- Logs omit query values that may identify restricted entities.
- Rights suspension removes a release before cache purge and public access.

## Release strategy

1. Synthetic private API and Worker tests.
2. Private API deploy with no public routes enabled.
3. Worker deploy with routes returning explicit not-released state.
4. Shadow requests using synthetic release.
5. Enable one experimental score to allowlisted reviewers.
6. Run security, load, and stale-cache exercises.
7. Enable public read routes after G5.
8. Verify workers.dev and `toslop.com` separately.
9. Roll back Worker first, then private API; restore prior release ID and purge
   new cache keys.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Upstream sends unknown/private fields | Worker schema/allowlist | Reject and return bounded error or stale | Fix private serializer |
| Query becomes expensive | Timeout and query metrics | Return unavailable; no partial rows | Add approved index or narrower bound |
| Release retired while cached | Release event and purge | Remove route/cache | Purge and activate prior release |
| Cursor forged or stale | HMAC/query check | Return 400 | Restart pagination |
| CSV formula injection | Export test | Escape cell | Fix exporter and regenerate |
| Custom-domain route fails after deploy | Separate canary | Keep workers.dev evidence, report domain failure | Correct Cloudflare route permission/config |

## Definition of done

1. The exact IS-007 version in `Approved intent reference`, this exact
   execution-spec version, and the public policies are approved.
2. Private release-only endpoints and roles pass tests.
3. Worker validates, minimizes, bounds, caches, and redacts all responses.
4. JSON and CSV exports match rendered values and contracts.
5. Current Toslop route regression suite passes.
6. Load, security, stale-data, purge, and rollback exercises pass.
7. Metrics, alerts, methods, and operations docs are complete.
8. workers.dev and custom-domain verification pass independently.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Private API plus Worker, static release artifacts, or a hybrid | Data lead and product owner | Execution approval |
| Public entity and dimension allowlist | Governance reviewer | G5 |
| Private API host and authentication method | Backend lead | G5 |
| Cache TTL and stale-if-error duration | Operations owner | G5 |
| Export row/range limits | Product owner and governance reviewer | G5 |
| Public rate-limit policy | Operations owner | G5 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Fixture and disabled-route execution is complete under DR-008. Production
activation remains blocked until this table records approval for this exact
execution version, the exact approved intent version, and the public policies.
