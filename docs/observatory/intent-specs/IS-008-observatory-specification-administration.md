# IS-008: Observatory Specification Administration

| Field | Value |
| --- | --- |
| Status | Proposed, as-built baseline exists |
| Version | 0.1.0 |
| Created | 2026-07-26 |
| Intent owner | Program owner |
| Decision owner | Program owner |
| Work packages | WP1.4, WP9.3, WP9.4 |
| Gates | G0, G5 |
| Approval prerequisites | None |

## Intent statement

Give specification owners and reviewers an authenticated workspace for reading,
validating, and proposing reviewable changes to observatory governance artifacts
without granting the browser direct write access to the default branch.

## Problem and evidence

The observatory already contains a project plan, seven intent specs, eleven
execution specs, shared contracts, and governance templates. Reviewing and
editing these files only through a local checkout makes discovery difficult and
creates inconsistent handoffs between research, product, and implementation
roles.

An as-built administration workspace is available at `admin.toslop.com`. It
lists the eligible GitHub files, renders Markdown, edits Markdown and JSON,
performs deterministic validation, and proposes changes through a short-lived
branch and pull request. Live verification on 2026-07-26 confirmed that all 32
eligible files were visible, unauthenticated requests failed, cross-origin
mutations failed, and desktop and mobile panes scrolled independently.

This intent formalizes that outcome retrospectively. Existing operation is not
evidence of G0 or G5 approval; expansion remains blocked until approval is
recorded.

## Primary users and decisions

| User | Decision supported |
| --- | --- |
| Intent-spec owner | Determine whether an intent is complete enough to request approval |
| Execution-spec owner | Refine implementation contracts and definition of done |
| Research lead | Review construct, evidence, benchmark, and interpretation boundaries |
| Product owner | Compare scope and sequencing across the program |
| Governance reviewer | Verify privacy, claims, licensing, and misuse controls |
| Implementation agent | Read the approved source of truth before executing work |

## Scope

- authenticated access at `admin.toslop.com`;
- recursive discovery of Markdown and JSON under
  `roosiq/toslop-model/docs/observatory/`;
- grouping, search, and filtering for intent specs, execution specs, contracts,
  decision records, release records, and closure records;
- sanitized Markdown preview and plain-text Markdown or JSON editing;
- deterministic path, size, JSON-syntax, and required-section validation;
- optimistic-concurrency checks using the current Git blob SHA;
- proposal creation through a new `admin/*` branch and GitHub pull request;
- visible repository, reference, file count, authentication mode, validation
  state, dirty state, and proposal result;
- keyboard-operable, responsive desktop and mobile layouts;
- independent scrolling for the file browser and selected document;
- no-store responses, security headers, lineage through GitHub, and operational
  health checks.

## Explicit exclusions

- direct commits, merges, approvals, or branch deletion from the browser;
- arbitrary repository, branch, path, file type, or binary editing;
- local-worktree reads or writes;
- execution of Markdown, embedded scripts, or repository code;
- score calculation, benchmark labeling, data annotation, or dashboard
  administration;
- treating validation findings as formal governance approval;
- public or unauthenticated access;
- individual cognitive diagnosis, AI-authorship classification, or score
  interpretation;
- replacing GitHub review, repository protections, CI, or named decision owners.

## Success measures

1. Every eligible `.md` and `.json` blob under the configured root appears with
   a stable path and current Git SHA; ineligible files never appear.
2. An authenticated user can search, filter, open, preview, edit, and validate a
   file without exposing a repository credential to the browser.
3. A valid proposal creates one short-lived branch and one pull request against
   the configured base reference without changing the base branch directly.
4. A stale expected SHA returns `409` before any branch or content write.
5. Invalid paths, traversal, control characters, empty content, invalid JSON,
   and content over 250 KiB fail closed.
6. Unauthenticated requests return `401` or the configured Access challenge;
   incomplete authentication configuration returns `503`.
7. Cross-origin mutation attempts return `403`; admin responses use
   `Cache-Control: no-store`, restrictive framing, content, and browser-policy
   headers.
8. At 1440x900 and 390x844, the document remains viewport-bounded, controls do
   not overlap, and file and document panes scroll independently.
9. GitHub outage, timeout, malformed response, truncated tree, stale edit, and
   pull-request failure produce bounded errors without leaking tokens, stack
   traces, or upstream response bodies.
