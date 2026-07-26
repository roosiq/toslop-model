# Observatory Contract Reference

Generated from the versioned ES-001 registries. Approved claim language
remains in the intent and execution specifications; this file does not
replace it.

Score registry: `1.0.0`

Warning registry: `1.0.0`

## Scores

| ID | Name | Direction | Unit | Required components |
| --- | --- | --- | --- | --- |
| S1 | External Exploration | `higher_means_broader_exploration` | `bounded_exploration_0_to_100` | `source_breadth`, `public_knowledge_use`, `citation_depth` |
| S2 | Source Concentration | `higher_means_more_concentration` | `bounded_concentration_0_to_100` | `domain_concentration`, `publisher_concentration`, `ownership_concentration` |
| S3 | Language Homogenization | `higher_means_more_convergence` | `bounded_convergence_0_to_100` | `lexical_convergence`, `syntactic_convergence`, `rhetorical_convergence`, `semantic_convergence` |
| S4 | Perspective Diversity | `higher_means_more_perspective_diversity` | `bounded_perspective_breadth_0_to_100` | `frame_breadth`, `argument_breadth`, `cause_breadth`, `action_breadth` |
| S5 | Model-Language Diffusion | `higher_means_more_pattern_diffusion` | `bounded_pattern_diffusion_0_to_100` | `pattern_prevalence`, `cross_domain_diffusion`, `temporal_lead_lag` |
| S6 | Human Knowledge Contribution | `higher_means_more_public_contribution` | `bounded_contribution_0_to_100` | `qa_contribution`, `explanatory_contribution`, `maintenance_contribution` |
| S7 | Employer AI Compulsion | `higher_means_more_compulsion` | `bounded_pressure_0_to_100` | `primary_level_pressure`, `required_prevalence`, `monitoring_or_enforcement_prevalence` |
| S8 | Novel Information Density | `higher_means_more_novel_information` | `bounded_novelty_density_0_to_100` | `claim_novelty`, `perspective_novelty`, `source_novelty` |

Public composites are prohibited. Every score retains its own
construct, evidence class, release, lineage, components, and warnings.

## Evidence Classes

| ID | Meaning | Separate study required |
| --- | --- | --- |
| `descriptive` | A documented measurement changed in the observed sample. | No |
| `exposure_association` | A predeclared exposure measure is associated with the outcome after stated controls. | Yes |
| `causal_estimate` | A separately reviewed design estimates an intervention effect under explicit assumptions. | Yes |

## Warning Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `EXPERIMENTAL` | `info` | This scorer or series has not completed all validation and production gates. |
| `LOW_SAMPLE_SIZE` | `error` | The eligible observation count is below the approved release threshold. |
| `LOW_EFFECTIVE_SAMPLE_SIZE` | `error` | Clustering or weighting reduces the effective sample below the approved threshold. |
| `BASELINE_INCOMPLETE` | `error` | The approved historical baseline does not have sufficient eligible coverage. |
| `SOURCE_OUTAGE` | `error` | One or more required sources did not complete collection for this period. |
| `SOURCE_MIX_SHIFT` | `warning` | The source-family composition changed beyond the approved comparison tolerance. |
| `COVERAGE_SHIFT` | `warning` | Entity, topic, genre, occupation, jurisdiction, or field coverage changed beyond tolerance. |
| `TOPIC_OR_GENRE_CONFOUNDER` | `warning` | The requested comparison has residual topic, event, template, or genre confounding. |
| `BENCHMARK_REGRESSION` | `error` | A required benchmark or safety slice regressed below its frozen threshold. |
| `EXTRACTOR_DRIFT` | `error` | Feature or label extraction changed beyond the approved drift tolerance. |
| `LINEAGE_INCOMPLETE` | `error` | One or more inputs, transformations, or versions cannot be reconstructed. |
| `LICENSE_RESTRICTED` | `error` | Source rights or retention state prohibit this calculation or publication. |
| `CONFIDENCE_UNAVAILABLE` | `warning` | The approved confidence calculation could not be completed. |
| `RELATIVE_CHANGE_UNDEFINED` | `info` | Relative change is null because the approved baseline value is zero. |
| `VERSION_BREAK` | `warning` | A major scorer version starts a separate series unless an approved bridge permits comparison. |
| `SUPPRESSED` | `error` | The result is intentionally withheld because one or more required gates failed. |

## Compatibility

- Patch versions may correct documentation without changing semantics.
- Minor versions may add backward-compatible fields.
- Major scorer versions start separate series.
- An approved bridge may explain comparison, but contract fixtures never
  permit an automatic major-version join.
