# ES-009: MVP Benchmark and Protected Evaluation

| Field | Value |
| --- | --- |
| Status | Synthetic framework complete; human benchmark blocked |
| Version | 0.1.0 |
| Created | 2026-07-25 |
| Execution owner | Applied science lead |
| Approved intent reference | IS-006 v0.1.0, synthetic framework boundary approved by DR-007 |
| Repositories | `slopslingers-infra`, `toslop-model` |
| Gates | G2, G3 |
| Start prerequisites | ES-001 contract; approved IS-006 |
| Stage interfaces | Bootstrap input from ES-003/ES-006; development and protected-final evaluation for ES-004/ES-007 |

## Implementation authorization

Synthetic framework work is authorized by DR-007. Human label
collection requires approved sources, annotator procedure, protected-store
policy, and governance review. Protected final evaluation requires frozen
scorer release candidates and a named research approver.

## Outcome

Provide one deterministic benchmark harness with public-safe schemas and
synthetic fixtures, protected text and labels, grouped splits, double
annotation, adjudication, candidate prediction ingestion, gate evaluation,
regression history, and no-text evidence packets for S7 and S3.

## Current state

- `toslop-model` already uses no-text manifests, deterministic split rules,
  protected evaluation concepts, checksums, and explicit HOLD/REJECT decisions
  for AI-likeness research.
- Those artifacts address a different construct and cannot validate S7 or S3.
- A synthetic-only implementation now provides strict benchmark contracts,
  grouped splits, append-only annotation transitions, protected-label role
  checks, classification and pairwise metrics, immutable gates, a
  prediction-only evaluator, lineage-consumption controls, and an aggregate
  public packet.
- Human labels, production protected storage, benchmark 1.0.0, and scorer
  validation remain blocked.

## Architecture and boundaries

```text
source-approved benchmark candidates
                 |
                 v
private annotation store <--> annotation and adjudication workflow
                 |
                 v
grouped immutable dev / validation / final manifests
                 |
      candidate predictions only
                 |
                 v
protected evaluator --> aggregate metrics + no-text predictions
                 |
                 v
public-safe benchmark packet in toslop-model
```

Private modules:

- `observatory/benchmarks/schemas.py`
- `observatory/benchmarks/synthetic.py`
- `observatory/benchmarks/splits.py`
- `observatory/benchmarks/annotation.py`
- `observatory/benchmarks/protected_store.py`
- `observatory/benchmarks/evaluate_s7.py`
- `observatory/benchmarks/evaluate_s3.py`
- `observatory/benchmarks/gates.py`
- `observatory/benchmarks/release.py`

Public-safe artifacts:

- `toslop-model/metadata/schemas/observatory_benchmark_*.schema.json`
- `toslop-model/services/evals/observatory/<benchmark-release>/`
- `toslop-model/docs/observatory/methods/benchmark/`

Raw text, protected labels, adjudication notes, and annotator identities stay in
the private object store and protected PostgreSQL schema.

## Data contracts

### Benchmark item manifest

```json
{
  "schema_version": "observatory.benchmark_item.v1",
  "benchmark_id": "mvp-s7-s3",
  "item_id": "bench:...",
  "construct": "S7",
  "task": "primary_level",
  "source_alias": "source-a",
  "logical_group_id": "group:...",
  "duplicate_cluster_id": "dup:...",
  "genre": "job_posting",
  "topic_id": null,
  "time_band": "post_transition",
  "private_object_id": "object:...",
  "rights_decision_version": "1.0.0",
  "split": "final",
  "manifest_version": "1.0.0"
}
```

Public manifests omit `private_object_id` and replace restricted source aliases
when required.

### Annotation

S7 annotations include:

- item and rubric version;
- annotator pseudonymous ID and qualification version;
- primary level;
- independent mechanisms;
- context flags;
- eligibility and ambiguity;
- private evidence spans and rationale;
- created time and revision lineage.

S3 annotations include:

- pair or triplet item IDs;
- task component;
- more-similar choice or tie;
- matched-frame validity;
- confounder flags;
- private rationale;
- annotator and rubric versions.

Annotations are append-only. Adjudication creates a new decision row and never
overwrites individual labels.

### Candidate prediction submission

