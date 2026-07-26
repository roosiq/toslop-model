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
| IS-004 | Deliver controlled professional-writing corpus | Synthetic bootstrap complete | ES-006 |
| IS-005 | Deliver Language Homogenization scorer | Synthetic bootstrap complete | ES-007, ES-008 |
| IS-006 | Deliver synthetic, labeled, and protected benchmark | Framework implementing | ES-009 |
| IS-007 | Deliver research API and dashboard | Fixture delivery complete | ES-010, ES-011 |
| IS-008 | Close administration conformance and production gates | Implementing | ES-012, ES-013, ES-014 |
| IS-009 | Deliver External Exploration scorer | Synthetic formula complete; empirical build blocked | ES-015 |
| IS-010 | Deliver Source Concentration scorer | Synthetic formula complete; empirical build blocked | ES-016 |
| IS-011 | Deliver Perspective Diversity scorer | Synthetic formula complete; empirical build blocked | ES-017 |
| IS-012 | Deliver Model-Language Diffusion scorer | Synthetic formula complete; provider capture blocked | ES-018 |
| IS-013 | Deliver Human Knowledge Contribution scorer | Synthetic formula complete; real collection blocked | ES-019 |
| IS-014 | Deliver Novel Information Density scorer | Synthetic formula complete; real extraction blocked | ES-020 |
| ES-001 | Build score registries and cross-runtime contract validation | Complete | RR-CONTRACT-v1.0.0 |
| ES-002 | Build source registry and immutable snapshot storage | Foundation complete | PostgreSQL and object-store tests; infra PR #12 |
| ES-003 | Build bounded job-posting collectors and normalization | Synthetic shadow complete | 21-test observatory suite; infra PR #12 |
| ES-004 | Build S7 extraction model and evidence lineage | Synthetic bootstrap complete | 32-test suite; `bootstrap-rule-v0` |
| ES-005 | Build S7 aggregation, uncertainty, and release artifacts | Synthetic formula complete | 37-test suite; suppressed contract projection |
| ES-006 | Build professional-writing corpus pipeline | Synthetic corpus complete | 50-test observatory suite |
| ES-007 | Build S3 linguistic feature and control pipeline | Synthetic fallbacks complete | 50-test observatory suite |
| ES-008 | Build S3 aggregation, uncertainty, and release artifacts | Synthetic formula complete | 50-test suite; suppressed contract projection |
| ES-009 | Build benchmark, protected evaluation, and gate engine | Synthetic framework complete | Protected evaluator tests; infra PR #12 |
| ES-010 | Build private read API and public Worker proxy | Disabled delivery complete | Python and Worker suites; infra PR #12; public PR #2 |
| ES-011 | Build and release the Observatory dashboard | Fixture UI complete | Desktop/mobile browser evidence; public PR #2 |
| ES-012 | Close Astro admin interface conformance | Implementing | Existing admin UI and browser tests |
| ES-013 | Replace broad credential and close workflow conformance | Implementing | API contract and failure suite |
| ES-014 | Replace Basic Auth, add external alerts, run recovery drills | Blocked externally | Access permission and alert destination |
| ES-015 | Build S1 aggregate contracts and scoring pipeline | Synthetic formula complete | 70-test observatory suite; infra PR #12 |
| ES-016 | Build S2 aggregate contracts and scoring pipeline | Synthetic formula complete | 70-test observatory suite; infra PR #12 |
| ES-017 | Build S4 aggregate contracts and scoring pipeline | Synthetic formula complete | 70-test observatory suite; infra PR #12 |
| ES-018 | Build S5 aggregate contracts and scoring pipeline | Synthetic formula complete | 70-test observatory suite; infra PR #12 |
| ES-019 | Build S6 aggregate contracts and scoring pipeline | Synthetic formula complete | 70-test observatory suite; infra PR #12 |
| ES-020 | Build S8 aggregate contracts and scoring pipeline | Synthetic formula complete | 70-test observatory suite; infra PR #12 |

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

## Post-MVP scorer checklists

### ES-015: External Exploration

- [x] Define S1 intent, semantics, exclusions, and source/privacy boundary.
- [x] Define aggregate observation, component, suppression, and release design.
- [x] Implement strict aggregate observation contracts.
- [x] Implement entropy, effective breadth, activity, depth, and panel controls.
- [x] Add synthetic invariants and suppressed ES-001 projection.
- [ ] Approve source families, rights, baseline, weights, and break policy.
- [ ] Run protected benchmark, negative controls, G4, and G5.

