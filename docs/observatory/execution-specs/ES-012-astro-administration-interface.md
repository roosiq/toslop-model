# ES-012: Astro Administration Interface

| Field | Value |
| --- | --- |
| Status | Draft, retrospective conformance review required |
| Version | 0.1.0 |
| Created | 2026-07-26 |
| Execution owner | Product and UX lead |
| Approved intent reference | IS-008 v0.1.0, approval pending |
| Repositories | `roosiq/toslop` |
| Gates | G0, G5 |
| Start prerequisites | None |
| Stage interfaces | ES-013 admin API; ES-014 authenticated runtime |

## Implementation authorization

The current interface predates IS-008 and is recorded as an as-built baseline.
No material feature expansion is authorized until IS-008 v0.1.0 and this exact
execution version are approved. Corrective security, availability, and
accessibility work may proceed when it preserves the documented boundary.

## Outcome

Provide a static Astro administration interface that exposes repository-backed
specification discovery, reading, editing, validation, and proposal controls
without mixing admin routes into the public Toslop surface.

This execution spec satisfies IS-008 success measures 1, 2, 7, 8, 9, 10, and
12 at the interface boundary.

## Current state

Verified as-built files in `toslop`:

- `src/pages/admin/index.astro`: complete responsive administration interface;
- `src/pages/index.astro`, `src/pages/model/index.astro`, and
  `src/pages/score/index.astro`: public Astro pages;
- `astro.config.mjs`: static output configuration;
- `src/admin-worker.js`: authenticated assets and API boundary;
- `src/index.js`: public Worker that does not expose admin routes;
- `scripts/check-admin.mjs`: deterministic admin Worker tests;
- `scripts/check-browser.mjs`: local desktop and mobile browser workflow;
- `wrangler.admin.jsonc`: separate admin Worker assets and routes.

Astro emits `dist/admin/index.html` and shared hashed assets. The admin Worker
serves only the admin shell and required generated assets. The public Worker
returns `404` for admin paths.

On 2026-07-26 the desktop grid-row bug was corrected by bounding `.workspace`
to one `minmax(0, 1fr)` row and clipping the sidebar shell. Browser measurement
confirmed a 900px document, 846px workspace, 659px file viewport over 1622px of
content, and independent wheel movement in file and document panes. Mobile
390x844 remained viewport-bounded.

## Architecture and boundaries

```text
Astro source
    |
    v
static dist/ -------------------------+
    |                                 |
    v                                 v
public Worker                    admin Worker
toslop.com                       authenticated only
no /admin                        / + /admin/ + /_astro/*
                                      |
                                      v
                               same-origin admin API
```

The browser owns presentation state only: selected path, search, filter, mode,
working content, expected SHA, validation findings, dirty state, and proposal
dialog state. It owns no repository credential and performs no direct GitHub
request.

The interface is a dense operational workspace. It uses one file sidebar, one
document surface, compact command controls, and modals only for proposal
confirmation. It has no marketing hero, decorative dashboard cards, or
cross-construct score presentation.

## Data contracts

### Client state

```json
{
  "session": null,
  "files": [],
  "selected_path": null,
  "selected_sha": null,
  "repository_content": "",
  "working_content": "",
  "mode": "read",
  "filter": "all",
  "query": "",
  "validation": null,
  "request_state": "idle",
  "error": null
}
```

`request_state` is one of `idle`, `loading`, `validating`, or `proposing`.
Dirty state is derived from exact content inequality. Proposal controls remain
disabled without a selected file, a writable session, or current content.

### Rendering

- Markdown preview is sanitized before insertion.
- JSON is edited as plain text and validated server-side.
- File paths and repository metadata are rendered as text, never HTML.
- Unknown errors use bounded public copy.
- The client does not persist document bodies to local storage.

## Algorithm design

1. Load the authenticated session.
2. Load and group the eligible file list.
3. Apply local search and type filters without changing server data.
4. Fetch one selected file and retain its SHA.
5. Render sanitized Markdown or plain editor content.
6. Derive dirty and command-disabled states.
7. Send validation and proposal requests only to same-origin API routes.
8. On successful proposal, present the pull-request URL and retain the
   repository version until an explicit refresh.

The layout uses viewport-bounded shell dimensions. Desktop uses a two-column
grid with `minmax(0, 1fr)` tracks. Mobile turns the sidebar into a fixed drawer.
The file browser and preview/editor are the scroll owners; `html`, `body`, the
workspace, and pane shells do not expand with document content.

## Implementation tasks

