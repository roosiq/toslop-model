# Project Plan: Web-Scale LLM Cognitive Impact Observatory

| Field | Value |
| --- | --- |
| Document type | Parent project plan |
| Version | 0.1.0 |
| Status | Proposed |
| Created | 2026-07-25 |
| Planning horizon | MVP through production observatory |
| Program owner | Pending assignment |
| Research lead | Pending assignment |

## Purpose

Build reproducible, longitudinal scorers for public signals associated with
LLM-mediated cognitive, epistemic, linguistic, labor-market, and
knowledge-production changes.

The observatory measures public traces and exposure relationships. It does not
diagnose people, infer private mental states, prove individual AI use, or
collapse distinct mechanisms into one sensational score.

## Objectives

| ID | Objective | Measurable result |
| --- | --- | --- |
| O1 | Create a shared longitudinal data foundation | Normalized, deduplicated, versioned corpora with source and transformation provenance |
| O2 | Implement eight transparent scorers | Monthly or quarterly scores with components, baselines, uncertainty, coverage, and warnings |
| O3 | Separate description from causation | Descriptive trends, exposure associations, and causal estimates are stored and reported as different evidence classes |
| O4 | Make every score auditable | Formula, source coverage, benchmark performance, lineage, and scorer version are visible |
| O5 | Support spec-driven delivery | Every work package has an approved intent spec and one or more execution specs before implementation |

## Design principles

- **Observable, not diagnostic**: Describe changes in public behavior and
  information systems, not individual cognitive conditions.
- **Longitudinal by default**: Use explicit historical, transition, and current
  periods. Retain the raw time series behind every comparison.
- **Mechanism-specific**: Keep employer compulsion, source concentration,
  language convergence, and the other constructs separate.
- **Transparent decomposition**: Return raw and normalized components, sample
  size, coverage, uncertainty, warnings, and versions.
- **Causal humility**: A trend is descriptive. LLM exposure is associative
  unless a reviewed design identifies a causal estimate.
- **Reproducibility**: Pin source snapshots, transformations, features,
  benchmarks, and model artifacts.
- **Minimal LLM dependency**: Prefer deterministic or conventional ML
  components. Any LLM extractor requires a benchmark, pinned model and prompt,
  retained outputs, drift monitoring, and a degraded mode.

## Score portfolio

| ID | Score | Measurement question | Primary data families |
| --- | --- | --- | --- |
| S1 | External Exploration | Are people consulting a broad set of external sources and public knowledge systems? | Search-interest aggregates, Wikipedia, Stack Exchange, and link or citation traces |
| S2 | Source Concentration | Are references and links concentrating among fewer domains, publishers, or owners? | Web snapshots, GDELT, OpenAlex, and outbound links |
| S3 | Language Homogenization | Is writing becoming more lexically, syntactically, rhetorically, and semantically similar within matched contexts? | Public web text, professional writing, research abstracts, and job postings |
| S4 | Perspective Diversity | Are fewer distinct frames, arguments, causes, and proposed actions visible within a topic? | News, forums, public corporate text, and event corpora |
| S5 | Model-Language Diffusion | Are model-associated language patterns spreading into public writing? | Controlled model corpus and longitudinal public corpora |
| S6 | Human Knowledge Contribution | Are public human Q&A and explanatory contributions weakening? | Stack Exchange, GitHub, Wikipedia, and eligible forums |
| S7 | Employer AI Compulsion | Are employers requiring, monitoring, or economically pressuring AI use? | Job postings, public career pages, policy statements, and annual reports |
| S8 | Novel Information Density | Is content volume growing faster than unique claims, perspectives, and sources? | Web snapshots, news, corporate content, and research abstracts |

## Shared analytical unit

The canonical analytical key is:

```text
entity x topic x period x source
```

Every aggregate must retain traceability to eligible records and source
snapshots. Supported examples include employer by quarter, occupation by month,
news topic by week, and knowledge community by month.

