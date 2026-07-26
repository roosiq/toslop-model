# ES-001: Score Registry and Output Contract

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-001 v0.1.0, approval pending |
| Repositories | `toslop-model`, `slopslingers-infra`, `toslop` |
| Gates | G0, G3, G5 |
| Start prerequisites | None beyond exact intent approval |
| Stage interfaces | Contract candidate to ES-002-ES-011 |

## Implementation authorization

Implementation may begin only after
[IS-001](../intent-specs/IS-001-score-ontology-and-reporting-semantics.md)
records approval for the exact referenced version and the unresolved baseline,
confidence, minimum-sample, normalization, and publication decisions have
versioned decision records.

## Outcome

Provide one source-controlled score registry, warning registry, JSON Schema,
validation library, fixtures, and compatibility policy used by batch scoring,
private APIs, the public Worker, exports, and documentation.

## Current state

- `toslop/src/index.js` normalizes the current AI-likeness summary and exposes
  `/summary.json`; this is not the observatory contract.
- `slopslingers-infra/services/gateway/app/schemas.py` contains current FastAPI
  product models but no S1-S8 ontology.
- The public model repository now contains proposed
  `docs/observatory/contracts/score-output.schema.json` and
  `warning-codes.json`.
- No generated language bindings, conformance fixtures, or compatibility tests
  exist.

## Architecture and boundaries

```text
toslop-model canonical JSON files
        |
        +--> checksum-locked mirror in private gateway
        |        |
        |        +--> Pydantic validation + database checks
        |        +--> batch scorer output validation
        |
        +--> checksum-locked mirror in public Worker
                 |
                 +--> upstream response minimization
                 +--> export and regression validation
```

The canonical public-safe JSON Schema and registries live in `toslop-model`.
Release automation copies exact bytes into each consuming repository and
records SHA-256 values. Consumers must fail CI on checksum or generated-binding
drift.

Proposed paths:

- `toslop-model/docs/observatory/contracts/score-output.schema.json`
- `toslop-model/docs/observatory/contracts/warning-codes.json`
- `toslop-model/docs/observatory/contracts/fixtures/*.json`
- `slopslingers-infra/services/gateway/app/observatory/contracts/`
- `slopslingers-infra/services/gateway/app/observatory/models.py`
- `toslop/public/observatory/contracts/`
- `toslop/scripts/validate-observatory-contracts.mjs`

## Data contracts

The normative output contract is
[score-output.schema.json](../contracts/score-output.schema.json). The warning
registry is
[warning-codes.json](../contracts/warning-codes.json).

Additional registry files:

```json
{
  "schema_version": "observatory.score_registry.v1",
  "registry_version": "1.0.0",
  "scores": [
    {
      "id": "S7",
      "slug": "employer-ai-compulsion",
      "name": "Employer AI Compulsion",
      "direction": "higher_means_more_compulsion",
      "public_composite_allowed": false,
      "supported_evidence_classes": ["descriptive"],
      "current_value_unit": "bounded_pressure_0_to_100",
      "score_transform_id": "identity_bounded_score_v1",
      "change_basis": "current_value_minus_baseline_value",
      "required_components": [
        "primary_level_pressure",
        "required_prevalence",
        "monitoring_or_enforcement_prevalence"
      ],
      "intent_version": "1.0.0"
    }
  ]
}
```

Validation rules beyond JSON Schema:

1. Component weights sum to `1.0 +/- 1e-9` for a released score.
2. Warning codes exist in the pinned registry.
3. Suppressed results null `score`, `current_value`, baseline value, change,
   confidence value, uncertainty bounds, and every component value; they have
   trend `insufficient` and at least one suppression reason.
4. Released results are finite, have complete coverage and baseline state,
   non-null confidence, uncertainty bounds, and component values, and no
   suppression reasons.
5. `period.end >= period.start`.
6. Evidence class is allowed by the score registry and release packet.
7. Every lineage snapshot and version resolves in the private catalog.
8. A causal estimate links to a separately approved study release.
9. Major-version series are not joined without an approved bridge record.
10. Unknown fields fail at every public boundary.
11. A scorer-specific registry function recomputes `score` from
    `current_value` and components, recomputes absolute and relative change from
    the reported baseline, and rejects any mismatch. JSON Schema alone is not
    treated as arithmetic validation.
12. The semantic validator requires
    `uncertainty_interval.lower <= uncertainty_interval.upper`, the approved
    interval level and method, and the scorer-specific minimum replicate and
    clustering rules.

`current_value` and `baseline.value` use the raw construct unit declared by the
score registry; they are not assumed to equal the bounded `score`. The registry
must declare the score transformation and change basis, and every producer and
public boundary must execute the same pinned semantic validator.

