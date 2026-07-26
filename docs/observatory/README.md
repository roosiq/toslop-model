# Web-Scale LLM Cognitive Impact Observatory

This directory is the documentation control plane for the proposed Web-Scale
LLM Cognitive Impact Observatory. The program measures longitudinal changes in
public web behavior and information systems. It does not diagnose individuals,
infer mental states, or provide a single composite "brainwashing" score.

## Document status

All specifications in this directory are **proposed** until their approval table
contains a named approver, decision date, and immutable approval evidence. An
execution specification may be drafted against a proposed intent, but
implementation must not begin until the referenced intent version and the exact
execution-spec version are both approved.

## Start here

1. Read the [parent project plan](project-plan.md).
2. Review the [intent-spec index](intent-specs/README.md).
3. After intent approval, use the
   [execution-spec index](execution-specs/README.md) to locate the technical
   implementation contract.
4. Use the [score output JSON Schema](contracts/score-output.schema.json) when
   implementing or validating score-producing interfaces.
5. Record blocking choices in the
   [decision-record index](decision-records/README.md), scorer cutovers in the
   [release-record index](release-records/README.md), and completed work
   packages in the [closure-record index](closure-records/README.md).

## Repository boundaries

| Repository | Role | Must not contain |
| --- | --- | --- |
| `toslop-model` | Public-safe constructs, methods, benchmark definitions, specifications, aggregate evaluation artifacts, and scorer documentation | Redistributable raw corpus text, secrets, private source paths, or production activation state |
| `slopslingers-infra` | Private collectors, storage, feature pipelines, scoring jobs, APIs, operations, and production configuration | Public browser credentials or undocumented direct browser access to the private gateway |
| `toslop` | Public Cloudflare Worker, observatory dashboard, public methodology pages, same-origin API proxy, and authenticated specification-administration application | Raw corpora, browser-visible credentials, private gateway secrets, or scorer training and batch execution |

The existing Toslop AI-likeness measurement is a separate instrument. It may
be used as an input to future model-language research only after an approved
intent spec says how. It is not silently promoted into any of the eight
observatory scores.

## Specification lifecycle

```text
proposed intent
      |
      v
intent approval (G0)
      |
      v
execution spec + blocking decision records
      |
      v
execution approval
      |
      v
data, benchmark, and scorer gates (G1-G3)
      |
      v
research review (G4)
      |
      v
production release (G5)
```

Allowed specification states are:

- `proposed`: ready for review; not authorized for implementation.
- `approved`: outcome and boundaries are authorized for the named version.
- `superseded`: replaced by a newer approved version.
- `withdrawn`: intentionally closed without implementation.

Execution states add `implementing`, `shadow`, `released`, and `retired`.
The canonical blocked execution state is `Draft, implementation blocked`;
abbreviated aliases are not used.

## Program rules

- Keep the eight constructs separate in storage, APIs, dashboards, and prose.
- Expose score components, raw values, sample size, coverage, uncertainty,
  lineage, version, and warnings with every score.
- Label findings as `descriptive`, `exposure_association`, or
  `causal_estimate`. Do not imply that one class is another.
- Suppress results that fail minimum sample, coverage, rights, quality, or
  benchmark gates.
- Keep raw source snapshots immutable and reconstruct every published result
  from versioned inputs and transformations.
- Prefer deterministic extraction. Benchmark, pin, and retain outputs for any
  LLM-assisted extraction step.
- Never label an individual document as AI-authored from style alone.
