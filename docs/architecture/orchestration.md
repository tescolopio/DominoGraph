# Orchestration

Route by task metadata and capability, not vendor name:

| Tier | Work | Execution |
| --- | --- | --- |
| 1 | Ontology, causality, hypotheses, scenarios, scoring methodology | Deep reasoning and human review |
| 2 | Synthesis, counter-evidence, policy interpretation, source comparison | Analytical provider |
| 3 | Document parsing, metadata, entities, schema mapping | Extraction provider |
| 4 | APIs, CSV, normalization, validation, calculations | Deterministic pipeline |
| 5 | Releases, thresholds, stale/missing observations | Deterministic monitoring |

The pilot exposes routing/provider contracts, not a production queue or scheduler.
Human review is required for high-impact scoring, ontology changes, causal findings,
and major hypotheses. In the pilot these states are data and contributor policy;
authenticated approval workflows and scheduled adversarial review remain future work.