### ES-016: Source Concentration

- [x] Define S2 intent, entity levels, semantics, and exclusions.
- [x] Define reference distribution, mapping, formula, and release design.
- [x] Implement strict distribution and mapping contracts.
- [x] Implement HHI, top-k, entropy, effective count, and level components.
- [x] Add monopoly, equal-share, merge, duplicate, and suppression tests.
- [ ] Approve link sources, canonicalization, publisher/owner evidence, and baseline.
- [ ] Run extraction/mapping benchmarks, sensitivities, and G5.

### ES-017: Perspective Diversity

- [x] Define S4 intent, taxonomy boundary, semantics, and exclusions.
- [x] Define category aggregate, breadth, unknown, and release design.
- [x] Implement strict category-count contracts and diversity kernel.
- [x] Add balance, monopoly, unknown, and monotonic tests.
- [ ] Approve taxonomy, labels, capacities, and extraction candidate.
- [ ] Run protected benchmark, matched controls, G4, and G5.

### ES-018: Model-Language Diffusion

- [x] Define S5 intent and prohibit document-level authorship inference.
- [x] Define reference-corpus, pattern, aggregate, placebo, and release design.
- [x] Implement strict aggregate and pattern-statistic contracts.
- [x] Implement prevalence, cross-domain diffusion, lag, and suppression.
- [x] Add preexisting-pattern, leakage, placebo, and no-authorship tests.
- [ ] Approve provider/model/prompt rights and capture the controlled corpus.
- [ ] Freeze patterns, run protected/placebo validation, G4, and G5.

### ES-019: Human Knowledge Contribution

- [x] Define S6 intent, activity boundary, privacy, semantics, and exclusions.
- [x] Define platform aggregate, bot, baseline, panel, and release design.
- [x] Implement strict platform aggregate contracts and normalization.
- [x] Add duplicate, bot, import, break, panel, and monotonic tests.
- [ ] Approve platform sources, activity ontologies, bot and identity rules.
- [ ] Run platform benchmarks, backfill, external controls, G4, and G5.

### ES-020: Novel Information Density

- [x] Define S8 intent, novelty semantics, and truth/quality exclusions.
- [x] Define aggregate claim/cluster, denominator, density, and release design.
- [x] Implement strict aggregate hierarchy and density normalization.
- [x] Add repetition, distinctness, hierarchy, coverage, and stability tests.
- [ ] Approve claim ontology, extraction, clustering, denominator, and baseline.
- [ ] Run protected benchmark, matched sensitivities, G4, and G5.

## ES-009 checklist

- [x] Approve a synthetic-only benchmark framework boundary.
- [x] Implement strict benchmark-item, prediction, and candidate freeze
  contracts.
- [x] Implement deterministic transitive grouping, split assignment, and
  zero-overlap audit.
- [x] Implement append-only double annotation and adjudication transitions.
- [x] Enforce evaluator-only final-label reads with an access audit.
- [x] Implement classification, ordinal-error, confusion, and S3 pairwise
  metrics.
- [x] Implement immutable required gates with PASS, HOLD, and REJECT behavior.
- [x] Verify manifest, prediction, artifact, freeze, exact coverage, and
  candidate-lineage constraints before protected evaluation.
- [x] Implement aggregate-only public packets with restricted-field hygiene.
- [x] Prove reference acceptance, rejection, malformed-submission, overlap,
  role-isolation, and lineage-reuse behavior with synthetic tests.
- [ ] Approve source frame, annotator training, protected-store operator, split
  proportions, S3 task design, and immutable final thresholds.
- [ ] Build synthetic monotonicity, confounder, interval-coverage, and external
  negative-control fixture inventory.
- [ ] Complete human S7 double annotation and S3 ranking benchmark at the
  required sizes and agreement thresholds.
- [ ] Freeze non-overlapping final manifests and run one protected evaluation
  for each approved scorer lineage.
- [ ] Publish independently reviewed benchmark 1.0.0 evidence without
  restricted text or labels.

## ES-010 checklist

- [x] Approve a fixture-only, disabled-route delivery boundary.
- [x] Add a score-output table and security-barrier release-only view.
- [x] Remove direct release-manifest access from the API role.
- [x] Implement strict score, series, coverage, release, methodology, and
  health contracts.
