# Changelog

## Unreleased — M1 source checks and SQLite recovery

- Add consistent file-backed SQLite backup and validated restore CLI commands.
- Include committed WAL changes; preserve raw payloads, provenance, and run history.
- Restore only to new destinations, with atomic non-replacing publication.
- Validate integrity, schemas, references, run chronology, and retained-content checksums.
- Reject weakened SQLite table definitions before backup/restore publication, while
  retaining the explicitly supported legacy table/index/trigger differences.
- Remove an orphaned duplicate stylesheet block without changing responsive breakpoints.
- Test additive legacy upgrades without canonical rewrites or invented refresh history.
- Document PowerShell/POSIX/Docker recovery, rollback, and excluded browser preferences.
- Ignore the recommended backup directory and sanitize nonzero CLI failure diagnostics.
- Keep PostgreSQL automation and general versioned migration management out of this increment.

- Persist country-scoped World Bank attempts for browser and CLI refreshes.
- Commit accepted data and successful run completion in one transaction.
- Retain sanitized failures, timestamps, validated-series counts, and accepted additions.
- Separate last successful check from the last changed response snapshot.
- Apply the approved seven-day workspace-check policy, without implying publication freshness.
- Show current economy check status and recent attempts even before a successful import.
- Expose bounded/paginated run history and preserve it across application restarts.
- Add the operational table without rewriting canonical entities or inventing legacy checks.
- Report CLI failures with nonzero exit status and sanitized diagnostics.
- Cover exact freshness boundaries, atomic rollback, unchanged checks, restart/upgrade behavior,
  pagination, unfinished attempts, and secret-free errors.

## 0.2.0 — Local research baseline (release preparation)

Application/package version: `0.2.0`. Schema version remains `1.0.0`;
scoring remains `pilot-weighted-v1` and new scenarios use `bounded-path-v2`.
This entry documents the prepared baseline, not a published GitHub release or tag.

### Release alignment

- Align package and API versions and add a version-consistency regression test.
- Separate general setup, real indicator import, and optional synthetic seeding.
- Document PowerShell/POSIX setup, persistence, credentials, and offline limitations.
- Clarify partial scoring coverage and defer architecture changes until justified.
- Add workflow screenshots and owned milestone tracking.

### Local indicator explorer

- Add an annual indicator library with search, saved indicators, charts and source inspection.
- Add a fixed-source World Bank connector for five economies and three macroeconomic series.
- Retain complete download snapshots and revisions; support historical availability cutoffs.
- Keep real indicators separate from the synthetic dependency pilot.
- Allow unknown publication dates and metrics without scoring rules.
- Add atomic refresh, same-origin request checks, local host validation and importer tests.
- Add Docker health checks, persistent storage and a configurable localhost port (8765 by default).

### Pilot review corrections

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
