# DR-001: Observatory Implementation Directive

| Field | Value |
| --- | --- |
| Status | Approved |
| Version | 1.0.0 |
| Created | 2026-07-25 |
| Decision owner | Program owner |
| Gate | G0 implementation start |
| Affected spec versions | IS-001 through IS-008 v0.1.0; ES-001 through ES-014 current draft versions |
| Supersedes | None |

## Decision

Implementation of the current Observatory specifications is authorized in
dependency order. This directive authorizes code, synthetic fixtures,
development benchmarks, private shadow pipelines, interface design, and
non-production verification.

It does not authorize public scorer release, causal claims, source acquisition
without a source-specific rights decision, protected-label access, or
publication of entity-level results. Those narrower gates remain fail closed.

Until scorer-specific decisions are approved:

- score normalization is declared per score and is never shared implicitly;
- confidence is an externally calibrated evidence-sufficiency value, not a
  probability of causation or construct truth;
- public results are aggregate only, with entity-level publication disabled;
- minimum sample, baseline, and release thresholds are mandatory registry
  fields and a missing value blocks release;
- major versions are not joined without an approved version bridge.

## Context and evidence

The program owner directed implementation with the instruction: "create todos
for each spec and build them." The preceding implementation had concentrated on
the administration shell while the score, data, benchmark, and dashboard
execution specs remained blocked.

This record preserves the instruction as implementation authorization while
retaining G1-G5 release, rights, benchmark, causal-review, and operations gates.

## Alternatives considered

| Alternative | Reason accepted or rejected |
| --- | --- |
| Leave all execution blocked | Rejected because it contradicts the explicit implementation directive |
| Treat the directive as public-release approval | Rejected because source rights, benchmarks, and scorer release evidence do not exist |
| Start implementation with fail-closed release defaults | Accepted because it permits engineering without fabricating evidence or bypassing later gates |

## Consequences

- ES-001 is the first implementation slice.
- Work proceeds through the staged dependency model in the execution-spec
  index.
- Synthetic and development-safe fixtures may be committed publicly.
- Real source collection requires a separate approved source decision.
- No score can enter `production` release state until its remaining gates pass.

## Revisit conditions

Supersede this record when the program owner pauses implementation, changes the
score portfolio, authorizes a public release, or changes the repository
boundaries.

## Approval

| Field | Value |
| --- | --- |
| Decision | Approved for implementation; release gates retained |
| Approved version | 1.0.0 |
| Approver | Ryan Cook, program owner |
| Decision date | 2026-07-25 |
| Evidence | Direct project instruction in the implementation session |