## Program architecture

```text
source acquisition
      |
      v
immutable raw snapshots + rights metadata
      |
      v
normalization + provenance + document identity
      |
      v
deduplication + entity/topic resolution
      |
      v
versioned feature sets
      |
      v
monthly/quarterly analytical aggregates
      |
      v
scoring + uncertainty + suppression
      |
      v
versioned API + public dashboard + evidence packets
```

Raw snapshots and restricted normalized text belong in the private
implementation boundary. The public replication repository contains schemas,
source identifiers, checksums, aggregate metrics, benchmark definitions, and
approved no-text evidence.

## Workstreams

| Workstream | Work packages |
| --- | --- |
| WS1 Program Definition and Governance | WP1.1 constructs and exclusions; WP1.2 scoring and confidence; WP1.3 ethics, privacy, and claims; WP1.4 versioning and release |
| WS2 Data Foundation | WP2.1 source inventory and licensing; WP2.2 canonical schemas; WP2.3 collectors and raw storage; WP2.4 deduplication and provenance; WP2.5 publisher, employer, and ownership resolution |
| WS3 Shared Analytical Components | WP3.1 topic assignment; WP3.2 linguistic features; WP3.3 embeddings and clustering; WP3.4 claims and arguments; WP3.5 frame taxonomy; WP3.6 controlled model-language corpus |
| WS4 MVP Scorers | WP4.1 Employer AI Compulsion; WP4.2 Language Homogenization; WP4.3 MVP reporting and drill-down |
| WS5 Diversity and Information Quality | WP5.1 Source Concentration; WP5.2 Perspective Diversity; WP5.3 Novel Information Density |
| WS6 Behavior and Knowledge Systems | WP6.1 External Exploration; WP6.2 Human Knowledge Contribution |
| WS7 Model Influence | WP7.1 prompt suite and capture; WP7.2 distinctive patterns; WP7.3 diffusion and lag analysis |
| WS8 Validation and Causal Analysis | WP8.1 synthetic suite; WP8.2 labeled benchmark; WP8.3 external-event validation; WP8.4 causal studies; WP8.5 sensitivity and confounders |
| WS9 Productization | WP9.1 Score API; WP9.2 research dashboard; WP9.3 lineage; WP9.4 monitoring and release |

## Initial intent-spec set

| Intent | Outcome | Primary work packages |
| --- | --- | --- |
| IS-001 | Shared score ontology and reporting semantics | WP1.1-WP1.4 |
| IS-002 | Compliant longitudinal public job-posting corpus | WP2.1-WP2.5 |
| IS-003 | Employer AI Compulsion scorer | WP4.1 |
| IS-004 | Topic- and genre-controlled professional-writing corpus | WP2.1-WP2.5, WP3.1 |
| IS-005 | Language Homogenization scorer | WP3.2-WP3.3, WP4.2 |
| IS-006 | MVP validation benchmark | WP8.1-WP8.3, WP8.5 |
| IS-007 | MVP research dashboard | WP4.3, WP9.1-WP9.4 |
| IS-008 | Authenticated observatory specification administration | WP1.4, WP9.3, WP9.4 |

## Delivery sequence

| Phase | Indicative duration | Scope | Exit criteria |
| --- | --- | --- | --- |
| Phase 0: Definition | 4-6 weeks | WS1 and source feasibility | Approved construct definitions, claims policy, source decision records, and score contract |
| Phase 1: Data foundation | 6-10 weeks | WS2 and core WS3 | Versioned corpora, canonical schemas, provenance, deduplication, and entity resolution |
| Phase 2: MVP | 8-12 weeks | WS4 and validation subset | S7 and S3 shadow scores, benchmark packet, API, and dashboard |
| Phase 3: Information diversity | 8-12 weeks | WS5 | S2, S4, and S8 meet scorer gate |
| Phase 4: Behavioral systems | 8-12 weeks | WS6 | S1 and S6 meet scorer gate |
| Phase 5: Model diffusion | 8-12 weeks | WS7 | S5 reference corpus and diffusion scorer meet scorer gate |
| Phase 6: Causal and production maturity | Ongoing | WS8 and WS9 | Reviewed causal studies, stable operations, and quarterly releases |

