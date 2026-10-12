# Roadmap

## v0.1.0 — Traceable local pilot

- Ten canonical entities and JSON schemas; provenance and retained vintages.
- Synthetic Memory & Compute observations for DRAM, HBM, NAND, inventory, memory
  fab capex, hyperscaler capex, PC and smartphone shipments, datacenter investment,
  and semiconductor equipment spending.
- Deterministic validation and independent dimension scores.
- Evidence-backed dependency graph, hypothesis registry, and counter-evidence.
- Provider-neutral reasoning/research/review interfaces and metadata-based routing.
- Local API/dashboard and an explicitly illustrative scenario.

This milestone proves architecture, **not** economic validity. Production source
integration, empirical calibration, and operational governance remain outstanding.

## v0.2.0 — Empirical pilot

Validate data licenses and integrate real releases. Add vintage-aware adapters,
Parquet exports and DuckDB/Polars analytics, publication-date/as-of backtesting,
source quality checks, and review queues. Evaluate scheduling options (cron,
Prefect, or Dagster) based on operational needs. Retain PostgreSQL relationships
until traversal complexity justifies a dedicated graph database.

## Toward v1.0.0

Add authenticated human-review workflows, migrations, audit logs, role separation,
monitoring for stale/missing observations, and a React/Next.js graph dashboard.
Empirically test transmission lags and scenario parameters. Expand to Housing,
Consumers, Banking, Sovereign Debt, Energy, Labor, Corporate Credit, Global Trade,
and Currencies only after the first domino is independently validated.

## Initial GitHub issue backlog

The following are issue proposals, not claims that remote issues were created:

1. Review canonical Node schema.
2. Review Metric schema and contextual direction.
3. Review Observation schema and vintage uniqueness.
4. Review Relationship schema and causal promotion requirements.
5. Validate the Source Registry and data-license policy.
6. Integrate and validate the FRED collector with real releases.
7. Build an IMF collector.
8. Replace synthetic memory inputs with licensed pilot sources.
9. Extend provenance to historical model runs and input hashes.
10. Extend data validation and stale-release monitoring.
11. Evolve the basic graph viewer to a production dashboard.
12. Validate the hypothesis registry with domain reviewers.
13. Create a scheduled adversarial-review workflow.
14. Write and empirically test a scoring methodology RFC.
15. Establish contribution/review ownership and enforcement.

Software follows semantic versioning. Keep independent `schema_version`,
`methodology_version`, `scoring_version`, and `collector_version` identifiers:
changing one must not silently rewrite another's historical meaning.
