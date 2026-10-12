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

## Immutable relationship versions

To revise or review a relationship, append a new Relationship with a new `id` and
`supersedes` set to the previous version's ID. Retain its endpoints and provide the
complete replacement payload, including evidence and review status. A version may
have only one successor; cycles and changes to endpoints are rejected. A database
unique index also prevents concurrent writers from creating competing successors.

`Store.current_relationships()` and the graph/node APIs expose only chain tips,
including rejected tips for inspection. Scenarios exclude rejected and
needs-revision tips. Historical assessments and scenarios retain their original
IDs and continue tracing to the original versions. To reverse a rejection, append
another version superseding the rejected tip. When rejecting a previously causal
or coordination finding, classify the replacement as disputed; those promoted
classifications still require approval and matching supporting evidence.

This is a version lifecycle, not an authenticated approval system. Maintainer
review remains contributor policy until identity, authorization and audit records
are implemented. Legacy relationship payloads without `supersedes` remain valid;
initialization adds the successor index to existing pilot databases.
