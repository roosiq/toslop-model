# Observatory Build Work Queue

This is the implementation ledger for every current intent and execution spec.
Checkboxes close only when linked code, tests, and evidence exist. Approval to
implement is recorded in
[DR-001](decision-records/DR-001-implementation-directive.md); public release
still requires the narrower G1-G5 gates.

## Program status

| Spec | Build todo | State | Evidence |
| --- | --- | --- | --- |
| IS-001 | Freeze ontology and shared reporting semantics | In progress | ES-001 implementation |
| IS-002 | Deliver compliant job-posting corpus foundation | In progress | ES-002, ES-003 |
| IS-003 | Deliver Employer AI Compulsion scorer | Bootstrap implementing | ES-004, ES-005 |
| IS-004 | Deliver controlled professional-writing corpus | Queued | ES-006 |
| IS-005 | Deliver Language Homogenization scorer | Queued | ES-007, ES-008 |
| IS-006 | Deliver synthetic, labeled, and protected benchmark | Queued | ES-009 |
| IS-007 | Deliver research API and dashboard | Queued | ES-010, ES-011 |
| IS-008 | Close administration conformance and production gates | Implementing | ES-012, ES-013, ES-014 |
| ES-001 | Build score registries and cross-runtime contract validation | Complete | RR-CONTRACT-v1.0.0 |
| ES-002 | Build source registry and immutable snapshot storage | Foundation complete | PostgreSQL and object-store tests; infra PR #12 |
| ES-003 | Build bounded job-posting collectors and normalization | Synthetic shadow complete | 21-test observatory suite; infra PR #12 |
| ES-004 | Build S7 extraction model and evidence lineage | Synthetic bootstrap complete | 32-test suite; `bootstrap-rule-v0` |
| ES-005 | Build S7 aggregation, uncertainty, and release artifacts | Synthetic formula complete | 37-test suite; suppressed contract projection |
| ES-006 | Build professional-writing corpus pipeline | Queued | Pending |
| ES-007 | Build S3 linguistic feature and control pipeline | Queued | Pending |
| ES-008 | Build S3 aggregation, uncertainty, and release artifacts | Queued | Pending |
| ES-009 | Build benchmark, protected evaluation, and gate engine | Queued | Pending |
| ES-010 | Build private read API and public Worker proxy | Queued | Pending |
| ES-011 | Build and release the Observatory dashboard | Queued | Pending |
| ES-012 | Close Astro admin interface conformance | Implementing | Existing admin UI and browser tests |
| ES-013 | Replace broad credential and close workflow conformance | Implementing | API contract and failure suite |
| ES-014 | Replace Basic Auth, add external alerts, run recovery drills | Blocked externally | Access permission and alert destination |

## ES-001 checklist

- [x] Record implementation authorization without waiving release gates.
- [x] Freeze score, warning, evidence-class, release, and version-bridge
  registries at `1.0.0`.
- [x] Add positive fixtures for S1-S8 and special evidence/version states.
- [x] Add required negative semantic fixtures.
- [x] Implement private Pydantic models and semantic validation.
- [x] Implement public Worker schema and semantic validation.
- [x] Implement checksum-locked mirroring.
- [x] Add Python and JavaScript conformance tests.
- [x] Generate public registry reference documentation.
- [x] Record contract release and rollback evidence.

## Remaining scorer-spec backlog

The parent plan defines six post-MVP scorers that do not yet have dedicated
intent or execution specs. They remain explicit build todos:

- [ ] S1 External Exploration intent, execution specs, implementation, and
  validation.
- [ ] S2 Source Concentration intent, execution specs, implementation, and
  validation.
- [ ] S4 Perspective Diversity intent, execution specs, implementation, and
  validation.
- [ ] S5 Model-Language Diffusion intent, execution specs, implementation, and
  validation.
- [ ] S6 Human Knowledge Contribution intent, execution specs, implementation,
  and validation.
- [ ] S8 Novel Information Density intent, execution specs, implementation, and
  validation.

## ES-002 checklist

- [x] Approve the local development and synthetic-shadow storage boundary.
- [x] Implement fail-closed database and object-store configuration.
- [x] Add dedicated loopback PostgreSQL 16 Compose service.
- [x] Add forward-only core migration and least-privilege role grants.
- [x] Implement source-decision validation, expiry, purpose, field, and state
  controls.