10. Unit, mocked integration, dry-run Worker, and live browser checks are
    reproducible from documented commands.
11. Service restart and tunnel recovery procedures restore the application
    without changing repository state.
12. A governance review confirms that the workspace cannot approve its own
    specifications or bypass repository review.

## Interface semantics

`Read` displays the repository version of the selected file. `Edit` creates a
browser-local working copy. `Validate` reports deterministic structural
findings and does not approve the document. `Propose change` requests a GitHub
branch and pull request; it does not merge or authorize implementation.

`Valid` means no blocking editor rule failed. It does not mean scientifically
valid, approved, complete, licensed, secure, or ready for release. Advisory
findings identify missing expected sections but do not replace human review.

Missing, unavailable, unauthorized, stale, and conflicting states remain
visibly distinct. The interface must not silently substitute cached content or
present a failed proposal as saved.

## Data boundaries

The GitHub repository is the source of truth. The browser receives only
allowlisted file metadata, eligible file content, deterministic findings,
session metadata, and pull-request results. GitHub credentials, Access secrets,
tunnel credentials, local paths outside documented public metadata, and
upstream diagnostics remain server-side.

Files are limited to the configured root and extensions. Responses are not
cached. The administration layer creates no independent document-retention
system; branches, commits, pull requests, reviews, and deletion follow GitHub
repository policy.

## Constraints

- Retain the existing Astro static build and Cloudflare Worker boundaries.
- Prefer deterministic parsers and validation; no LLM call is required.
- Keep the public Worker unable to serve admin routes.
- Keep the admin origin loopback-bound when hosted on a workstation.
- Preserve pull-request review as the only write path.
- Use a repository-scoped GitHub App or fine-grained token when available.
- Cloudflare Access is the preferred edge identity boundary; Basic
  authentication is a documented temporary tunnel fallback.
- The application must remain usable at 200% zoom and supported mobile widths.

## Dependencies

### Approval prerequisites

None. This administration capability does not depend on approval of a scorer or
dashboard intent because it does not calculate or publish observatory results.

### Coordination interfaces

- ES-012 defines Astro and user-interface boundaries.
- ES-013 defines repository reads, validation, concurrency, and proposals.
- ES-014 defines authentication, tunnel, deployment, and recovery.
- GitHub branch protection and CI remain external enforcement boundaries.
- Observatory templates define expected document sections.

## Risks and unresolved decisions

| Decision or risk | Owner | Resolution required by |
| --- | --- | --- |
| Replace temporary Basic authentication with Cloudflare Access | Security and operations owner | G5 |
| Replace broad classic GitHub credential with a repository-scoped GitHub App or fine-grained token | Repository owner | G5 |
| Define admin access-review and credential-rotation cadence | Governance reviewer | G5 |
| Decide whether pull-request creation requires blocking structural completeness | Program owner | IS-008 approval |
| Decide whether approved specs become read-only in the editor | Program owner | Before approval workflow implementation |
| Add durable audit metrics without retaining document bodies | Security and operations owner | G5 |

## Acceptance scenarios

1. **Given** an authenticated owner opens the workspace, **when** GitHub returns
   the complete observatory tree, **then** every eligible file appears with its
   repository path and no ineligible file is exposed.
2. **Given** a user edits an intent spec, **when** required sections are absent,
   **then** validation identifies each missing section without claiming that the
   document is approved.
3. **Given** another commit changes the selected file, **when** the user
   proposes an edit with the old SHA, **then** the request returns `409` and
   creates no branch.
4. **Given** a valid current edit, **when** the user proposes it, **then** one
   pull request is created and `main` remains unchanged.
5. **Given** a forged cross-origin request with valid Basic credentials,
   **when** it posts a mutation, **then** the request is rejected.
6. **Given** a 1440x900 viewport with all current files, **when** the user
   scrolls the file list and then the selected document, **then** each pane
   scrolls independently and the page itself remains viewport-bounded.
7. **Given** GitHub or the tunnel is unavailable, **when** the workspace loads,
   **then** it shows a bounded unavailable state and does not display stale
   content as current.

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved version | None |
| Approver | None |
| Decision date | None |
| Evidence | Existing as-built implementation and 2026-07-26 verification |

The existing implementation may remain available for retrospective review.
Material expansion is blocked until this table records approval.
