# Observatory Delivery Fixture Boundary

## Status

The read API, Worker proxy, and dashboard are implemented for contract fixtures
and disabled production routes under DR-008. No empirical Observatory score is
published.

## Public behavior

`/observatory/` first requests the public release-health contract. When no
approved score release exists, the page displays `Not released` and does not
request or invent series values.

When a release is available, the page requests a same-origin series, coverage,
and release packet. S7 and S3 use separate modes, source frames, charts, tables,
exports, and evidence metadata.

## Boundary controls

- The private API reads a security-barrier view, not corpus or benchmark text.
- The public Worker carries the upstream credential server-side.
- Exact route and query allowlists reject arbitrary filters.
- Upstream redirects, time, bytes, schemas, unknown fields, mixed score IDs,
  malformed ETags, and diagnostic bodies fail closed.
- JSON output is validated against ES-001. CSV uses fixed columns and
  spreadsheet-formula-safe cells.
- Bootstrap scores are absent from the default store and public database view.
- `OBSERVATORY_API_ENABLED` defaults to `false`.

## Fixture evidence

Python tests cover query behavior, cursor integrity, ETags, release approval,
contract revalidation, empty state, and migration policy. Node tests cover
existing routes, contracts, proxy authentication and redaction, unknown
queries, oversized and invalid upstream responses, exports, URL state, score
modes, and dashboard states.

Browser checks cover 375, 768, and 1280 pixel layouts. A populated fixture pass
verifies chart pixels, three trend rows, component binding, latest-period
selection, coverage and warnings, clean console, and document-width
containment.

Fixture values are not research findings and must not be enabled in production.