```json
{
  "schema_version": "observatory.benchmark_predictions.v1",
  "candidate_id": "s7-linear-v1",
  "candidate_lineage_id": "s7-linear-family-1",
  "candidate_version": "1.0.0-rc.1",
  "candidate_freeze_record_id": "freeze:s7-linear-family-1:rc1",
  "benchmark_version": "1.0.0",
  "task": "s7_primary_level",
  "manifest_sha256": "...",
  "predictions_sha256": "...",
  "artifact_sha256": "...",
  "predictions": [
    {
      "item_id": "bench:...",
      "prediction": "required",
      "scores": {
        "required": 0.87
      }
    }
  ]
}
```

The protected runner accepts predictions, not candidate code, for final
evaluation. It verifies exact item coverage, no duplicates, finite scores,
manifest checksum, and a separately approved freeze record binding candidate
lineage, source revision, artifact checksum, features, formula, thresholds, and
weights. The submission registry rejects a lineage or bound descendant that has
already consumed that benchmark major version.

### Gate packet

The packet includes:

- candidate, corpus, feature, rubric, benchmark, and code versions;
- split and overlap audits;
- agreement and adjudication;
- pooled and required slice metrics;
- synthetic and negative-control results;
- interval calibration;
- artifact and no-text hygiene;
- gate-by-gate pass, fail, or blocked status;
- final disposition and named approval evidence.

## Algorithm design

### Split isolation

Build groups from the transitive union of:

- logical document ID;
- exact, near-duplicate, and syndication clusters;
- source-native revision group;
- authored synthetic template family;
- S3 pair or triplet family.

Hash the sorted group ID with the benchmark seed to assign development,
validation, or final according to approved proportions. Source and label
balancing may move whole groups only through a deterministic documented
optimizer. Final overlap with development or validation is zero.

### S7 evaluation

Calculate:

- six-class macro and per-class precision, recall, and F1;
- weighted Cohen kappa and ordinal mean absolute error;
- mechanism precision, recall, and F1;
- calibration error and reliability for class scores when available;
- hard-negative slice metrics;
- source-family, occupation, industry, time-band, and ambiguity diagnostics;
- confusion matrices and bootstrap intervals.

Required gates come from IS-003 and are immutable for benchmark 1.0.0.

### S3 evaluation

For each component:

- pairwise or triplet accuracy with ties;
- Spearman rank correlation with aggregate human ranking;
- matched-frame validity precision and recall;
- synthetic monotonicity;
- confounder false movement;
- component and top-level interval coverage;
- genre, topic, event, source, and template diagnostics.

Required gates come from IS-005.

### Human labeling

1. Train annotators on authored examples and development-only practice items.
2. Require qualification at the approved agreement and accuracy threshold.
3. Assign every item to two annotators, blinded to source identity where
   feasible, period hypothesis, and model output.
4. Adjudicate disagreements and all high-risk S7 levels.
5. Freeze labels before candidate final predictions are accepted.
6. Report agreement before and after adjudication.

### Protected final access

- Final text and labels are unavailable to scorer developers.
- The evaluator runs under a separate role and logs access.
- One final evaluation is allowed for one immutable candidate lineage against
  one benchmark major version. Renaming or version-bumping a candidate does not
  create another allowance.
- The evaluator commits the disposition before releasing aggregate final
  metrics. A failed or withdrawn candidate cannot submit any descendant,
  threshold change, feature change, or replacement candidate against that final
  partition.
- Any later candidate qualification requires a newly sampled, non-overlapping
  final partition under a new benchmark major version. The prior final result
  may be published, but it cannot become feedback for another candidate tested
  on the same items.
- Development and validation results remain the only iterative feedback
  available to scorer developers.
- Any benchmark correction creates a new benchmark major version and retires
  affected prior claims.

## Implementation tasks

1. Freeze benchmark schemas, source frame, task inventory, thresholds, and
   protected-store decision.
2. Implement synthetic schema, generators, expected outcomes, and checksum
   manifests.
3. Implement group construction, split optimizer, and zero-overlap audit.
4. Implement annotation, qualification, double-label, and adjudication flows.
5. Create development and validation labels and validate the rubric.
6. Freeze final manifests, protected labels, and a non-overlapping
   replenishment pool.
7. Implement S7 and S3 evaluators and bootstrap intervals.
8. Implement gate engine and immutable threshold registry.
9. Implement prediction-only final evaluation, lineage-aware submission
   registry, freeze-record verification, and access audit.
