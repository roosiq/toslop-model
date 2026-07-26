# ES-013: GitHub Specification Workflow

| Field | Value |
| --- | --- |
| Status | Draft, retrospective conformance review required |
| Version | 0.1.2 |
| Created | 2026-07-26 |
| Execution owner | Data engineering lead |
| Approved intent reference | IS-008 v0.1.0, approval pending |
| Repositories | `roosiq/toslop`, `roosiq/toslop-model` |
| Gates | G0, G5 |
| Start prerequisites | ES-012 interface contract |
| Stage interfaces | GitHub API; observatory document templates |

## Implementation authorization

The current GitHub workflow is an as-built baseline. New repositories, roots,
file types, write operations, approval actions, or merge capabilities are
blocked until IS-008 v0.1.0 and this exact execution version are approved.

## Outcome

Provide bounded server-side discovery, reading, validation, optimistic
concurrency, branch creation, file update, and pull-request creation for
observatory Markdown and JSON files while preserving GitHub as the source of
truth and review boundary.

This execution spec satisfies IS-008 success measures 1-5, 7, 9, 10, and 12.

## Current state

`toslop/src/admin-worker.js` implements:

- repository configuration and path normalization;
- Git commit and tree traversal;
- allowlisted recursive file discovery;
- GitHub Contents API reads;
- Markdown-heading and JSON-syntax validation;
- stale-SHA checks;
- short-lived branch creation;
- Contents API update and pull-request creation;
- best-effort branch cleanup when pull-request creation fails;
- bounded GitHub response reads and a 15-second timeout;
- adversarial path, Unicode, control-character, and exact byte-boundary tests;
- mocked failure coverage for tree, payload, timeout, permission, branch,
  content, pull-request, and cleanup failures;
- stable JSON errors without token or upstream-body leakage.

The configured source is `roosiq/toslop-model`, reference `main`, root
`docs/observatory/`, extensions `.md` and `.json`, and maximum file size
250 KiB. The GitHub credential is server-side.

## Architecture and boundaries

```text
authenticated browser
        |
        | same-origin JSON
        v
toslop admin Worker
  | path and request validation
  | deterministic document validation
  | GitHub response bounds
  v
GitHub API
  | commit/tree/content reads
  | admin/* branch
  | one file commit
  v
pull request to main --> repository review and CI
```

The Worker may propose a repository change. It cannot approve, merge, force
push, modify branch protection, execute repository code, or treat a pull
request as an approved spec.

## Data contracts

All responses are JSON with `Cache-Control: no-store`.

### `GET /api/admin/session`

```json
{
  "ok": true,
  "session": {
    "email": "reviewer@example.com",
    "mode": "access",
    "repository": "roosiq/toslop-model",
    "reference": "main",
    "root": "docs/observatory/",
    "can_propose": true
  }
}
```

### `GET /api/admin/specs`

Returns `files[]` containing only allowed blobs with path, name, SHA, and size,
plus the base commit SHA and `truncated: false`. A truncated recursive tree is
an error, not a partial success.

### `GET /api/admin/spec?path=<encoded-path>`

```json
{
  "ok": true,
  "spec": {
    "path": "docs/observatory/intent-specs/IS-008-example.md",
    "sha": "40-character-git-sha",
    "size": 1234,
    "content": "# IS-008...",
    "html_url": "https://github.com/..."
  }
}
```

Content must be a UTF-8 file within the size and path boundary.

### `POST /api/admin/validate`

Input contains `path` and `content`. Output contains `valid`, kind, byte size,
and stable findings with `code`, `severity`, and `message`.
Blocking findings include invalid path, invalid JSON, empty content, and size
violations. Missing template sections are advisory.

### `POST /api/admin/proposals`

```json
{
  "path": "docs/observatory/intent-specs/IS-008-example.md",
  "content": "# IS-008...",
  "expected_sha": "40-character-git-sha",
  "title": "docs(observatory): refine IS-008",
  "summary": "Clarifies the administration acceptance criteria."
}
```

A success returns pull-request number, URL, branch, commit SHA, and validation
findings. `expected_sha` is mandatory for an existing file. A mismatch returns
`409 stale_spec` before a branch is created.

The machine-readable contract is
`docs/observatory/contracts/admin-api-v1.openapi.json`.

### Error contract

```json
{
  "ok": false,
  "error": {
    "code": "stable_machine_code",
    "message": "Bounded user-facing message",
    "details": {}
  }
}
```

No error includes credentials, stack traces, raw upstream bodies, or headers.

## Algorithm design

### Discovery

1. Resolve the configured base commit.
2. Traverse path segments from the root tree to `docs/observatory`.
3. Request one bounded recursive tree.
4. Reject a truncated tree.
5. Keep blobs only when extension, path, size, and root checks pass.
6. Sort by logical group and path.

### Validation

1. Normalize and constrain path.
2. Require a string body and compute UTF-8 byte length.
3. Enforce empty and size rules.
4. Parse JSON exactly for `.json`.
5. Parse Markdown headings deterministically for known intent and execution
   paths.
6. Emit stable findings without rewriting content.

### Proposal

1. Validate request shape, origin, path, content, title, and summary.
2. Fetch current base commit and selected file.
3. Compare current SHA with `expected_sha`.
4. Generate a bounded unique `admin/*` branch name.
5. Create the branch from the configured base.
6. Update exactly one allowed file through the Contents API.
7. Open one pull request against the configured reference.
8. If pull-request creation fails, delete the new branch best-effort and return
   a bounded error.

