# Roadmap

See the [development roadmap](docs/development-roadmap.md) for the current staged
implementation plan, AI involvement tiers, completion criteria, and next three
release increments. Its [next-priority milestone requirements and definitions of done](docs/development-roadmap.md#next-priority-milestone-requirements-and-definitions-of-done)
define the release baseline, explorer, evidence/review workspace, and first real
dependency-chain gates. That plan supersedes the sequencing assumptions below;
the version milestones and initial backlog here provide historical context.

## Active milestone tracking

The prepared application baseline is **0.2.0**: a local indicator explorer plus a
separate synthetic dependency pilot. This is not the empirical-pilot milestone
proposed in the historical plan below, and no release tag is implied.

| Milestone | Tracking issue | Initial owner | Prerequisites |
| --- | --- | --- | --- |
| M0: Release baseline | [#2](https://github.com/tescolopio/DominoGraph/issues/2) | tescolopio | Technical baseline accepted; publication remains open |
| M1: Research explorer | [#3](https://github.com/tescolopio/DominoGraph/issues/3) | tescolopio | World Bank freshness/history and SQLite recovery implemented; PR review pending; remaining scope open |
| M2: Evidence and review workspace | [#4](https://github.com/tescolopio/DominoGraph/issues/4) | tescolopio | M1 data contracts; document permissions and review policy |
| M3: Real dependency-chain workflow | [#5](https://github.com/tescolopio/DominoGraph/issues/5) | tescolopio | M1 observations; M2 evidence/review controls; approved empirical protocol |

M0 technical preparation is recorded in the
[development roadmap](docs/development-roadmap.md#m0-verification-record).
tescolopio accepted the verified M0 technical baseline on 2026-10-12 and authorized
scoped M1 implementation; no commit, push, tag, or release was authorized by that
acceptance. The first M1 increment adds World Bank check freshness and persistent
ingestion history; its [verification record](docs/development-roadmap.md#m1-freshnesshistory-verification-record)
documents validation before publication. The next approved increment
adds [SQLite backup/restore and upgrade validation](docs/development-roadmap.md#m1-sqlite-recovery-verification-record).
M1 as a whole and M2-M3 remain open; their issues retain unresolved
decisions and no delivery-date commitments.

On 2026-10-13 the user authorized a reviewed feature-branch commit and PR for this
combined checkpoint, not a release or milestone completion. The original M1
scope remains unchanged: FRED/ALFRED, source-neutral display, comparisons, portable
watchlists, exports, general migrations, concurrency coverage, and performance
acceptance must be completed before M2 implementation begins.

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

## Historical v0.2.0 proposal — Empirical pilot

Validate data licenses and integrate real releases. Add vintage-aware adapters,
Parquet exports and DuckDB/Polars analytics, publication-date/as-of backtesting,
source quality checks, and review queues. Evaluate scheduling options (cron,
Prefect, or Dagster) based on operational needs. Retain PostgreSQL relationships
until traversal complexity justifies a dedicated graph database.

## Historical direction toward v1.0.0

Add authenticated human-review workflows, migrations, audit logs, role separation,
monitoring for stale/missing observations, and a React/Next.js graph dashboard.
Empirically test transmission lags and scenario parameters. Expand to Housing,
Consumers, Banking, Sovereign Debt, Energy, Labor, Corporate Credit, Global Trade,
and Currencies only after the first domino is independently validated.

## Historical initial issue proposals

The following are historical issue proposals, not the active tracked backlog
and not claims that remote issues were created for each item. Use M0-M3 above for
current priorities and their acceptance gates:

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
