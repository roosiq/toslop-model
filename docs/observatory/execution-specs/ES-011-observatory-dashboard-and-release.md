# ES-011: Observatory Dashboard and Release

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Product and UX lead |
| Approved intent reference | IS-007 v0.1.0, approval pending |
| Repositories | `toslop`, `toslop-model`, `slopslingers-infra` |
| Gates | G3, G5 |
| Start prerequisites | ES-010 fixture routes |
| Stage interfaces | Approved scorer, API, and dashboard release records |

## Implementation authorization

Implementation may begin after IS-007 approval and ES-010 fixture routes exist.
Production cutover requires an approved public score release, completed claims
review, accessibility and browser QA, operations evidence, and explicit program
owner approval.

## Outcome

Deliver an accessible, responsive research dashboard at `/observatory/` that
keeps S7 and S3 separate, shows components and evidence state with every trend,
supports bounded comparison and export, and degrades clearly during
suppression, staleness, version breaks, or API failure.

## Current state

- `toslop/src/index.js` is the public Worker entry and renders the existing
  report.
- Static assets live under `toslop/public/`.
- The current site uses a self-hosted vendored chart bundle and has extensive
  Node regression checks.
- No observatory page, navigation entry, client state, browser acceptance suite,
  or observatory release canary exists.

## Architecture and boundaries

```text
Worker route /observatory/
          |
          +--> semantic server-rendered shell and current status
          |
          +--> /public/observatory/dashboard.js
          |          |
          |          v
          |   same-origin ES-010 API
          |
          +--> self-hosted chart and style assets
```

Add a separate page module rather than enlarging the current report template:

- `toslop/src/observatory-page.js`
- `toslop/src/observatory-api.js`
- `toslop/public/observatory/dashboard.js`
- `toslop/public/observatory/dashboard.css`
- `toslop/public/observatory/methods/`
- `toslop/scripts/check-observatory-ui.mjs`
- `toslop/tests/browser/observatory.spec.mjs`

`src/index.js` owns routing and imports the page and API modules. Existing report
behavior remains unchanged.

## Data contracts

### URL state

Allowed query keys:

- `score=S7|S3`;
- `from=YYYY-MM`;
- `to=YYYY-MM`;
- `granularity=month|quarter`;
- `frame=<approved-slug>`;
- approved scorer-specific filters;
- `compare=<up-to-three-approved-series-ids>`.

Unknown, private, or oversized values are removed and never forwarded. The URL
contains no raw text, private entity ID, source-native ID, credential, or cursor.

### Client state

```json
{
  "status": "loading|ready|partial|suppressed|stale|unavailable",
  "score_id": "S7",
  "query": {},
  "series": [],
  "coverage": {},
  "release": {},
  "selection": {
    "period_id": null,
    "component_id": null
  },
  "error": null
}
```

State transitions are explicit. A failed comparison series may produce
`partial`; a failed primary series produces `unavailable`.

## Interface design

The page is a quiet research tool, not a product hero.

```text
+------------------------------------------------------------------+
| Toslop | Observatory | Methods | Data status                      |
+------------------------------------------------------------------+
| S7 Employer AI Compulsion | S3 Language Homogenization           |
+------------------------------------------------------------------+
| Period | Granularity | Frame | Score-specific filters | Export   |
+------------------------------------------------------------------+
| Construct, evidence class, release state, version, last updated  |
|                                                                  |
| Primary trend with interval and version-break markers            |
|                                                                  |
+--------------------------------------+---------------------------+
| Component table and selected trend   | Coverage and warnings     |
| raw | normalized | change | status   | sample | sources | gaps   |
+--------------------------------------+---------------------------+
| Methodology | Benchmark | Release | Downloaded-view provenance   |
+------------------------------------------------------------------+
```

Desktop uses the two-column analysis region shown above. Mobile stacks the trend,
components, and coverage in that order. Filters use native selects, segmented
controls, checkboxes, and compact icon buttons where appropriate. No cards are
nested and no decorative hero, gradient, or ornamental background is added.

### Required states

- loading skeleton that does not shift the layout;
- ready;
- partial comparison;
- suppressed with exact reason;
- stale with last successful calculation;
- version break;
- no matching data;
- API unavailable;
- unsupported filter combination;
- export preparing, complete, and failed.

### Chart rules

- S7 and S3 never share one y-axis or combined headline.
- Intervals are visible and keyboard-accessible through an accompanying table.
- Suppressed periods are gaps, not zeros or interpolated lines.
- Major-version boundaries break the line unless an approved bridge exists.
- Color does not encode good/bad; it distinguishes series and components.
- Every chart has a tabular equivalent and textual evidence-class label.
- Tooltips include period, score, interval, sample, warning count, and version.

## Algorithm design

### Loading

1. Render semantic heading, selected construct, status, and methods links on the
   server.
2. Parse and normalize URL state.
3. Fetch series, coverage, and release in parallel through same-origin routes.
4. Validate response versions and join only compatible series.
5. Derive display state without changing data values.
6. Render chart and synchronized table.
7. Announce state changes through a bounded live region.

### Comparisons

- Maximum three series.
- All series must have the same score ID, evidence class, granularity, ontology
  major version, scorer major version or approved bridge, and compatible frame.