- [x] Implement stable sorting and signed cursors bound to normalized queries.
- [x] Revalidate every stored result through the shared ES-001 contract.
- [x] Require explicit release approval in the in-memory fixture store.
- [x] Implement exact Worker path and query allowlists, upstream
  authentication, timeout, redirect, byte, schema, and error controls.
- [x] Implement bounded JSON and formula-safe CSV exports.
- [x] Preserve current Worker route regressions and pass Cloudflare dry-run.
- [ ] Approve public frames, entities, cache, stale, export, and rate policies.
- [ ] Deploy the private database view and authenticated API service.
- [ ] Run cache purge, stale serve, load, security, and rollback exercises.
- [ ] Enable one G5-approved score release and verify workers.dev plus the
  custom domain independently.

## ES-011 checklist

- [x] Approve a fixture-only dashboard implementation boundary.
- [x] Add a separate `/observatory/` Worker page and static client assets.
- [x] Keep S7 and S3 in separate segmented modes with score-specific frames.
- [x] Implement normalized public URL state and bounded same-origin queries.
- [x] Implement loading, not-released, unavailable, empty, ready, partial, and
  suppressed state logic.
- [x] Implement trend, uncertainty, table equivalent, selected components,
  coverage, warnings, versions, and evidence links.
- [x] Implement JSON and CSV view exports through ES-010.
- [x] Use the self-hosted ECharts asset and Toslop brand image.
- [x] Pass Node regressions and fixture-backed desktop/mobile browser checks
  with chart pixels, clean console, and no document overflow.
- [ ] Complete keyboard, screen-reader, 200% zoom, contrast, and reduced-motion
  accessibility audit.
- [ ] Add version-break and maximum-warning browser fixtures.
- [ ] Add production source freshness, Worker, API, and custom-domain canaries.
- [ ] Complete claims review and explicit G5 production cutover approval.


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

## ES-006 checklist

- [x] Define explicit structural block roles and authored-only extraction.
- [x] Implement contact minimization and quote, boilerplate, template,
  navigation, code, table, and unknown ratios.
- [x] Implement four allowlisted synthetic genres with unresolved state.
- [x] Implement versioned topic fixtures and deterministic event clustering.
- [x] Implement exact, near, syndication, revision, and logical identities.
- [x] Emit canonical snapshots and no-text matched-frame counts.
- [x] Test authored preservation, exclusion, deduplication, events, quality,
  tracking removal, and public hygiene.
- [ ] Approve four real genres, sources, taxonomy, thresholds, and ownership
  policy.
- [ ] Pass adjudicated extraction, classification, event, and dedup benchmarks.
- [ ] Complete historical and one-year shadow corpus releases.

## ES-007 checklist

- [x] Fit immutable baseline lexical vocabulary and frequency artifacts.
- [x] Implement lexical distributions and named diversity diagnostics.
- [x] Implement transparent synthetic surface-syntax fallback.
- [x] Implement fixed authored rhetorical registry and structural features.
- [x] Implement local deterministic hashed TF-IDF semantic fallback.
- [x] Enforce finite vectors, fixed dimensions, artifact checksums, and
  current-period isolation.
- [x] Emit no-text feature manifest.
- [x] Test golden determinism, perturbations, normalization, metadata
  invariance, and artifact immutability.
- [ ] Approve production tokenizer, parser, rhetorical registry, and semantic
  model with license, revision, checksums, and benchmarks.
- [ ] Build private typed feature objects, drift thresholds, and shadow
  release.

## ES-008 checklist

- [x] Implement base-2 Jensen-Shannon and cosine dispersion.
- [x] Implement robust center and MAD, IQR, and standard-deviation scale
  fallbacks.
- [x] Implement convergence z-scores, clipping, four component scores, and
  equal synthetic weights.
- [x] Implement deterministic logical deduplication and contribution caps.
- [x] Test exact numerical fixtures, convergence monotonicity, permutation,
  duplicate, conflict, cap, and suppression behavior.
- [x] Validate a shared score-contract projection with all values suppressed.
- [ ] Approve historical baseline cells, weights, caps, scales, effective
  sample, and sensitivity thresholds.
- [ ] Implement entity-cluster uncertainty and every required sensitivity.
- [ ] Complete baseline and shadow backfills, protected benchmark, monitoring,
  and release review.
