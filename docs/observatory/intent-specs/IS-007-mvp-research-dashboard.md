# IS-007: MVP Research Dashboard

| Field | Value |
| --- | --- |
| Status | Proposed |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Intent owner | Product and UX lead |
| Decision owner | Program owner |
| Work packages | WP4.3, WP9.1, WP9.2, WP9.3, WP9.4 |
| Gates | G0, G3, G5 |
| Approval prerequisites | IS-001, IS-003, IS-005, IS-006 |

## Intent statement

Give research leads and public readers an auditable dashboard for comparing S7
and S3 trends, components, coverage, uncertainty, and warnings without hiding
evidence limits, mixing constructs, or overstating causation.

## Problem and evidence

A top-line chart alone would hide the exact conditions that determine whether a
trend is interpretable: component disagreement, source composition, baseline
coverage, sample size, confidence, suppression, benchmark status, and scorer
version. A public interface also creates pressure to simplify distinct
constructs into one dramatic number.

The existing `toslop` Worker serves a public report, `/summary.json`, a scoring
methods page, and bounded score proxies. It is the correct public boundary, but
the current report is an AI-likeness product and does not provide the
observatory's evidence classes, score portfolio, filters, lineage, or
methodology views. The private gateway must remain behind a Worker proxy.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Research lead | Inspect whether a movement is supported and which components or coverage changes explain it |
| Product owner | Decide whether an experimental score is ready for wider release |
| Data and applied-science leads | Diagnose source outages, drift, benchmark regressions, and version changes |
| Public researcher | Compare approved periods and strata, download public-safe data, and understand limitations |
| Governance reviewer | Verify claims, suppression, privacy, and entity-publication behavior |

## Scope

The MVP dashboard is a real research interface at `/observatory/`, not a
marketing landing page. It includes:

- separate S7 and S3 views with no default composite;
- overview trends with period, baseline, evidence class, and scorer version;
- component trends and contribution breakdown;
- filters for approved period, genre, occupation, industry, jurisdiction,
  source family, and topic where public policy permits;
- comparison of up to three approved series;
- sample, effective-sample, coverage, source-mix, and warning panels;
- uncertainty intervals and suppression states;
- methodology, construct definition, benchmark, release, and known-limit links;
- source-coverage and data-freshness status;
- version-change markers and comparability notices;
- public-safe CSV and JSON export of the current view;
- stable URLs that encode only public-safe filter state;
- accessible desktop and mobile layouts.

The supporting public API provides read-only score series, score detail,
coverage, methodology, benchmark metadata, and release metadata. Private
record-level drill-down remains outside the public Worker and requires a
separate internal-product intent.

## Explicit exclusions

The MVP does not include:

- one cross-construct cognitive-impact, brainwashing, or overall score;
- individual document, worker, author, applicant, or employee views;
- public record-level source text or evidence spans;
- public employer ranking by default;
- causal language for descriptive or exposure-association series;
- model-generated narrative summaries presented as research findings;
- user accounts, alert subscriptions, annotation tools, or private admin
  controls;
- direct browser calls to `model-api.slopslingers.com`;
- replacement of the existing Toslop AI-likeness report.

## Success measures

1. A user can open S7 or S3, select an approved frame, and see score, baseline,
   change, all components, interval, confidence, sample, effective sample,
   coverage, warnings, evidence class, and versions in one workflow.
2. No route, heading, chart, metadata tag, or export presents a cross-construct
   composite.
3. Descriptive, exposure-association, and causal-estimate fixtures render
   visibly different evidence labels and methodology text.
4. Suppressed fixtures show the suppression reason and never render a zero,
   interpolated point, ordinary trend line, or rank.
5. Component disagreement remains visible; the top-level score cannot be
   displayed without its component-access control and warning state.
6. Every chart point links to its public-safe score detail, methodology,
   benchmark version, source-coverage summary, and scorer release.
7. Public exports validate against the shared score schema and contain the same
   values, filters, warnings, and versions as the rendered view.
8. Cached public GET requests meet p95 server response under 500 ms and the
   primary dashboard becomes interactive within 2.5 seconds on the approved
   desktop and mobile test profiles.