- The UI refuses an invalid comparison and explains the mismatch.
- Components compare only when component IDs and definitions match.

### Wording

Display approved registry copy. Do not generate interpretations with an LLM.
Templates interpolate only allowlisted values. A descriptive increase says the
named construct increased in the observed frame; it does not say LLMs caused
the change.

### Exports

Export the exact normalized view query. Display row count, format, release,
schema, and methods link before download. The client does not rebuild CSV from
chart state; it calls ES-010.

## Implementation tasks

1. Approve information architecture, public labels, filter set, and visual
   design.
2. Add Worker page routing and server-rendered shell.
3. Add observatory navigation without replacing the existing report.
4. Implement URL parser and typed client state.
5. Implement API loader, cancellation, retry, stale, partial, and unavailable
   behavior.
6. Implement accessible filter bar and score tabs.
7. Implement trend chart, interval, version breaks, synchronized table, and
   tooltips using the existing self-hosted chart asset.
8. Implement component, coverage, warning, methodology, benchmark, release, and
   export views.
9. Implement mobile, keyboard, screen-reader, zoom, reduced-motion, and
   no-JavaScript states.
10. Add unit, regression, browser, visual, accessibility, and performance tests.
11. Add source freshness, API, Worker, and custom-domain canaries.
12. Run shadow, staged, public, and rollback release.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | URL normalization, state transitions, comparison compatibility, wording templates, export query |
| Worker regression | Existing routes and observatory shell/API routing |
| Browser functional | Filters, score tabs, period selection, comparison, suppression, version break, export |
| Accessibility | Keyboard order, labels, live regions, chart table, contrast, 200% zoom, reduced motion |
| Responsive | 360, 390, 768, 1280, and 1440 pixel viewports |
| Visual | No overlap, clipping, blank chart, unexpected shift, or nested-card layout |
| Security | Hostile labels and warning messages render as text; no HTML injection or secret exposure |
| Performance | Cached interactive target from IS-007; no layout shift from controls or loading |
| Production canary | workers.dev and `toslop.com` routes, API, assets, console, and current report |

Browser fixtures cover both scores, every required state, long labels, maximum
warnings, three comparisons, and empty components.

## Operational design

- Client errors report bounded error codes and public request IDs.
- Metrics: page load, API success, ready/partial/suppressed/stale/unavailable
  states, export, client error, and version mismatch.
- Alerts: observatory route failure, API unavailable over threshold, stale over
  24 hours, asset failure, JavaScript exception, or custom-domain mismatch.
- Methodology and release assets are versioned and cache-busted.
- A feature flag controls public route visibility without changing score data.
- The last approved release remains available during a new release upload.

## Security, privacy, rights, and compliance

- Render all data as text; do not use untrusted HTML.
- Apply the existing Worker security headers plus a restrictive content
  security policy.
- Use only same-origin scripts, styles, fonts, API, and exports.
- Do not add third-party analytics by default.
- Do not log public filter values that can identify a restricted entity.
- Entity filters are omitted unless publication policy enables them.
- Public methods and downloads carry license and limitation links.

## Release strategy

1. Local fixture UI with no private API.
2. Worker preview using synthetic ES-010 routes.
3. Internal shadow with one experimental score.
4. Accessibility, browser, visual, security, and performance acceptance.
5. Deploy hidden production route.
6. Verify workers.dev and `toslop.com` independently.
7. Enable navigation for the approved audience.
8. Monitor canaries through one full release window.
9. Public cutover after program-owner G5 approval.
10. Roll back by disabling navigation/flag, restoring prior Worker version, and
    retaining the previous API release.

Before deploy, run:

```bash
git status --short --branch
npm run ci
```

The deploy command remains `npm run deploy`. An upload success is not release
evidence until both workers.dev and the custom domain pass.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Chart library fails | Browser canary | Keep table and methods usable | Restore asset or prior Worker |
| Long label overlaps | Responsive visual test | Wrap or reduce local container typography | Fix CSS and add fixture |
| Version-incompatible comparison | Client compatibility check | Refuse comparison | Select compatible series |
| API stale or unavailable | Freshness and fetch state | Show stale/unavailable, not zero | Restore API or serve approved stale |
| Suppressed point connected by line | Browser fixture | Fail test | Render explicit gap |
| Domain route update fails | Separate custom-domain canary | Report failed release despite workers.dev success | Fix route permissions/config |

## Definition of done

1. The exact IS-007 version in `Approved intent reference`, this exact
   execution-spec version, design, labels, and public policies are approved.
2. S7 and S3 remain separate in every page, chart, export, and route.
3. All required states, components, coverage, warnings, evidence, and version
   information are present.
4. Functional, accessibility, responsive, visual, security, performance, and
   current-route regression tests pass.
5. No claims review finding remains.
6. Metrics, alerts, feature flag, stale behavior, and rollback are tested.
7. workers.dev and `toslop.com` both pass production canaries.
8. Release and closure evidence are linked from the dashboard.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Final information architecture and labels | Product and UX lead | G5 |
| Filter and comparison set | Research lead and product owner | G5 |
| Feature-flag mechanism | Operations owner | G5 |
| Browser test tooling and CI budget | Engineering lead | G5 |
| Public launch audience and date | Program owner | G5 |

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
