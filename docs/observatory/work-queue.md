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
| IS-003 | Deliver Employer AI Compulsion scorer | Queued | ES-004, ES-005 |
| IS-004 | Deliver controlled professional-writing corpus | Queued | ES-006 |
| IS-005 | Deliver Language Homogenization scorer | Queued | ES-007, ES-008 |
| IS-006 | Deliver synthetic, labeled, and protected benchmark | Queued | ES-009 |
| IS-007 | Deliver research API and dashboard | Queued | ES-010, ES-011 |
| IS-008 | Close administration conformance and production gates | Implementing | ES-012, ES-013, ES-014 |
| ES-001 | Build score registries and cross-runtime contract validation | In progress | Pending |
| ES-002 | Build source registry and immutable snapshot storage | In progress | Local foundation and migration tests |
| ES-003 | Build bounded job-posting collectors and normalization | Queued | Pending |
| ES-004 | Build S7 extraction model and evidence lineage | Queued | Pending |
| ES-005 | Build S7 aggregation, uncertainty, and release artifacts | Queued | Pending |
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
