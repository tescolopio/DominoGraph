# Canonical data model

The ten first-class objects are Node, Metric, Source, Observation, Relationship,
Intervention, Hypothesis, Evidence, Scenario, and Assessment. Pydantic models are
the executable definition; generated JSON schemas live in `schemas/`.

- **Node:** economic component, domain, geography, description.
- **Metric:** measurable definition, unit, frequency, and node reference.
- **Source:** publisher, URL, tier, methodology, cadence, revisions, licensing,
  redistribution status, and limitations.
- **Observation:** metric measurement with source URL, retrieval/publication and
  observation dates, vintage, collector/transformation versions, and validation.
- **Relationship:** directed endpoints, mechanism, lag, confidence, evidence state,
  supporting/counter-evidence, alternatives, and review status.
- **Intervention:** deliberate institutional action, distinct from a measured outcome.
- **Hypothesis:** claim, supporting/contradicting evidence, required datasets,
  falsification criteria, confidence/status, nodes, policies, and statements.
- **Evidence:** classified claim linked to sources and, where appropriate, observations.
- **Scenario:** explicit assumptions and conditional impacts, never a proven forecast.
- **Assessment:** independently scored dimensions with versioned methodology and
  resolvable observation/metric/relationship/evidence lineage.

Institutional statements are stored separately with organization/person/document,
date, exact statement/context, prediction, advocacy, policy proposal, implemented
policy, subsequent action, economic outcome, source, and confidence. A quotation
does not establish intent beyond its wording; outcome resemblance is not coordination.

Referential integrity is checked on ingestion. Schema validation alone cannot prove
scientific validity, licensing compliance, or causal identification. Human review is
still required. Empty counter-evidence lists mean incomplete investigation, not that
contradictions cannot exist.