9. Keyboard-only, screen-reader, contrast, zoom, focus, and reduced-motion tests
   meet WCAG 2.2 AA for the scoped routes.
10. Desktop widths of 1280 and 1440 pixels and mobile widths of 360 and 390
    pixels have no overlapping, clipped, or horizontally scrolling core
    controls or data labels.
11. API, source, benchmark, or release outages render a stale or unavailable
    state while preserving the last successful calculation timestamp.
12. Security tests prove that the browser receives no private API key, private
    gateway URL detail beyond the public proxy contract, raw text, internal
    path, stack trace, or upstream diagnostic.
13. A claims review finds zero individual diagnosis, document authorship proof,
    unsupported causal wording, or implication that all high scores are bad.
14. Existing `/`, `/model/`, `/summary.json`, `/health`, and scoring routes pass
    their regression suite unchanged.

## Interface semantics

The first question the interface answers is "what was measured in this frame?"
The second is "how much and in which components did it change?" The third is
"is the evidence sufficient and comparable?"

Visual emphasis follows this order:

1. construct name and evidence class;
2. period, frame, and score movement;
3. components and interval;
4. coverage, sample, warnings, and version;
5. methodology and benchmark evidence.

An unavailable or suppressed result is a first-class state, not an error to
hide. The dashboard does not assign good/bad color semantics to the score
direction.

## Data boundaries

The public Worker receives only public-safe aggregate contracts from an
authenticated private upstream or a published static artifact. It validates,
minimizes, caches, and returns an allowlisted response. Raw text, record-level
features, protected benchmark labels, credentials, private source paths, and
internal diagnostics never cross the public boundary.

Entity-level filters and exports are disabled unless an approved publication
policy explicitly permits them and the score meets entity-specific suppression
rules.

## Constraints

- The implementation follows the current `toslop` Worker and static-asset
  patterns unless an approved execution spec changes them.
- Existing vendored chart code remains self-hosted; no third-party browser
  analytics or chart CDN is introduced by default.
- All public requests are same-origin through the Worker.
- API contracts are versioned and backward compatible within a major version.
- The dashboard works without JavaScript for core methodology and current
  status, while interactive filtering may require JavaScript.
- No live LLM call is required to render or explain a score.

## Dependencies

### Approval prerequisites

- [IS-001](IS-001-score-ontology-and-reporting-semantics.md)
- [IS-003](IS-003-employer-ai-compulsion-scorer.md)
- [IS-005](IS-005-language-homogenization-scorer.md)
- [IS-006](IS-006-mvp-validation-benchmark.md)

### Coordination interfaces

- Approved public API, caching, entity-publication, accessibility, and release
  decisions

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Public route and navigation placement | Product and UX lead | Execution approval |
| Whether public data comes from private API, static release artifact, or both | Data lead and product owner | Execution approval |
| Public entity-level filters | Governance reviewer and program owner | G5 |
| Cache TTL and stale-data policy | Operations owner | G5 |
| Visualization library reuse versus replacement | Product and UX lead | Execution approval |
| Public export row limits and licensing notices | Governance reviewer | G5 |
| Internal record-level research console | Program owner | Separate intent |

## Acceptance scenarios

1. **Given** S7 is available and S3 is suppressed, **when** the overview opens,
   **then** S7 renders normally while S3 displays its suppression reason rather
   than a zero.
2. **Given** a scorer major version changes, **when** a user views a series
   across the boundary, **then** the chart shows a break and comparability
   notice unless a reviewed bridge exists.
3. **Given** a descriptive trend rises, **when** a user opens its detail,
   **then** the evidence label and copy describe observed movement without
   causal wording.
4. **Given** the private API returns a stack trace or unknown field, **when** the
   Worker validates the response, **then** the public response contains a
   bounded unavailable state and no private diagnostic.
5. **Given** a mobile user selects filters and opens methodology, **when** the
   viewport is 360 pixels wide, **then** controls, chart labels, warnings, and
   links remain readable and non-overlapping.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

Implementation is blocked until this table records approval and S7/S3 reach the
required release state.
