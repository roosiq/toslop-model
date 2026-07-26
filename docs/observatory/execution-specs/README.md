# Execution-Spec Index

These documents describe proposed implementation and verification. Every
execution spec is **blocked** until its exact intent-spec reference is approved.
Drafting an execution spec does not waive G0-G5.

| ID | Execution boundary | Intent reference | Status |
| --- | --- | --- | --- |
| [ES-001](ES-001-score-registry-and-output-contract.md) | Score registry, warning registry, and output contract | IS-001 v0.1.0 | Contract implementation complete; release gates retained |
| [ES-002](ES-002-source-registry-and-immutable-storage.md) | Source governance, metadata store, immutable objects, and deletion lineage | IS-002 v0.1.0 | Development foundation complete; production activation blocked |
| [ES-003](ES-003-job-posting-collectors-and-normalization.md) | Job-posting collectors, normalization, deduplication, and entity resolution | IS-002 v0.1.0 | Synthetic shadow complete; real collection blocked |
| [ES-004](ES-004-employer-compulsion-extraction.md) | S7 rubric, classifier, mechanism extraction, and evidence | IS-003 v0.1.0 | Synthetic bootstrap complete; candidate freeze blocked |
| [ES-005](ES-005-employer-compulsion-aggregation.md) | S7 formula, uncertainty, aggregation, backfill, and release | IS-003 v0.1.0 | Synthetic formula complete; scorer release blocked |
| [ES-006](ES-006-professional-writing-corpus-pipeline.md) | Professional-writing ingestion, controls, and corpus releases | IS-004 v0.1.0 | Synthetic corpus complete; real collection blocked |
| [ES-007](ES-007-language-feature-and-control-pipeline.md) | S3 lexical, syntactic, rhetorical, semantic, and matching features | IS-005 v0.1.0 | Synthetic fallbacks complete; feature release blocked |
| [ES-008](ES-008-language-homogenization-aggregation.md) | S3 formula, uncertainty, sensitivities, backfill, and release | IS-005 v0.1.0 | Synthetic formula complete; scorer release blocked |
| [ES-009](ES-009-mvp-benchmark-and-protected-evaluation.md) | Synthetic, labeled, protected-final, and regression benchmark system | IS-006 v0.1.0 | Synthetic framework complete; human benchmark blocked |
| [ES-010](ES-010-observatory-read-api-and-worker-proxy.md) | Private read API, public Worker proxy, caching, and exports | IS-007 v0.1.0 | Draft, implementation blocked |
| [ES-011](ES-011-observatory-dashboard-and-release.md) | Research dashboard, accessibility, QA, monitoring, and production cutover | IS-007 v0.1.0 | Draft, implementation blocked |
| [ES-012](ES-012-astro-administration-interface.md) | Astro admin interface, public/admin boundaries, responsive layout, and browser behavior | IS-008 v0.1.0 | Draft, retrospective conformance review required |
| [ES-013](ES-013-github-specification-workflow.md) | GitHub discovery, validation, concurrency, branch, and pull-request workflow | IS-008 v0.1.0 | Draft, retrospective conformance review required |
| [ES-014](ES-014-admin-access-tunnel-and-operations.md) | Authentication, edge proxy, Cloudflare Tunnel, services, monitoring, and recovery | IS-008 v0.1.0 | Draft, retrospective conformance review required |

## Administration dependency model

```text
IS-008 approval
      |
      +--> ES-012 interface --------+
      |                             |
      +--> ES-013 GitHub workflow --+--> retrospective conformance and G5
      |                             |
      +--> ES-014 access/operations +
```

ES-012 through ES-014 document an existing baseline. Their presence does not
retroactively grant approval. Corrective security, availability, and
accessibility work may preserve the baseline; material expansion remains
blocked until the exact versions are approved.

## Staged dependency model

```text
0 contracts          ES-001
                         |
1 storage/bootstrap     ES-002 --> ES-003
                         |           |
                         +--------> ES-006

2 benchmark dev      ES-009 synthetic + development artifacts
                       ^  ^               |               |
                       |  |               v               v
                       |  +------------ ES-004          ES-007
                       |                  |               |
                       +-- ES-003/006 ----+---------------+

3 protected final    frozen ES-004/007 candidates --> ES-009 evaluator
                                                       |
4 aggregation                         ES-005 <----------+----------> ES-008
                                         |                           |
5 delivery                               +--------> ES-010 <----------+
                                                        |
                                                        v
                                                     ES-011
```

This is a staged workflow, not a simple package-level DAG. ES-009 starts its
contract and synthetic work after ES-001. ES-003 and ES-006 then provide
bootstrap records for development-only benchmark artifacts. ES-004 and ES-007
consume those development artifacts and submit one frozen candidate each to the
protected ES-009 evaluator. Final labels never flow back to candidate
development.

Near-duplicate calibration uses an explicit handshake: ES-003 first emits
candidate duplicate pairs using exact matches and a deliberately broad
deterministic retrieval rule; ES-009 returns development-only adjudicated pair
labels; ES-003 freezes the threshold; ES-009 then constructs validation and
final partitions using that frozen rule. No final partition is used to tune
ES-003.
