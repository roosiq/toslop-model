# ES-014: Admin Access, Tunnel, and Operations

| Field | Value |
| --- | --- |
| Status | Draft, retrospective conformance review required |
| Version | 0.1.0 |
| Created | 2026-07-26 |
| Execution owner | Security and operations owner |
| Approved intent reference | IS-008 v0.1.0, approval pending |
| Repositories | `roosiq/toslop`; workstation systemd and Cloudflare configuration |
| Gates | G0, G5 |
| Start prerequisites | ES-012 interface; ES-013 API |
| Stage interfaces | Cloudflare custom domain, Worker, Tunnel, systemd, GitHub |

## Implementation authorization

The current tunnel path is an as-built temporary deployment. It may receive
corrective security and reliability fixes, but new identities, hostnames,
origins, repositories, or administrative actions are blocked until IS-008
v0.1.0 and this exact execution version are approved.

Cloudflare Access remains the target production identity boundary. HTTP Basic
authentication is a temporary fallback, not the approved terminal state.

## Outcome

Serve `admin.toslop.com` through an authenticated, no-store Cloudflare path to a
loopback-bound local admin Worker, with durable services, bounded trust
transitions, credential handling, health checks, recovery, and rollback.

This execution spec satisfies IS-008 success measures 6-12 at the runtime and
operations boundary.

## Current state

Verified on 2026-07-26:

- `toslop-admin-tunnel-edge` owns the `admin.toslop.com` custom domain;
- `src/admin-tunnel-proxy.js` forwards to
  `toslop-admin-origin.ryancook.name` and rewrites only a matching same-origin
  mutation Origin to the tunnel origin;
- Cloudflare named tunnel `matrix-ryancook-name` routes the origin hostname to
  `http://127.0.0.1:8789`;
- `toslop-admin.service` runs `npm run dev:admin` as a user service;
- `cloudflared-matrix.service` runs the named tunnel as a user service;
- local secrets are mode `600` in ignored `.dev.vars.local`;
- `ops/systemd/toslop-admin.service` versions the live unit with no-new-
  privileges, private temporary and device namespaces, kernel and control-group
  protection, namespace and address-family restrictions, and mode-077
  process-created files;
- `scripts/check-admin-tunnel.mjs` verifies the constant origin, exact
  same-origin rewrite, foreign-origin preservation, redirect rewrite, body and
  authentication forwarding, and no-store response;
- `scripts/check-admin-live.mjs` verifies loopback or public authentication,
  session, file list, known read, deterministic validation, and cross-origin
  rejection without writing;
- `scripts/wait-admin-ready.mjs` prevents the app unit from reaching ready
  state before the loopback authentication challenge responds;
- `toslop-admin-health.timer` runs the complete public-path canary every five
  minutes and records a failed unit and bounded journal evidence on failure;
- unauthenticated live requests return `401`;
- authenticated session, 32-file list, known file read, and validation return
  successfully;
- forged cross-origin validation returns `403`;
- both user services are enabled and active.

The available Cloudflare API token lacked Zero Trust Access permissions.
Wrangler OAuth could deploy the custom-domain proxy but did not resolve Access
policy creation. The current fallback therefore uses Basic authentication.

## Architecture and boundaries

```text
browser
  | TLS + Basic challenge today
  v
Cloudflare custom domain
toslop-admin-tunnel-edge Worker
  | no-store pass-through
  | exact same-origin Origin rewrite only
  v
toslop-admin-origin.ryancook.name
  |
  v
named Cloudflare Tunnel
  |
  v
127.0.0.1:8789
local Wrangler admin Worker
  | authenticate again in application code
  | same-origin mutation checks
  v
GitHub API
```

The edge proxy is not an authorization boundary. The local admin Worker must
authenticate every request. The local origin remains loopback-bound and is
never exposed through a LAN listener.

Cloudflare Access mode verifies `Cf-Access-Jwt-Assertion` signature, issuer,
expiry, and application audience against the team JWKS, requires an email
claim, and may apply email or domain allowlists. Missing configuration fails
closed.

Tunnel fallback mode requires both `ADMIN_BASIC_AUTH_USERNAME` and
`ADMIN_BASIC_AUTH_PASSWORD`. If either is configured, authentication runs
before the localhost development bypass.

## Data contracts

### Runtime configuration

