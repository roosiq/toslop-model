# ES-004: Employer Compulsion Extraction

| Field | Value |
| --- | --- |
| Status | Draft, implementation blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-003 v0.1.0, approval pending |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G2, G3 |
| Start prerequisites | ES-003 bootstrap records; ES-009 development labels |
| Stage interfaces | Frozen candidate to ES-009; approved predictions to ES-005 |

## Implementation authorization

Implementation may begin only after IS-003 approval, an IS-002 corpus release
candidate exists, and ES-009 freezes the S7 label rubric, split policy, and
benchmark thresholds.

## Outcome

Provide a deterministic, source-blind extraction pipeline that identifies
eligible employer AI-use direction, assigns the six-level primary label, emits
independent mechanism flags and private evidence spans, and passes the frozen
S7 benchmark.

## Current state

- The current private gateway has conventional ML, NLP, and test dependencies,
  but no employer-compulsion module or labels.
- Existing authorship detector code is trained for AI-likeness and is prohibited
  from serving as an S7 feature or label.
- No S7 lexicon, annotation packet, classifier, or frozen extraction artifact
  exists.

## Architecture and boundaries

```text
eligible normalized document
          |
          v
sentence/paragraph segmentation
          |
          v
AI-use relevance gate
          |
          v
primary-level classifier + mechanism extractors
          |
          v
context rules: negation, quote, third party, historical
          |
          v
private evidence rows + document label
          |
          v
no-text prediction and benchmark artifacts
```

Proposed paths:

- `services/gateway/app/observatory/scorers/s7/rubric.py`
- `services/gateway/app/observatory/scorers/s7/features.py`
- `services/gateway/app/observatory/scorers/s7/rules.py`
- `services/gateway/app/observatory/scorers/s7/classifier.py`
- `services/gateway/app/observatory/scorers/s7/extract.py`
- `services/gateway/app/observatory/scorers/s7/artifacts/`
- `services/gateway/tests/observatory/s7/`
- public-safe rubric and evaluation packet under
  `toslop-model/docs/observatory/methods/s7/`

The production extractor accepts normalized employer-authored text only. It
does not receive source ID, employer ID, period, occupation, industry,
jurisdiction, URL, collector, or current score as model features.

## Data contracts

### Private passage prediction

```json
{
  "schema_version": "observatory.s7_passage_prediction.v1",
  "document_snapshot_id": "snap:...",
  "passage_id": "passage:...",
  "start_char": 120,
  "end_char": 286,
  "eligible": true,
  "relevance_probability": 0.97,
  "primary_level": "required",
  "primary_level_index": 4,
  "class_probabilities": {
    "none": 0.01,
    "optional": 0.01,
    "encouraged": 0.02,
    "expected": 0.08,
    "required": 0.85,
    "monitored_or_enforced": 0.03
  },
  "mechanisms": {
    "monitoring_or_audit": false,
    "performance_evaluation": false,
    "compensation_or_promotion": false,
    "discipline_or_continued_work": false,
    "mandatory_training": true,
    "tool_or_workflow_specific": true,
    "opt_out_or_accommodation": false
  },
  "context": {
    "negated": false,
    "quoted": false,
    "third_party": false,
    "historical_only": false
  },
  "extractor_version": "1.0.0",
  "rubric_version": "1.0.0"
}
```

Evidence offsets and text are private. Public predictions replace document and
passage IDs with benchmark-safe IDs and omit offsets when they could reveal
restricted text length or structure.

### Document prediction

The approval-blocked proposed rule sets the document primary level to the
highest non-negated eligible passage level. When two eligible passages conflict,
the higher level wins and the lower level remains in passage evidence. A
quoted, third-party, or historical-only passage does not set the document level
unless the rubric explicitly marks the employer as adopting that policy.
Implementation must not encode this proposal until the corresponding G2
decision record approves it or replaces it with an adjudicated conflict rule.

Document output includes:

- primary level and index;
- union of qualifying mechanism flags;
- eligible passage count;
- maximum and mean class probabilities;
- ambiguity and context warnings;
- extractor, feature, artifact, and rubric versions;
- lineage to every qualifying passage.

### Artifact metadata

The frozen artifact records:

- candidate type and hyperparameters;
- feature vocabulary checksum without training text;
- class order and label polarity;
- training, validation, and final manifest IDs;
- dependency versions and random seeds;
- benchmark and per-slice metrics;
- scorer limitations and release state;
- artifact files and SHA-256 checksums.

## Algorithm design

### Predeclared candidates

Implement exactly two candidate families before final evaluation:

1. **Rule baseline**: versioned phrase and context rules authored from the
   rubric and development partition.
2. **Linear text classifier**: word `1-2` gram and character `3-5` gram
   TF-IDF features, L2-regularized multinomial logistic regression, fixed class
   order, and validation-selected regularization from
   `{0.1, 0.3, 1.0, 3.0, 10.0}`.

The text classifier input is the passage plus at most one preceding and one
following sentence, separated by reserved boundary tokens. Feature
construction is fit on training only. Class balancing is selected between
`none` and `balanced` on validation using the same candidate-selection rule.

Mechanism flags use:

- high-precision deterministic rules for explicit monitoring, evaluation,
  compensation, discipline, training, opt-out, and tool specificity;
- one binary logistic classifier per flag only when the rule baseline misses
  the approved recall threshold on validation;