- [x] Implement bounded content-addressed filesystem and injected
  S3-compatible adapters.
- [x] Implement collection-run, object, snapshot, lineage, release, and audit
  repository boundaries.
- [x] Implement legal hold, source suspension, retention expiry, descendant
  deletion, and release retirement for synthetic shadow state.
- [x] Implement allowlisted public manifest export.
- [x] Run unit, integrity, migration idempotency, and API-role isolation tests.
- [ ] Run backup/restore and deletion workflows against PostgreSQL plus an
  S3-compatible test service.
- [ ] Select production providers, regions, recovery objectives, and alert
  destinations.
- [ ] Approve one source-specific decision before any real pilot.

## ES-003 checklist

- [x] Approve the synthetic-shadow implementation boundary.
- [x] Define strict collection-window, task, envelope, source-record, private
  normalized posting, and canonical snapshot contracts.
- [x] Implement a bounded HTTPS client with host, DNS, robots, redirect,
  timeout, response-size, request-budget, and user-agent controls.
- [x] Implement a deterministic synthetic adapter and end-to-end corpus build.
- [x] Remove personal contacts and tracking parameters before normalized
  persistence, including punctuation-boundary regression coverage.
- [x] Implement exact grouping and deterministic provisional MinHash plus
  Jaccard near-duplicate clustering.
- [x] Implement versioned reviewed-alias employer resolution and occupation
  mapping with ambiguous and unresolved states.
- [x] Emit synthetic-shadow coverage, release, object, snapshot, and lineage
  records with deterministic reruns.
- [x] Add four named queues, retry and quarantine classification, and text-free
  dead-letter contracts.
- [x] Add the disabled-by-default `observatory-worker` Compose service.
- [ ] Calibrate and freeze near-duplicate thresholds on the ES-009 development
  partition.
- [ ] Approve and implement the first real source adapter.
- [ ] Complete bounded one-month pilot and one-year two-source-family shadow.
- [ ] Meet final deduplication, employer, occupation, privacy, performance, and
  release gates.

## ES-004 checklist

- [x] Approve a synthetic-only source-blind bootstrap boundary.
- [x] Define the six-level primary enum, fixed class order, mechanism flags,
  context masks, private offsets, and no-text public packet.
- [x] Implement deterministic sentence segmentation and source-blind runtime
  signature.
- [x] Implement high-precision rule candidates for all primary levels and seven
  mechanism families.
- [x] Mask negation, quotation, third-party, and historical-only context.
- [x] Add product-development and general-discussion hard negatives.
- [x] Implement provisional highest-qualifying-passage document aggregation
  with complete private passage lineage.
- [x] Mark every candidate output `bootstrap_only`.
- [x] Test all levels, mechanisms, context, ambiguity, determinism, offsets,
  source blindness, and public artifact hygiene.
- [ ] Freeze the adjudicated rubric, ambiguity margin, and conflict policy
  through ES-009 development evidence.
- [ ] Build and compare the predeclared linear classifier.
- [ ] Run the protected final benchmark and required slice gates.
- [ ] Package a checksum-verified shadow artifact and run real-corpus drift and
  throughput review.

## ES-005 checklist

- [x] Approve synthetic-only formula implementation and fail-closed release
  behavior.
- [x] Implement strict baseline registry validation and approved-state checks.
- [x] Implement logical-document deduplication and conflict rejection.
- [x] Implement within-cell employer balancing and baseline-composition
  standardization.
- [x] Implement all level shares, required and enforcement prevalence,
  mechanism prevalence, ambiguity, resolution, and matched-weight diagnostics.
- [x] Implement effective sample size and production-default suppression gates.
- [x] Implement deterministic employer-cluster bootstrap.
- [x] Implement current-composition, document, source, and occupation
  sensitivities.
- [x] Prove endpoint, monotonicity, permutation, duplicate, balancing,
  determinism, and suppression behavior with synthetic tests.
- [x] Validate a bootstrap score-contract projection that nulls every reportable
  value.
- [ ] Approve real baseline dates, cell weights, effective-sample threshold,
  and sensitivity tolerances.
- [ ] Run real baseline and current backfills with a frozen ES-004 artifact.
- [ ] Complete protected benchmark, event validation, monitoring, and release
  review.