10. Implement no-text public packet and hygiene scan.
11. Run a reference bad candidate and reference fixture candidate to prove
    rejection and acceptance behavior.
12. Conduct independent benchmark, privacy, and claims review.

## Test and benchmark plan

| Layer | Tests |
| --- | --- |
| Unit | Schemas, label enums, groups, hashing, metrics, ties, gate comparisons, disposition |
| Property | No group overlap, deterministic split, item order invariance, finite metrics |
| Synthetic | Every declared direction, warning, suppression, and negative control |
| Protected runner | Missing/extra/duplicate item, wrong manifest, lineage alias or descendant reuse, repeated submission, unauthorized label access |
| Annotation | Qualification, double assignment, revision, adjudication, anonymized export |
| Security | Role isolation, audit logging, object access, no arbitrary candidate code |
| Hygiene | No raw text, private IDs, source paths, annotator identities, or labels in public packet |
| Reproducibility | Public metrics recompute from permitted no-text predictions and aggregate labels |

## Operational design

- Benchmark releases and thresholds are immutable.
- Annotation and final evaluation roles are separate from candidate developers.
- Metrics: labeling throughput, disagreement, adjudication, unresolved items,
  split counts, access events, candidate submissions, gate outcomes, and
  hygiene findings.
- Alerts: protected-label access outside workflow, duplicate submission,
  manifest mismatch, overlap, source-rights expiry, or public hygiene failure.
- Backups encrypt protected labels and use a separate retention decision.
- Benchmark retirement immediately blocks new validation against the retired
  version.

## Security, privacy, rights, and compliance

Final text and labels use least-privilege access, encryption, audit logs, and
source-specific retention. Candidate code never executes in the protected
evaluator. Public-safe artifacts pass deterministic pattern checks and semantic
review for text, identity, path, and claim leakage.

## Release strategy

1. Synthetic benchmark 0.x.
2. Development annotation pilot.
3. Rubric revision and qualification freeze.
4. Validation annotation and evaluator dry run.
5. Final partition freeze and access lockdown.
6. Reference rejection and acceptance tests.
7. Benchmark 1.0.0 release packet.
8. First scorer final evaluations.
9. Roll back by retiring a compromised benchmark and reverting scorer release
   claims; final labels are never silently edited.

## Known failure modes

| Failure | Detection | Behavior | Recovery |
| --- | --- | --- | --- |
| Duplicate group crosses splits | Overlap audit | Block benchmark | Repair grouping and major-version split |
| Annotator agreement below threshold | Agreement report | Hold label freeze | Retrain, revise rubric, relabel |
| Final labels leak | Access audit or artifact scan | Retire benchmark and affected claims | Investigate, rotate access, create new benchmark |
| Candidate or descendant probes final set repeatedly | Lineage-aware submission registry | Reject submission and hold release | Qualify only against a newly sampled benchmark major version |
| Source rights expire | Policy check | Suspend affected benchmark | Remove under new major version |
| Public packet contains text | Hygiene gate | Block publication | Delete and regenerate allowlisted packet |

## Definition of done

1. The exact IS-006 version in `Approved intent reference`, this exact
   execution-spec version, and the protected-store policy are approved.
2. Synthetic, development, validation, and final manifests are immutable and
   overlap-free.
3. Annotation agreement and adjudication requirements pass.
4. Protected evaluator rejects malformed and unauthorized submissions.
5. Gate engine exactly implements IS-003 and IS-005 thresholds.
6. Reference bad and good candidates produce expected dispositions.
7. Public-safe packet is reproducible and contains no restricted data.
8. Independent research, privacy, and benchmark reviews pass.

## Open decisions

| Decision | Owner | Blocking gate |
| --- | --- | --- |
| Annotator qualification thresholds | Research lead | G2 |
| Split proportions and balancing optimizer | Applied science lead | G2 |
| S3 pair, triplet, and tie design | Research lead | G2 |
| Replenishment-pool size and benchmark refresh cadence | Research lead | G2 |
| Protected-store operator | Governance reviewer | G2 |

## Approval

| Field | Value |
| --- | --- |
| Decision | Pending |
| Approved execution version | None |
| Approved intent version | None |
| Approver | None |
| Decision date | None |
| Evidence | None |

The synthetic framework is implemented under DR-007. Human benchmark
construction and protected final scorer evaluation remain blocked until this
table records approval for this exact execution version and the exact approved
intent version.