- context masks for negation, quotation, third-party attribution, and
  historical reporting.

No neural or LLM extractor enters MVP production. It may be evaluated later
under a new execution version and the same protected benchmark rules.

### Selection rule

An eligible candidate must meet every IS-003 required threshold. Among eligible
candidates:

1. maximize final-validation primary-level macro F1;
2. then maximize `monitored_or_enforced` precision;
3. then maximize `required` precision;
4. then choose the rule baseline if the absolute macro-F1 difference is below
   `0.01`;
5. otherwise choose the linear classifier.

Hyperparameters and selection use development and validation only. The final
partition is evaluated once for release disposition.

### Eligibility and abstention

A passage is `none` when no employer AI-use direction is present. It is
`ambiguous` and excluded from document escalation when:

- the top two class probabilities differ by less than the validation-frozen
  margin;
- context resolution cannot determine employer versus third-party language;
- segmentation or language eligibility failed;
- the artifact or feature version is unavailable.

Ambiguous prevalence is reported as a coverage component and may trigger
suppression under ES-005.

## Implementation tasks

1. Freeze rubric enums, examples, hard negatives, conflicts, and context rules.
2. Implement segmentation and source-blind feature contracts.
3. Implement rule baseline and unit fixtures.
4. Implement deterministic training dataset loader with protected split
   enforcement.
5. Implement linear candidate grid and validation reports.
6. Implement mechanism rules and only the benchmark-justified binary
   classifiers.
7. Implement document aggregation and evidence lineage.
8. Implement artifact package, checksum, role, and no-text report.
9. Run development and validation evaluation and freeze one candidate.
10. Execute protected final evaluation through ES-009.
11. Record HOLD or REJECT on any failed gate; otherwise produce a shadow
    artifact.
12. Add drift, throughput, and private evidence review tools.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Segmentation, class order, level index, context masks, mechanism rules, document max rule |
| Property | Source/time/employer metadata never changes a prediction, same bytes and version produce same output |
| Hard negatives | Product features, AI companies, applicant personal statements, quotation, negation, legal disclaimers |
| Benchmark | IS-003 macro F1, required and enforcement precision/recall, per-source and per-occupation slices |
| Leakage | Vocabulary and fitting use training only; duplicate groups do not cross splits |
| Artifact | Checksums, dependency versions, class polarity, load/predict round trip |
| Performance | At least 100,000 passages per CPU hour on the approved reference host, measured before release |
| Privacy | No text, offsets, source names, personal data, or private paths in public-safe outputs |

## Operational design

- Extraction runs after an immutable corpus release.
- Idempotency key: corpus release, document snapshot, extractor version.
- Writes are upserts on that key and never overwrite a different version.
- Transient worker failures retry three times; artifact, schema, rights, or
  lineage failures quarantine without retry.
- Metrics: passages per second, eligible and ambiguous rates, class and
  mechanism shares, probability distributions, hard-negative canary results,
  artifact load errors, and drift by approved diagnostic slice.
- Alerts: artifact checksum mismatch, class-order mismatch, throughput drop over
  30%, ambiguous-rate increase over 10 percentage points, or benchmark canary
  failure.
- A degraded rule-only mode has a distinct extractor version and cannot emit a
  production S7 score unless separately validated.

## Security, privacy, rights, and compliance

Training and prediction text remain in protected storage. Annotator and source
metadata are diagnostic only and excluded from runtime features. Artifact
loading is local and checksum-verified. Pickle artifacts are prohibited; use
safe serialized vocabulary, coefficients, intercepts, enums, and metadata.

## Release strategy

1. Rule baseline on synthetic fixtures.
2. Linear candidate on development and validation partitions.
3. Private shadow extraction on one corpus month.
4. Protected final evaluation.
5. Twelve-month shadow extraction with drift review.
6. Freeze artifact and public-safe evidence packet.
7. Hand off to ES-005; no public score yet.
8. Roll back by activating the prior extractor version and rebuilding affected
   document labels from its immutable corpus release.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Class-order or polarity mismatch | Artifact load test | Refuse artifact | Repackage from frozen metadata |
| New employer phrasing | Drift and error review | Warn or raise ambiguity | Label under new benchmark version |
| Context window crosses unrelated section | Segmentation fixture | Exclude passage | Fix segmentation and major-version extractor |
| Source identity leaks into features | Feature audit | Reject candidate | Remove feature and retrain |
| Mechanism rule overfires on negation | Hard-negative slice | Fail G3 | Fix on development partition and rerun |
| Public artifact includes text | Hygiene scan | Block release | Delete artifact and regenerate no-text packet |

## Definition of done

1. The exact IS-003 version in `Approved intent reference`, this exact
   execution-spec version, and the referenced rubric version are approved.
2. Candidate selection follows the predeclared rule.
3. Protected final metrics meet every IS-003 threshold.
4. Source-blindness, split isolation, artifact safety, and no-text gates pass.
5. Shadow extraction completes with stable throughput and drift.
6. Private evidence and public-safe packet reproduce metrics and checksums.
7. Monitoring, degraded behavior, and rollback are tested.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Ambiguity probability margin | Applied science lead | G2 |
| Approve passage max or replace it with a reviewed conflict rule | Research lead | G2 |
| Mechanism-specific classifier need | Applied science lead | G2 |
| Approved reference host and throughput budget | Operations owner | G3 |

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
