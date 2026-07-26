# DR-008: Observatory Delivery Fixture Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G3-G5 fixture and disabled-route bootstrap only |
| Affected spec versions | IS-007 v0.1.0; ES-010 v0.1.0; ES-011 v0.1.0 |
| Supersedes | None |

## Decision

Approve implementation and testing of the release-only read API, disabled public
Worker proxy, and fixture-backed Observatory dashboard without enabling a
public score release.

The approved boundary includes:

- a PostgreSQL score-output table and security-barrier public view that admits
  only validated or released manifests, validated or production score states,
  and unsuppressed outputs;
- an in-memory store requiring an explicit approved-release allowlist;
- strict score and series queries, signed query-bound cursors, stable ordering,
  ETags, release metadata, coverage, methodology, and health;
- an authenticated Worker proxy with exact path and query allowlists, timeout,
  redirect, byte, schema, field, and error controls;
- JSON and CSV exports bounded to the validated series response;
- an `/observatory/` research interface with separate S7 and S3 modes, release
  state, filters, trend, interval, table equivalent, components, coverage,
  warnings, versions, methods, benchmark, and release links;
- deterministic Node, Python, Worker dry-run, and browser fixture tests.

## Prohibited uses

This decision does not enable `OBSERVATORY_API_ENABLED`, approve a private
upstream host or secret, admit an empirical release, approve public entities or
additional source frames, or authorize workers.dev or custom-domain production
cutover.

Contract fixtures are interface evidence only. Their values and apparent trend
are not observed research results and must never be deployed as public data.

## Expansion gate

Production activation requires approved S7 or S3 scorer and corpus releases,
benchmark and claims review, public dimension policy, deployed release-only
database role, upstream service authentication, cache and rate policy,
accessibility and browser acceptance, alerts, rollback evidence, and explicit
G5 approval.

## Approval evidence

Ryan Cook's instruction on 2026-07-25 to create todos for every spec and build
them, constrained by DR-001 through DR-007 and the G0-G5 release gates.
