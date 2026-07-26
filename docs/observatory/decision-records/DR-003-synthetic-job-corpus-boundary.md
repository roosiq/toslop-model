# DR-003: Synthetic Job-Corpus Implementation Boundary

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G1 development and G2 bootstrap |
| Affected spec versions | IS-002 v0.1.0; ES-003 v0.1.0 |
| Supersedes | None |

## Decision

Approve ES-003 v0.1.0 for deterministic synthetic-shadow implementation and
bootstrap testing only.

The approved implementation boundary includes:

- canonical collector, fetch-envelope, source-record, private normalized
  posting, and job-posting snapshot contracts;
- a bounded HTTP client with HTTPS and host allowlists, public-address
  validation, robots authorization, redirect and timeout bounds, response byte
  limits, source request budgets, and an identifying user agent;
- a deterministic synthetic source adapter;
- contact and tracking-data minimization before normalized persistence;
- exact and provisional near-duplicate clustering;
- reviewed-alias employer resolution and versioned occupation mapping with
  abstention;
- synthetic corpus release manifests, coverage, immutable lineage, idempotent
  reruns, queue contracts, retries, quarantine, and text-free dead letters.

This decision does not approve:

- any real network collection or source adapter;
- production collection credentials or schedules;
- the provisional near-duplicate threshold as a frozen G2 threshold;
- employer parent or subsidiary rollups;
- a production occupation taxonomy;
- a publishable corpus, historical backfill, or S7 score release.

## Rationale

ES-002 supplies the private storage and policy boundary needed to test the full
corpus path without accessing a real source. Implementing the synthetic path
now exposes schema, privacy, lineage, idempotency, and operational failures
before source-specific legal and governance decisions are available.

## Evidence required to expand

Each real adapter still requires an approved source decision that names its
access method, hosts, fields, purposes, retention, deletion behavior, request
budget, and terms and robots evidence. G2 threshold freeze still requires the
ES-009 development benchmark.

## Approval evidence

Ryan Cook's instruction on 2026-07-25 to create todos for every spec and begin
building them, constrained by DR-001 and DR-002.