## Algorithm design

The registry does not calculate a construct score. It calculates shared
contract state:

- score validity;
- warning severity;
- suppression state;
- release and evidence-class compatibility;
- version compatibility;
- confidence-display eligibility;
- public field allowlisting.

`confidence.value` is accepted only from a scorer-specific calibration version
listed in the release packet. Shared validation never derives confidence from
score magnitude.

## Implementation tasks

1. Freeze the exact approved IS-001 version referenced by this execution spec
   and create the score, warning, evidence-class, release, and version-bridge
   registries in `toslop-model`.
2. Add positive fixtures for all eight scores, plus missing, suppressed,
   warned, version-break, exposure-association, and causal-study fixtures.
3. Add negative fixtures for composite score, unknown warning, missing lineage,
   invalid period, invalid confidence or uncertainty, any non-null suppressed
   value, incomplete released baseline or coverage, unavailable released
   components, arithmetic mismatch, and unapproved causal class.
4. Implement Pydantic models and registry validation under
   `slopslingers-infra/services/gateway/app/observatory/`.
5. Implement JSON Schema and registry validation in `toslop` using vendored
   files and deterministic JavaScript checks.
6. Add a mirror script that copies canonical files, writes checksums, and fails
   if a consumer has local semantic edits.
7. Add CI checks in all three repositories.
8. Generate public reference documentation from registry values without
   allowing generated copy to replace approved claim text.
9. Record version 1.0.0 release evidence and rollback instructions.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Schema fields, enums, periods, score bounds, confidence, warning lookup, component weights, suppression |
| Property | Random finite values, period order, component weight sums, unknown-field rejection, suppressed-state invariants |
| Integration | Batch JSON to Postgres to FastAPI to Worker to CSV/JSON export |
| Regression | Existing Toslop summary and scoring routes remain byte- or behavior-compatible where required |
| Compatibility | Patch/minor acceptance, major-version rejection, approved bridge acceptance |
| Security | Unknown upstream fields, stack traces, private paths, NaN/Infinity, oversized arrays, hostile strings |
| Documentation | Registry names, direction, and warning explanations match public methodology |

All fixtures must pass in Python and JavaScript. A fixture accepted in one
runtime and rejected in another blocks release.

## Operational design

- Registry files are immutable per semantic version.
- Consumers log schema and registry versions with every validation failure.
- A checksum mismatch blocks build and deploy.
- Unknown warning or evidence values fail closed.
- Metrics: validation failures by code, unknown fields, checksum mismatch,
  suppressed/released counts, and version-bridge use.
- Alerts: any production checksum mismatch, causal-class rejection, unknown
  warning, or output-contract failure.
- Rollback restores the prior mirrored contract and scorer release as one
  versioned unit.

## Security, privacy, rights, and compliance

Contract fixtures contain only synthetic or public-safe aggregate data. URLs
and IDs use reserved examples. Validation errors returned publicly use
allowlisted messages and never echo an upstream payload, private path, source
text, or stack trace.

## Release strategy

1. Run conformance in all three repositories.
2. Shadow-validate existing synthetic and scorer fixture outputs.
3. Freeze registry and contract 1.0.0 checksums.
4. Deploy private validation before any score-producing endpoint.
5. Deploy public Worker validation before enabling observatory routes.
6. Publish methodology and compatibility policy.
7. Roll back all consumers together if conformance differs.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Consumer contract drift | Checksum CI | Block build/deploy | Re-copy canonical bytes and review semantic change |
| Python/JS validation disagreement | Cross-runtime fixture test | Block release | Fix implementation, not fixture expectation |
| Unknown warning | Registry lookup | Suppress upstream result | Upgrade registry or correct scorer |
| Major scorer version joined | Compatibility validator | Break series and warn | Add reviewed bridge or retain separate series |
| Private diagnostic in payload | Public allowlist test | Return bounded unavailable response | Fix upstream and add regression fixture |

## Definition of done

1. The exact IS-001 version in `Approved intent reference` and this exact
   execution-spec version are approved.
2. Canonical score and warning registries and JSON Schema are version 1.0.0.
3. All eight positive fixtures and all negative fixtures pass identically in
   Python and JavaScript.
4. Private batch/API and public Worker consumers validate exact mirrored bytes.
5. CI blocks drift, unknown values, composite output, and invalid causal class.
6. Methodology and compatibility documentation are published.
7. Monitoring, alert, rollback, and release evidence are complete.
8. Existing Toslop tests pass.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Final confidence calibration contract | Applied science lead | G0 |
| Public entity dimension policy | Governance reviewer | G0 |
| Version-bridge approval format | Research lead | G3 |
| Canonical registry release owner | Program owner | G5 |

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