1. Keep Astro configured for deterministic static output.
2. Keep public and admin page sources and Worker entry points separate.
3. Preserve the route allowlist for admin assets.
4. Maintain sanitized preview and text-only metadata rendering.
5. Maintain search, grouped file navigation, read/edit modes, validation,
   proposal dialog, loading, empty, dirty, conflict, and error states.
6. Add a regression assertion for document, workspace, sidebar, file-list, and
   preview scroll dimensions at desktop and mobile sizes.
7. Add keyboard traversal, focus restoration, zoom, and screen-reader checks.
8. Record screenshots and measured scroll results in release evidence.

Tasks 1-5 exist. Tasks 6-8 require closure evidence before conformance approval.

## Test and benchmark plan

- Astro build and type diagnostics.
- Static JavaScript syntax checks.
- Public-route regression proving `/admin/` is unavailable.
- Admin asset allowlist and security-header tests.
- Mocked API integration for loading, selection, validation, stale edit, and
  proposal states.
- Playwright at 1440x900, 1280x800, 390x844, and 360x800.
- Assert document `scrollHeight` equals viewport height.
- Assert file-list `scrollHeight > clientHeight` and wheel input changes only
  its `scrollTop`.
- Assert long preview `scrollHeight > clientHeight` and wheel input changes
  only its `scrollTop`.
- Keyboard-only, 200% zoom, reduced-motion, contrast, and focus-visible checks.
- CSP test proving no remote script, style, font, or frame dependency.

## Operational design

Astro assets are rebuilt before Worker validation or deployment. A long-running
local Wrangler process must restart after Astro atomically replaces `dist/`;
hot reload alone may retain a stale asset manifest. Health checks request the
authenticated root and one generated asset.

The admin shell and API responses use `no-store`. No background schedule,
queue, or retry runs in the browser. Users explicitly refresh repository state.

Rollback restores the previous `toslop` source revision, rebuilds `dist/`,
restarts the local admin service when tunnel-hosted, and verifies public and
admin routes separately.

## Security, privacy, rights, and compliance

- Sanitize Markdown with an allowlisted library.
- Serve a restrictive CSP, frame denial, no-sniff, no-referrer, no-index, and
  permissions policy.
- Never interpolate file content into executable script or style contexts.
- Keep repository credentials out of Astro output and browser state.
- Do not add browser analytics or third-party assets by default.
- Do not expose public Worker admin routes as a fallback.
- Avoid local persistence of unpublished specification content.

## Release strategy

1. Build and test against mocked GitHub data.
2. Start public and admin Workers on separate loopback ports.
3. Run desktop and mobile browser workflows.
4. Verify public `/admin/` remains `404`.
5. Verify unauthenticated admin access fails.
6. Deploy or restart only the admin path.
7. Run live shell, asset, file-list, preview, edit, and validation canaries.
8. Compare document and pane scroll dimensions with the approved baseline.
9. Record Worker version, source revision, screenshot, and rollback command.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Implicit desktop grid row expands with file content | Document scroll height exceeds viewport | Page appears clipped or cannot scroll correctly | Restore bounded grid row and pane overflow rules |
| Wrangler retains stale Astro asset manifest | Admin root or hashed asset returns `500`/`404` after build | Fail unavailable | Restart admin Wrangler service |
| Generated asset hash mismatch | Browser console or asset canary fails | Shell may be incomplete | Rebuild once, restart, verify manifest |
| Markdown sanitizer regression | Security test or DOM fixture fails | Block release | Restore sanitizer/version and CSP |
| Mobile drawer traps or loses focus | Keyboard browser test | Block release | Restore focus and drawer state handling |
| API fails after shell loads | Bounded error state | Editing disabled | Restore API or runtime; refresh explicitly |

## Definition of done

1. IS-008 and this execution version are approved.
2. Current routes, assets, and component ownership match this document.
3. Public admin-route rejection passes.
4. Desktop and mobile dimensions and independent scrolling pass.
5. Keyboard, zoom, focus, sanitizer, and CSP checks pass.
6. All request and failure states are visibly distinct.
7. Build, test, deployment, restart, and rollback commands are documented.
8. Live evidence and a closure record link the tested source and Worker version.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Whether to extract the large admin page into smaller Astro components | Product and UX lead | Next material interface change |
| Whether validation findings should have direct source links | Intent-spec owner | IS-008 approval |
| Supported browser matrix beyond current Chromium automation | Product and UX lead | G5 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending retrospective conformance review |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | 2026-07-26 CI and desktop/mobile live scroll verification |

Material interface expansion is blocked until this table records approval.