| Variable | Required in Access mode | Required in tunnel fallback | Purpose |
| --- | --- | --- | --- |
| `ADMIN_HOST` | Yes | Configured default | Expected production hostname |
| `ADMIN_ACCESS_TEAM_DOMAIN` | Yes | No | Access issuer and JWKS host |
| `ADMIN_ACCESS_AUD` | Yes | No | Access application audience |
| `ADMIN_ALLOWED_EMAILS` | Optional | No | Worker-side identity allowlist |
| `ADMIN_ALLOWED_DOMAINS` | Optional | No | Worker-side domain allowlist |
| `ADMIN_BASIC_AUTH_USERNAME` | No | Yes | Temporary tunnel identity |
| `ADMIN_BASIC_AUTH_PASSWORD` | No | Yes | Temporary tunnel secret |
| `TOSLOP_MODEL_GITHUB_TOKEN` | For proposals | For proposals | Server-side repository credential |

Incomplete Basic or Access configuration returns `503`. Missing credentials
return `401` with the applicable challenge. Invalid authenticated identity
returns `403`.

### Edge forwarding

- Preserve method, path, query, body, Authorization, and safe request headers.
- Resolve only to the constant tunnel origin.
- Do not follow redirects automatically.
- Rewrite `Location` from the tunnel origin back to the public origin.
- Rewrite `Origin` only when it exactly equals the incoming public origin.
- Preserve foreign Origin values so the local Worker rejects them.
- Force `Cache-Control: no-store` on responses.

## Algorithm design

### Authentication precedence

1. If either Basic variable exists, require complete valid Basic credentials.
2. Otherwise allow local bypass only when explicitly enabled and URL hostname
   is loopback.
3. Otherwise require exact configured production host.
4. Require complete Access issuer and audience.
5. Verify Access JWT and optional identity allowlists.

Basic username and password comparisons use SHA-256 digest comparison to avoid
obvious variable-time string equality. TLS is mandatory outside loopback.

### Health evaluation

1. Confirm both systemd user services are active.
2. Confirm loopback root returns `401` without credentials.
3. Confirm tunnel origin returns `401` without credentials.
4. Confirm public hostname returns `401` without credentials.
5. Confirm authenticated session, file list, known file read, and non-writing
   validation.
6. Confirm forged cross-origin mutation returns `403`.
7. Confirm expected security and no-store headers.
8. Confirm live browser renders and scrolls at desktop and mobile sizes.

## Implementation tasks

1. Preserve loopback binding and durable user services.
2. Preserve fail-closed application authentication behind the tunnel.
3. Add a systemd dependency and readiness policy so the tunnel may run while
   the app restarts without restart loops.
4. Add explicit service hardening appropriate for Node/Wrangler and
   cloudflared.
5. Add automated health checks and bounded alerts for app, origin, custom
   domain, authentication, GitHub read, and cross-origin rejection.
6. Obtain Zero Trust permissions and create a Cloudflare Access self-hosted
   application for `admin.toslop.com`.
7. Restrict the Access policy to approved identities and capture the audience.
8. Configure Access JWT secrets, test dual enforcement, then remove Basic
   credentials.
9. Replace the current GitHub classic credential with a repository-scoped
   credential and document rotation.
10. Record recovery and rollback drills.

Tasks 1-4 exist. The scheduled health-check portion of task 5 exists; external
alert delivery does not. Tasks 6-10 remain required before G5 approval.

## Test and benchmark plan

- Unit tests for Basic completeness, challenge, invalid and valid credentials.
- Unit tests for Access missing config, missing assertion, invalid assertion,
  issuer, audience, expiry, email, and allowlist behavior.
- Proxy tests for exact Origin and Location rewriting and foreign Origin
  preservation.
- Verify the edge Worker cannot select an arbitrary origin.
- Verify loopback is the only listening address.
- Verify secret files are ignored and mode `600`.
- Verify unauthenticated app, origin, and custom-domain responses.
- Verify authenticated read and non-writing validation.
- Verify cross-origin mutation rejection through the full proxy/tunnel path.
- Restart app and tunnel independently while running canaries.
- Stop the app and verify bounded Cloudflare failure; restart and recover.
- Desktop and mobile live browser smoke tests with no console errors.

## Operational design

The user services start with the user default target and restart on failure.
The app builds Astro before starting Wrangler. Because Astro replaces `dist/`,
the service must restart after a production asset rebuild to refresh Wrangler's
asset manifest.

Health checks run from three perspectives: loopback, tunnel origin, and public
custom domain. They distinguish DNS, edge Worker, tunnel connector, local app,
authentication, GitHub, and client-render failures.

