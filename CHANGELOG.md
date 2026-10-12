# Changelog

## Unreleased — Local indicator explorer

- Add an annual indicator library with search, saved indicators, charts and source inspection.
- Add a fixed-source World Bank connector for five economies and three macroeconomic series.
- Retain complete download snapshots and revisions; support historical availability cutoffs.
- Keep real indicators separate from the synthetic dependency pilot.
- Allow unknown publication dates and metrics without scoring rules.
- Add atomic refresh, same-origin request checks, local host validation and importer tests.
- Add Docker health checks, persistent storage and a configurable localhost port (8765 by default).

## Unreleased — Pilot review corrections

- Keep historical provenance stable by following retained forward references only.
- Preserve revision predecessors on ingestion retry and exclude later/different-source predecessors.
- Apply causal and coordination promotion gates to hypotheses as well as relationships.
- Sum scenario contributions before clamping; preserve v1 records and emit bounded-path-v2.
- Add immutable relationship supersession, single-successor database enforcement,
  and current-version selection for graph inspection and scenario execution.
- Add regression coverage for ingestion history, promotion, path ordering and review lifecycle.

## 0.1.0 — Initial pilot

- Canonical economic entities, explicit evidence states, and retained provenance.
- Deterministic synthetic Memory & Compute pipeline, dimension assessments,
  hypothesis/counter-evidence registry, and illustrative scenarios.
- Provider-neutral orchestration interfaces and API/dashboard source inspection.
- Contribution, security, licensing, and methodology guidance.