Durations are planning ranges, not commitments. A phase does not start solely
because time elapsed; its entry gates must pass.

## Gate model

| Gate | Requirement |
| --- | --- |
| G0 Construct | Construct, score semantics, exclusions, users, and claims policy approved |
| G1 Data | Rights, coverage, provenance, historical baseline, quality, and retention approved |
| G2 Benchmark | Synthetic suite and adjudicated benchmark frozen before score tuning |
| G3 Scorer | Formula, components, uncertainty, suppression, failure warnings, and benchmark thresholds pass |
| G4 Research | Exposure and causal claims reviewed separately from descriptive release |
| G5 Production | Lineage, monitoring, rollback, public methodology, security, and release evidence complete |

## Program acceptance

The program is complete only when:

1. All eight constructs have approved definitions, exclusions, directionality,
   and human-readable semantics.
2. Every published result is reproducible from versioned source snapshots and
   transformation code.
3. Every result exposes the standard score contract and uses suppression when
   evidence is insufficient.
4. No public output diagnoses an individual, proves AI authorship from style, or
   presents a cross-construct composite as a public fact.
5. Each scorer passes synthetic validation and its approved human-labeled or
   external benchmark.
6. Descriptive, exposure-association, and causal outputs remain visibly and
   structurally distinct.
7. Source rights, privacy, retention, and access controls are approved.
8. At least one reviewed exposure or quasi-experimental study exists before the
   program uses causal LLM-impact wording.
9. Production scorers monitor source outages, distribution shift, benchmark
   regression, data freshness, and lineage completeness.
10. Every work package closes with approved intent and execution specs plus
    release or closure evidence.

## Major risks and controls

| Risk | Failure mode | Required control |
| --- | --- | --- |
| Causal overreach | A post-2022 trend is attributed to LLMs despite other causes | Evidence-class field, matched controls, event studies, and claim review |
| Genre or topic confounding | Similar subjects naturally look linguistically similar | Matched strata, residualization, event controls, and sensitivity analysis |
| Source instability | APIs, robots rules, or access terms change | Snapshot manifests, source health checks, versioned collectors, and substitutes |
| Licensing constraints | Text or job postings cannot be retained or redistributed | Source-specific decision record, field minimization, restricted storage, and aggregate publication |
| Extraction drift | Provider or model changes alter claims, frames, or classifications | Pinned versions, retained outputs, release benchmark, and deterministic fallback |
| False AI-authorship inference | Model-like language is treated as proof of generation | Similarity and diffusion language only; no document-level authorship verdict |
| Benchmark subjectivity | Frame or compulsion labels vary by reviewer | Rubric, double labeling, adjudication, and inter-rater reporting |
| Composite misuse | Stakeholders demand one sensational score | Separate APIs and views; no public cross-construct composite |
| Data sparsity | Small strata generate unstable results | Minimum sample rules, effective sample size, intervals, shrinkage policy, and suppression |

## Decision rights

| Role | Accountability |
| --- | --- |
| Program owner | Priorities, scope, funding, and final release |
| Research lead | Construct validity, causal design, interpretation, and publication |
| Data lead | Sources, rights implementation, schemas, pipelines, quality, and lineage |
| Applied science lead | Features, formulas, benchmarks, uncertainty, and drift |
| Product and UX lead | Research workflow, dashboard, drill-down, and explanation |
| Governance reviewer | Privacy, ethics, claims policy, and misuse controls |
| Intent-spec owner | Outcome, boundaries, acceptance criteria, and approval packet |
| Execution-spec owner | Architecture, delivery plan, verification, operations, and closure |

Named assignees remain an approval-blocking decision.