Credential rotation:

1. create a new scoped credential;
2. update the protected secret source;
3. restart only the app service;
4. run authenticated read and controlled proposal tests;
5. revoke the old credential;
6. record timestamp, owner, scope, and evidence without secret material.

No automated retry sends proposal writes. Tunnel and app process restarts are
safe because repository writes remain request-driven.

## Security, privacy, rights, and compliance

- Prefer Cloudflare Access with named identity and periodic access review.
- Treat Basic authentication as temporary and rotate after any suspected
  exposure.
- Never place credentials in repository files, service unit command lines,
  logs, screenshots, or browser storage.
- Keep secret files mode `600` and ignored by Git.
- Keep the origin loopback-bound.
- Keep the edge origin constant and force no-store.
- Verify Access JWT in the application even when Access protects the edge.
- Restrict GitHub credential scope and rotate it independently.
- Log bounded event metadata, not Authorization, cookies, JWTs, passwords,
  document bodies, or upstream error bodies.
- Revoke access and credentials immediately during an incident; preserving
  read availability is secondary to preventing unauthorized proposals.

## Release strategy

1. Validate source and Worker bundles.
2. Verify dirty-worktree scope before deployment.
3. Start or restart the local app and confirm loopback.
4. validate tunnel ingress before restarting cloudflared;
5. verify origin hostname independently;
6. deploy the custom-domain edge Worker;
7. verify DNS and Worker version;
8. run unauthenticated, authenticated, cross-origin, API, and browser checks;
9. capture service status, tunnel connector, source revision, Worker version,
   and rollback evidence.

Rollback order:

1. withdraw the public custom-domain trigger or restore the previous edge
   Worker version;
2. restore the previous tunnel ingress and restart cloudflared;
3. restore the previous local source and `dist/`;
4. restart the local app;
5. verify unrelated tunnel hostnames separately.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Public DNS absent or stale | Authoritative and recursive DNS probes | Host unavailable | Restore custom domain and flush only local stale cache |
| Edge proxy deployment succeeds but origin fails | Origin and public probes disagree | Bounded Cloudflare failure | Restore tunnel/app before public cutover |
| Tunnel connector stops | Tunnel info and service status | Host unavailable | Restart connector and inspect ingress |
| Local app stops | Loopback probe and systemd | Tunnel returns origin error | Restart app and inspect build/assets |
| Wrangler asset manifest is stale | Root or hashed assets return `500`/`404` after build | Admin unavailable | Restart app service |
| Basic credential exposed | Incident report or anomalous access | Revoke immediately | Rotate credentials; review GitHub activity |
| Access variables incomplete | `503 access_not_configured` | Fail closed | Restore issuer and audience |
| Origin rewrite accepts foreign Origin | Security regression test | Potential CSRF | Block deployment; restore exact comparison |
| GitHub credential fails | Session cannot propose or API error | Reads/validation may remain; writes fail | Rotate scoped credential |
| Shared tunnel edit breaks another hostname | Canary failure on existing ingress | Unrelated service degraded | Restore previous validated config |

## Definition of done

1. IS-008 and this exact execution version are approved.
2. Cloudflare Access protects the custom domain and is verified again in the
   local Worker.
3. Temporary Basic credentials are removed.
4. GitHub credential is repository-scoped and rotation is tested.
5. App and tunnel services have reviewed hardening and recovery behavior.
6. Loopback, origin, public, auth, API, cross-origin, and browser canaries pass.
7. Existing hostnames on the shared tunnel pass regression checks.
8. Alerts and incident procedures are active without secret logging.
9. Rollback and credential-revocation drills pass.
10. Release and closure records link immutable evidence.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Cloudflare Access identity provider and allow policy | Governance reviewer | G5 |
| Dedicated Toslop tunnel versus existing shared tunnel | Operations owner | G5 |
| Service hardening profile for local Wrangler | Security owner | G5 |
| Health-check location and alert destination | Operations owner | G5 |
| GitHub App versus fine-grained token | Repository owner | G5 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending retrospective conformance review |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | 2026-07-26 CI, readiness-gated hardened-service restart, successful five-minute canary unit, loopback/public checks, proxy tests, and edge Worker `9366be75-88f6-4a02-b756-ab20d74f4af1` |

The temporary deployment may remain available for review. G5 is blocked until
Cloudflare Access, scoped credentials, monitoring, and recovery evidence meet
the definition of done.