No retry is applied to a write because branch or commit creation may already
have succeeded. Recovery inspects GitHub state before repeating.

## Implementation tasks

1. Freeze the API contracts and stable error codes.
2. Keep repository, reference, root, extension, and size checks centralized.
3. Maintain bounded reads and GitHub request timeouts.
4. Maintain deterministic validation with no LLM dependency.
5. Add property tests for path normalization, Unicode, control characters,
   encoded traversal, and byte-size boundaries.
6. Add mocked integration cases for truncated trees, malformed GitHub payloads,
   timeout, rate limit, stale SHA, branch collision, content update failure,
   pull-request failure, and cleanup failure.
7. Add a repository-permission test proving the credential cannot administer
   the repository or merge.
8. Publish a versioned API schema or equivalent contract fixtures.

Tasks 1-6 and 8 have implementation evidence. Task 7 remains required before
G5 approval.

## Test and benchmark plan

- Unit tests for path, heading, JSON, size, and result-kind validation.
- Property tests over encoded and Unicode path inputs.
- Mocked GitHub reads and writes with exact request assertions.
- Verify Authorization never appears in returned or logged structures.
- Verify stale edits produce zero write calls.
- Verify one valid proposal creates branch, content commit, and pull request in
  order.
- Verify pull-request failure triggers best-effort branch deletion.
- Verify timeout and oversized upstream response fail closed.
- Verify public Worker cannot reach admin API routes.
- Live non-writing canary for session, list, read, and validate.
- Controlled pull-request canary in a disposable fixture file before G5.

## Operational design

GitHub reads are user-triggered and unscheduled. The Worker applies a 15-second
upstream timeout and bounded response body. It does not cache repository
content. GitHub rate-limit or outage produces an unavailable response.

Write recovery is manual and GitHub-first:

1. inspect whether the branch exists;
2. inspect whether the content commit exists;
3. inspect whether a pull request exists;
4. link or remove the orphan branch as repository policy permits;
5. never replay blindly.

Metrics must count read, validation, stale conflict, proposal success, bounded
failure class, and latency without recording document bodies or credentials.

## Security, privacy, rights, and compliance

- Use a repository-scoped GitHub App or fine-grained token with Contents and
  Pull requests permissions only.
- Keep the token in an encrypted Worker secret or mode-600 local secret file.
- Never send the token, private key, or upstream response headers to the client.
- Require authenticated identity and same-origin mutation requests.
- Restrict all paths before GitHub calls.
- Do not fetch submodules, symlinks, releases, Actions artifacts, or arbitrary
  URLs.
- Preserve GitHub commit author, branch, pull-request, review, and merge audit
  history.
- Specification text follows repository retention and rights policy.

## Release strategy

1. Run deterministic and mocked integration tests.
2. Dry-run the admin Worker bundle.
3. Start against the production repository in read-only mode.
4. Verify the full eligible file count and one known SHA.
5. Run non-writing validation.
6. Create a controlled proposal against a disposable fixture.
7. Verify `main` remains unchanged and the pull request has expected content.
8. Close the fixture pull request and remove its branch.
9. Record credential scope, Worker version, GitHub request evidence, and
   rollback.

Rollback removes proposal capability by withdrawing the GitHub credential while
retaining authenticated read/validation only if a read credential is approved.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| GitHub tree is truncated | `truncated=true` | Reject list as incomplete | Narrow root or use paginated traversal |
| Token missing or revoked | GitHub configuration or `401` | Proposal disabled or unavailable | Rotate scoped credential |
| Rate limit or outage | Bounded upstream error | No stale substitution | Wait or restore GitHub service |
| File changed during edit | SHA mismatch | `409`, zero writes | Reload and reconcile |
| Branch name collision | GitHub `422` | No content write | Generate new bounded name after inspection |
| Content write succeeds but PR fails | PR error after commit | Cleanup branch best-effort | Inspect and remove or open PR manually |
| Cleanup fails | GitHub delete error | Report bounded failure | Repository owner removes orphan branch |
| Malformed or oversized upstream body | Parser or size guard | Fail unavailable | Inspect GitHub/API compatibility |

## Definition of done

1. IS-008 and this exact version are approved.
2. API and error contracts are versioned and tested.
3. Root, extension, traversal, Unicode, control, size, and response bounds pass.
4. Stale-edit tests prove zero writes.
5. Proposal tests prove one-file, branch, commit, and PR behavior.
6. Credential scope is reviewed and rotation is documented.
7. Live read and controlled proposal canaries pass.
8. Metrics omit document content and secrets.
9. Rollback and orphan-branch recovery are tested.
10. Release and closure records link immutable evidence.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| GitHub App versus fine-grained token | Repository owner | G5 |
| Advisory versus blocking structural completeness | Program owner | IS-008 approval |
| New-file creation support | Program owner | Separate version approval |
| Audit metric retention period | Governance reviewer | G5 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending retrospective conformance review |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | 2026-07-26 adversarial path/size suite, complete mocked GitHub failure matrix, OpenAPI v1 contract, and live read/validation canary |

Material repository-workflow expansion is blocked until this table records
approval.
