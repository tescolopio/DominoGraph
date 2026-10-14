# Development roadmap

Planning baseline: 2026-10-12. This document describes intended work, not completed
capabilities or promised delivery dates. It is the detailed development roadmap;
the root [ROADMAP.md](../ROADMAP.md) provides the milestone overview.

## Objective and delivery approach

Build a useful economic research application incrementally. Every release should
give users a concrete workflow while strengthening the traceable dependency graph,
source provenance, evidence standards, and reproducibility underneath it.

Develop reliable data and inspection tools first, then add AI analysis against that
evidence. Observation, institutional statements, hypotheses, causal proposals, and
reviewed findings must remain distinct. Rising or falling values acquire meaning
only through documented context and methodology.

## Current foundation

- Local indicator explorer with World Bank GDP growth, inflation, and modeled
  unemployment for five supported economies; charts, search, saved indicators,
  source inspection, and historical download cutoffs.
- Retained raw snapshots, revisions, attribution, and atomic imports.
- World Bank ingestion history with sanitized outcomes and separate last-successful
  check/last-changed-snapshot timestamps; a seven-day manual workspace-check policy.
- Consistent file-backed SQLite backup and validated restore to a new destination,
  with preserved provenance/run history and tested additive legacy upgrades.
- Local Docker deployment with persistent SQLite storage; PostgreSQL is configurable.
- Separate synthetic Memory & Compute dependency pilot, evidence and hypothesis
  schemas, review states, and illustrative scenario calculations.
- Provider-neutral AI role and routing contracts.

The real indicators are not yet a validated causal graph. Download history is not
an archive of original publication history. Production AI execution, authenticated
review, scheduled ingestion, and empirically calibrated scenarios remain future work.

## Delivery stages

### 1. Expand the indicator explorer

**User value:** compare indicators, maintain watchlists, and see what changed.

- Integrate a small FRED/ALFRED series set for U.S. inflation, employment, interest
  rates, output, and housing; retain World Bank international context.
- Verify each series' definitions, license, frequency, units, seasonal adjustment,
  and available vintages before enabling it. Store credentials outside source control.
- Add comparison charts, persistent watchlists, data export, refresh status, and
  source freshness indicators. Label frequency conversions and transformations.
- Establish schema migrations, database backup/restore, and ingestion monitoring.

**AI:** generally unnecessary at runtime. Use code for collection and calculations.

**Completion criteria:** imports are repeatable; failed updates preserve existing
data; revisions remain inspectable; charts handle missing data and mixed frequencies
explicitly; a backup has been restored successfully. Never imply historical vintages
exist where a source does not supply them.

### 2. Build an evidence workspace

**User value:** inspect source documents beside charts and trace extracted claims
back to their original passages.

- Retain permitted source documents with hashes, retrieval dates, publication dates
  where known, attribution, and licensing constraints.
- Extract schema-constrained claims with page/section/passage references.
- Suggest entity matches without silently merging ambiguous entities.
- Add a staging area and review inbox for extracted claims and corrections.

**AI:** standardized extraction, with analytical escalation for ambiguous material.

**Completion criteria:** a manually checked evaluation set demonstrates acceptable
field accuracy and citation correctness; thresholds are documented before release;
unsupported claims remain unaccepted; corrections preserve their audit history.

### 3. Connect the first real dependency graph

**User value:** explore a bounded economic mechanism with evidence and alternatives.

- Start with a candidate chain such as interest rates → housing activity →
  construction employment. Each arrow begins as a proposal.
- Record mechanisms, context, possible lags, supporting evidence, counter-evidence,
  alternative explanations, and conditions that would weaken the hypothesis.
- Add reviewable relationship revisions and clear proposed/reviewed/rejected states.
- Implement authenticated approval and an audit trail before publishing AI-assisted
  causal findings. Validate the first chain before expanding across domains.

**AI:** deep reasoning proposes mechanisms; analytical review challenges them;
humans approve high-impact findings. Agreement between models is not validation.

**Completion criteria:** every accepted edge has inspectable evidence and review
history; rejected proposals cannot influence published assessments; correlation
is not promoted to causality without the required methodological support.

### 4. Add a grounded research assistant

**User value:** ask questions about retained data and evidence and receive cited,
reproducible answers.

- Retrieve canonical records and document passages through scoped tools.
- Delegate arithmetic and data transformations to deterministic analytical functions.
- Retain research inputs, tool results, citations, model metadata, and review outcomes.
- Escalate complex questions and surface missing or conflicting evidence.

**AI:** analytical models by default; deep reasoning for difficult synthesis.

**Completion criteria:** evaluated answers cite supporting evidence, reproduce
calculations, respect historical cutoffs, and disclose insufficient evidence.
Retrieved text cannot grant tool permissions or override system instructions.

### 5. Add conditional scenarios

**User value:** explore explicit assumptions and compare conditional outcomes.

- Version assumptions, transformations, parameter estimates, and calculation rules.
- Add sensitivity analysis and alternative mechanisms, including support and firebreaks.
- Evaluate against historical data available at the time and simple baselines.
- Keep illustrative scenarios distinct from validated forecasts.

**AI:** deep reasoning designs and critiques assumptions; code executes calculations.

**Completion criteria:** scenarios are reproducible, uncertainty and assumptions are
visible, historical evaluation avoids future-data leakage, and empirical claims have
documented validation. Do not use confidence scores as causal coefficients.

### 6. Mature operations and collaboration

**User value:** dependable updates and shared research/review workflows.

- Add scheduled jobs, bounded retries, idempotency, run history, and failure visibility.
- Extend authentication, permissions, review ownership, and audit logs for shared use.
- Test migrations, restore procedures, deployment upgrades, and source outages.
- Add per-task AI budgets, usage reporting, cancellation, and bounded escalation.

**AI:** selective automation under explicit execution and approval policies.

**Completion criteria:** jobs recover without duplicate records, access boundaries
are tested, failed refreshes retain usable data, and backups can restore the service.

Basic backup, migration, and monitoring work starts in Stage 1. Security and review
controls must ship before the capabilities that depend on them, not wait for Stage 6.

## AI involvement and execution authority

These tiers align with [orchestration](architecture/orchestration.md) and the existing
provider-neutral routing contracts. Concrete providers should be chosen using task
evaluations, cost, latency, and data-handling requirements rather than embedded in
the canonical schema.

| Tier | Work | Trigger | Authority |
| --- | --- | --- | --- |
| 1 — Deep reasoning | Ontology, competing mechanisms, major hypotheses, methodology, scenario assumptions | Milestone review or a substantial unresolved question | Propose; human review for high-impact changes |
| 2 — Analytical | Source comparison, evidence synthesis, contradictions, research briefs | User request or material new evidence | Cited drafts and review recommendations |
| 3 — Standardized extraction | Claims, metadata, classification, candidate entity matches | New or changed unstructured documents | Validated candidates in staging |
| 4 — Deterministic processing | APIs, parsing, normalization, validation, calculations, storage, traversal | Ingestion and analysis jobs | Execute tested, versioned rules |
| 5 — Deterministic monitoring | Staleness, revisions, missing data, failures, thresholds | Schedule or pipeline event | Record events and trigger scoped tasks |

Deep models are occasional specialists. Routine chart refreshes, arithmetic,
revision retention, and stale-data detection should not require language models.
Route work to the least expensive method that meets an established evaluation
threshold. Escalate validation failures or unresolved contradictions; do not rely
solely on a model's self-reported confidence.

For development itself, use deep reasoning for architecture and difficult reviews,
ordinary coding assistance for bounded features, and deterministic checks to enforce
contracts. Runtime AI capability must be evaluated separately from coding assistance.

### Example release workflow

1. Code downloads an employment release and preserves its raw snapshot.
2. Code validates units, retains the prior vintage, and calculates changes.
3. An extraction model proposes claims from accompanying commentary with citations.
4. An analytical model compares those claims with observations and hypotheses.
5. Deep reasoning is invoked only for a substantial unresolved mechanism or conflict.
6. A human reviews proposed changes to published causal relationships.

## Shared architecture and provenance

```text
Sources → Retained raw data → Validated observations → Charts and calculations
                   ↓                    ↓
             Document evidence → AI proposals → Review → Accepted graph
```

All collectors, tools, and agents must use the canonical contracts. Keep AI proposals
in staging rather than granting models unrestricted writes to accepted records.
Treat source documents as untrusted data, not instructions.

Retain source IDs and passages, input hashes, provider/model identity, prompt/template
versions, tool inputs and outputs, validation results, review disposition, runtime,
and cost for AI runs. Preserve supporting and contradicting evidence. Keep independent
schema, methodology, scoring, collector, and model-run versions.

Keep SQLite for the current local application. Move to PostgreSQL when concurrent
workers or shared reviews justify it, with a tested migration and restore path.
Introduce a dedicated graph database only when measured traversal requirements demand
it. Adopt a frontend framework or analytical storage layer for a demonstrated need.

## Recommended next three releases

| Release increment | Deliverable | Dependencies |
| --- | --- | --- |
| Research explorer (M1) | Small FRED integration, comparison charts, portable watchlists, freshness, backup/restore | Release baseline (M0); source definitions and licensing review; API credentials |
| Evidence and review workspace (M2) | Document retention, cited extraction, authenticated review inbox and audit history | Explorer data contracts (M1); document permissions; extraction evaluation set; AI run records |
| First real dependency chain (M3) | Focused graph, reviewed evidence, competing hypotheses and historical evaluation | Explorer observations (M1); review identity/audit controls and accepted evidence (M2) |

Assign version numbers and delivery estimates when each increment is scoped. Do not
make a framework rewrite, broad source coverage, or multiple autonomous agents a
prerequisite for delivering the next useful workflow.

The explorer is intended for regular research use, not a promise of daily-frequency
data or daily publication. A grounded assistant is a subsequent increment, not part
of the first real-chain release.

## Next-priority milestone requirements and definitions of done

These are planning requirements, not claims of completed work. M0 is release
preparation; M1-M3 are the next capability increments. Detailed estimates and
implementation choices require the scope decisions listed below.

| Milestone | Tracking issue | Initial owner | Status |
| --- | --- | --- | --- |
| M0 | [#2](https://github.com/tescolopio/DominoGraph/issues/2) | tescolopio | Technical baseline accepted; publication pending |
| M1 | [#3](https://github.com/tescolopio/DominoGraph/issues/3) | tescolopio | World Bank freshness/history and SQLite recovery implemented; PR review pending; remaining scope open |
| M2 | [#4](https://github.com/tescolopio/DominoGraph/issues/4) | tescolopio | Planned; publishing depends on M1 contracts and review policy |
| M3 | [#5](https://github.com/tescolopio/DominoGraph/issues/5) | tescolopio | Planned; depends on M1/M2 and an approved empirical protocol |

### Publication checkpoint and M1 gate

On 2026-10-13 the user authorized review, commit, and feature-branch PR publication
of the integrated M0 baseline and two scoped M1 increments. One coherent checkpoint
avoids artificially splitting their shared storage/tests/documentation changes.
This authorization does not include merging, tagging, or publishing a release.

The user explicitly chose to retain the original M1 scope. FRED/ALFRED scope and
licensing, source-neutral display, comparisons, portable watchlists, exports,
general versioned migrations, concurrency coverage, and performance acceptance
remain required, not deferred or silently marked complete. Complete those
requirements and the common release gate before starting M2 implementation.
Neither this checkpoint nor a passing PR closes #3; maintainer review and milestone
acceptance remain distinct from local technical validation.

### Common release gate

Each milestone is done only when:

- Every requirement has a tracked issue, an owner, and acceptance evidence. An
  unchecked gate blocks completion; deferring a requirement requires an explicit
  scope change rather than marking it complete.
- Canonical schema checks and the full existing test suite pass, with regression
  tests for affected contracts. Record exact commands, results, environment, and
  manual/browser checks in the implementation PR.
- Existing World Bank exploration, synthetic-pilot isolation, immutable records,
  historical lineage, and causal-promotion safeguards remain intact.
- Schema, collector, transformation, scoring, and application versions change
  independently when their contracts change. Historical records remain readable.
- Documentation, configuration examples, migration/upgrade instructions, and the
  changelog describe the delivered behavior and its limitations.
- A named maintainer reviews the evidence and records release acceptance. No
  milestone implies production hosting or empirical predictive validity.

### M0. Establish an accurate release baseline

**Outcome:** a new user can identify what exists and reproduce the local setup.

**Dependencies:** none. This does not require implementing new product features.

**Requirements**

1. Declare the current application version consistently in package metadata, API
   metadata, and release notes; retain independent schema and methodology versions.
2. Put current maturity beside the README vision: a real indicator explorer plus
   a separate synthetic dependency pilot, not a validated forecasting platform.
3. Present one general quick start with separate optional steps for synthetic
   seeding and real-data import. Include POSIX and Windows/PowerShell commands,
   credential configuration, persistence locations, and offline limitations.
4. Explain that illustrative pressure is implemented while the other economic
   dimensions lack independent measured inputs; null does not mean zero.
5. Add representative screenshots of both workflows and identify sample data.
6. Reconcile README and architecture guidance with this plan: React, Parquet,
   PostgreSQL adoption, and a dedicated graph database are need-driven decisions,
   not prerequisites for the next release.
7. Create the initial milestone issues with dependencies and acceptance checklists;
   label the older proposed backlog as historical rather than active tracking.

**Definition of done**

- [x] Package and API report the same chosen application version.
- [x] A clean source-checkout setup succeeds using the documented POSIX commands
      and separately using PowerShell; the documented Docker path also succeeds.
- [x] An unseeded installation opens the explorer without inventing observations;
      explicit import adds real indicators and explicit seeding enables the pilot.
- [x] README local links resolve, screenshots match the release, and current versus
      planned capabilities are distinguishable without reading the full roadmap.
- [x] M1-M3 have tracked scope, owners, prerequisites, and unresolved decisions.
- [ ] The common release gate is satisfied.

**Excluded:** fixing all historical backlog items, changing economic methodology,
or adding new sources.

#### M0 verification record

Verified on 2026-10-12 against the prepared 0.2.0 working copy. Application version
selection and issue ownership were approved by the user. tescolopio subsequently
accepted the verified M0 technical baseline and authorized scoped M1 work; that
acceptance alone did not authorize publication. At this verification checkpoint,
no commit, push, release tag, or GitHub release had been created. Later commit/PR
authorization is recorded above.

Windows validation used a clean source copy and fresh virtual environment with
Python 3.14.3. POSIX validation used a clean source copy and fresh virtual environment
in a Linux `python:3.12-slim` container (Python 3.12.15), not a native macOS test.

| Environment | Exact command | Result |
| --- | --- | --- |
| PowerShell | `python -m venv .venv` | Passed |
| PowerShell | `.\.venv\Scripts\python.exe -m pip install -e '.[test]'` | Passed; installed 0.2.0 |
| PowerShell | `.\.venv\Scripts\python.exe -m pip check` | Passed |
| PowerShell | `.\.venv\Scripts\python.exe -m scripts.export --check` | Passed |
| PowerShell | `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | Passed: 35 tests |
| PowerShell | `.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 18080` | Passed; HTTP explorer/health available, initially unseeded |
| PowerShell | `.\.venv\Scripts\python.exe -m scripts.sync_worldbank --country US` | Passed: three series, 165 observations |
| PowerShell | `.\.venv\Scripts\python.exe -m scripts.seed` | Passed: six synthetic nodes, ten metrics/observations, five relationships |
| POSIX/Linux | `python -m venv .venv` and `. .venv/bin/activate` | Passed |
| POSIX/Linux | `python -m pip install -e ".[test]"` | Passed; installed 0.2.0 |
| POSIX/Linux | `python -m pip check` | Passed |
| POSIX/Linux | `python -m scripts.export --check` | Passed |
| POSIX/Linux | `python -m unittest discover -s tests -v` | Passed: 35 tests |
| POSIX/Linux | `python -m uvicorn --version` | Passed: uvicorn 0.54.0 |
| POSIX/Linux container | `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000` | Passed; clean source/venv setup served HTTP explorer/health, initially unseeded, API reports 0.2.0 |
| POSIX/Linux | `python -m scripts.sync_worldbank --country US` | Passed: three series, 165 observations |
| POSIX/Linux | `python -m scripts.seed` | Passed: six synthetic nodes, ten metrics/observations, five relationships |
| Docker | `docker compose -p dominograph-m0-17cf03dc -f docker\docker-compose.yml build` | Passed |
| Docker | `docker compose -p dominograph-m0-17cf03dc -f docker\docker-compose.yml up -d --wait --wait-timeout 90` | Passed; healthy, initially unseeded, API reports 0.2.0 |
| Docker | `docker compose -p dominograph-m0-17cf03dc -f docker\docker-compose.yml exec -T api python -m scripts.sync_worldbank --country US` | Passed: three series, 165 observations |
| Docker | `docker compose -p dominograph-m0-17cf03dc -f docker\docker-compose.yml exec -T api python -m scripts.seed` | Passed: explicit synthetic seeding, separate from real import |
| Docker | `docker compose -p dominograph-m0-17cf03dc -f docker\docker-compose.yml down` then `docker compose -p dominograph-m0-17cf03dc -f docker\docker-compose.yml up -d --wait --wait-timeout 90` | Passed; named volume retained latest real observation IDs and six synthetic nodes |

Docker validation set `$env:DOMINOGRAPH_PORT = "18765"` before each Compose command
and used an isolated project to avoid touching existing workspaces. The Windows
server used port 18080 to avoid collisions with existing services. The separate
POSIX startup container listened on 0.0.0.0 internally to exercise HTTP through
Docker; only `127.0.0.1:18081` was published on the host. Standalone source-checkout
commands continue to bind to 127.0.0.1.

Browser checks passed for real-series rendering, search, saving, chart display,
pre-download historical cutoffs, and observation-to-metric/node/raw-snapshot/source
lineage. The synthetic dashboard displayed six nodes and four "Not assessed"
dimensions; pointer and keyboard scenario submission returned six illustrative
impacts using `bounded-path-v2`. README screenshots capture these real/synthetic
workflows separately.

A local Markdown file/anchor/image check passed for README and both roadmaps;
`git diff --check` passed. All four remote milestone issues are open and assigned
to tescolopio, with explicit prerequisites and acceptance checklists.

The installed Starlette/httpx test client emits a deprecation warning; it did not
fail either suite. PostgreSQL deployment, native macOS setup, empirical validity,
production hosting, and a dedicated security audit were not validated by M0.
M1 owns migrations/restore and the previously observed in-memory concurrency issue.

The M0 technical acceptance is recorded in #2. Publication through the normal review
process remains open. Do not close M0 or call 0.2.0 a published release until that
remaining gate is recorded; M1 changes require their own acceptance.

### M1. Deliver a dependable research explorer

**Outcome:** users can compare a bounded set of real indicators, retain their
research selections, inspect revisions, and recover the workspace.

**Dependencies:** M0; approved source licenses and a scoped series list.

The M0 technical baseline is accepted. The user approved freshness and persistent
run history as the first M1 increment, with a seven-day threshold for World Bank
workspace checks. This authorization does not select FRED series, a comparison
workflow, watchlist persistence, export behavior, or the remaining operational scope.

The scoped World Bank increment is technically implemented and verified, with PR
review pending. Its verification record below does not constitute
acceptance or completion of the full M1 milestone.

On 2026-10-13 the user approved file-backed SQLite CLI backup/restore into a new
destination with upgrade validation as the next scoped increment. It is technically
implemented with PR review pending; PostgreSQL automation, browser preference export,
and a general versioned migration framework remain outside this increment.

**Requirements**

1. Approve a small initial FRED/ALFRED series list covering the chosen inflation,
   employment, rates, output, and housing workflows. For each series record its
   publisher, definition, units, frequency, seasonal adjustment, licensing,
   revision behavior, and actual vintage availability.
2. Complete collection and normalization, including pagination/completeness checks,
   missing values, bounded timeouts/retries, explicit failures, and credential
   handling without credential-bearing logs or retained URLs.
3. Preserve raw inputs and revisions. Imports are atomic at a documented refresh
   boundary and idempotent on retries; historical selection must not substitute
   today's data for a requested historical vintage. Unknown release dates stay
   unknown; ALFRED availability is labeled separately from local retrieval.
4. Replace World Bank-specific display assumptions with metadata-driven source,
   units, periods, and change calculations. Percent, percentage points, index
   levels, and counts must not be conflated.
5. Support a bounded comparison workflow with explicit axis/unit labels and gaps.
   Mixed-frequency series retain their native dates by default; any resampling,
   rebasing, or percent-change calculation is opt-in, versioned, and explained.
6. Make watchlists durable across restarts and portable through backup or
   export/import. Document whether browser preferences require a separate export.
7. Export permitted observations with metric/source IDs, units, selected cutoff,
   vintage, retrieval time, and transformation lineage, directly or through a
   companion metadata file. Do not offer restricted content for redistribution.
8. Retain ingestion run outcomes, counts, start/end times, and sanitized errors.
   Show last successful check separately from last changed data and reference
   period. Define freshness using each source's expected cadence and grace period.
9. Establish explicit schema migrations and documented consistent backup/restore
   covering observations, sources, lineage, run history, and watchlists.
10. Add browser workflow tests and file-backed SQLite concurrency tests. Reproduce
    the observed in-memory parallel-read failure and either support that mode
    safely or explicitly restrict it; do not infer deployment failure from it.

**Definition of done**

- [ ] Every enabled series has an approved source/metadata checklist and a
      credentialed live smoke-test result; deterministic tests use retained fixtures.
- [ ] Fixtures cover pagination, missing/malformed values, revisions, withdrawal,
      unchanged checks, source outages, and retries. Failed imports leave the
      prior accepted dataset unchanged; retries do not duplicate observations.
- [ ] Historical-cutoff tests select the expected vintage and exclude later
      information, including explicit handling of unavailable historical data.
- [ ] Browser tests cover selecting, comparing, saving, reopening, exporting,
      historical cutoffs, and tracing an observation to its source/raw input.
- [ ] At least a percentage series, an index/count series, and a mixed-frequency
      comparison render correct units and dates without implicit conversions.
- [ ] A successful unchanged refresh advances last-checked status without
      fabricating a changed vintage; failed/stale states are visible after restart.
- [ ] A backup is restored into a clean workspace and reproduces observation IDs,
      source references, provenance, and watchlists; upgrade testing preserves
      existing synthetic and World Bank records.
- [ ] A declared benchmark dataset, size, environment, and response-time budget
      are approved before performance testing, and measured results meet that budget.
- [ ] The common release gate is satisfied.

**Excluded:** broad source coverage, runtime AI, automatic economic risk scores,
public hosting, and framework/database rewrites without measured justification.

#### M1 freshness/history verification record

Verified on 2026-10-12. This increment retains World Bank refresh attempts across
browser and CLI workflows, including start/end times, outcomes, accepted addition
counts, and sanitized failures. Successful data writes and run completion share
one transaction. Unchanged checks advance last-successful-check without inventing
new observations or snapshots. Failed attempts leave accepted data and the previous
successful-check time intact.

The approved seven-day policy measures elapsed time since a successful country-wide
check, not the source's publication cadence or the age/validity of annual values.
Current check history remains separate from historical observation cutoffs.
Existing databases gain the operational table without invented legacy checks;
unfinished attempts remain explicitly incomplete.

| Environment | Command | Result |
| --- | --- | --- |
| Windows, Python 3.14.3 | `.\.venv-review\Scripts\python.exe -m scripts.export --check` | Passed on final working copy |
| Windows, Python 3.14.3 | `.\.venv-review\Scripts\python.exe -m unittest discover -s tests -v` | Passed: all 48 tests on final working copy |
| Windows | `node --check frontend\explorer.js` | Passed on final working copy |
| Windows | `git diff --check` | Passed |
| Linux, Python 3.12.15 | `python -m scripts.export --check` | Passed before the final country-summary/UI refinements |
| Linux, Python 3.12.15 | `python -m unittest discover -s tests -v` | Passed: all 48 tests before the final country-summary/UI refinements |
| Live World Bank, Windows | `.\.venv-review\Scripts\python.exe -m scripts.sync_worldbank --country US` | Passed: three series checked, zero observations/snapshots added, persisted successful run |

The live CLI command used an isolated file-backed validation database through
`DATABASE_URL`, not the user's normal workspace. Initial live import retained
165 U.S. observations and three snapshots. Subsequent checks confirmed separate
successful-check and changed-snapshot timestamps.

Regression coverage includes the exact seven-day boundary (including adjacent
microseconds), pagination and successful checks outside the recent-history window,
sanitized source/storage/configuration failures, transactional rollback, terminal
run protection, additive upgrades, file-backed restart persistence, incomplete
attempts, and historical-cutoff independence. The existing Starlette/httpx
deprecation warning remains visible and did not fail validation.

Browser checks passed for fresh/stale/never-checked states, failed first import
without retained indicators, unchanged refreshes, economy-specific status headings,
and current checks alongside a pre-download cutoff with zero observations.
Observation evidence still exposes full snapshot/source provenance; the synthetic
pilot still loads separately. An actual server stop/restart preserved the exact
failed German run and the prior U.S. successful run; a later live CLI success
became the newest U.S. check. Empty economies no longer inherit a previous
economy's "Saved data loaded" status.

Unchanged browser checks used retained live U.S. responses; failure states used
explicit fault injection. The stale Canadian check was a test-only fixture, not
evidence of a real Canadian download. The updated README screenshot uses real
U.S. annual data and the successful live CLI check, with injected failure history
collapsed. Temporary validation servers and databases were removed after checks.

At that verification checkpoint the increment was not committed, pushed, or
published. Full M1 acceptance,
source-neutral freshness policies, scheduling/recovery, FRED/ALFRED, comparisons,
portable watchlists, exports, migrations/restore, performance budgets, and the
previously observed in-memory concurrency issue remain open.

#### M1 SQLite recovery verification record

Verified on 2026-10-13 in the then-unpublished working copy. The CLI exposes
`scripts.workspace backup --output PATH` for the configured file-backed SQLite
workspace and `scripts.workspace restore --backup PATH --output PATH` for a
validated new destination. The SQLite online backup API includes committed WAL
changes and excludes in-flight writes. No live database or existing destination is
replaced; activation requires an explicit configuration change and service restart.

Validation covers database integrity/foreign keys, recognized layouts, canonical
models and semantics, exact provenance references, and run states/chronology.
A retained-content SHA-256 checksum must match before and after additive restore
initialization, including exact stored JSON rather than just record counts.
Malformed/foreign/future backups and unsupported URLs fail explicitly. No legacy
check history is invented, interrupted attempts remain incomplete, and
canonical/schema/scoring versions are unchanged.

| Environment | Command | Result |
| --- | --- | --- |
| Windows, Python 3.14.3 | `.\.venv-review\Scripts\python.exe -m unittest discover -s tests -p test_backup.py -v` | Initial 13-test recovery suite passed; subsequent coverage expanded to 18 tests |
| Windows, Python 3.14.3 | `.\.venv-review\Scripts\python.exe -m unittest discover -s tests -v` | Passed: all 66 tests, including 18 recovery regressions |
| Windows | `.\.venv-review\Scripts\python.exe -m scripts.export --check` | Passed |
| Windows | `python -m pip --python .\.venv-review\Scripts\python.exe check` | Passed; no broken requirements |
| Windows | `git diff --check` and `git check-ignore data\backups\workspace.db` | Passed; recommended backup location is ignored |
| Docker | `docker build -f docker\Dockerfile -t dominograph-recovery-17cf03dc .` | Passed; current commands packaged in the non-root runtime image |
| Linux, Python 3.12.15 | `python -m unittest discover -s tests -v` | Passed: all 66 tests in the current image with tests mounted read-only |
| Linux, Python 3.12.15 | `python -m scripts.export --check` and `python -m pip check` | Passed |

The runtime image intentionally excludes test dependencies. After an explicit
missing-`httpx` check, the ephemeral Linux validation container installed the
existing pinned test dependency with
`python -m pip install --no-cache-dir httpx==0.28.1`; no dependency manifest changed.
The existing Starlette/httpx deprecation warning remains visible and non-failing.

Recovery regressions verify exact canonical payloads/IDs, source/raw lineage,
historical cutoff selection, successful/failed/unfinished run history, repeated
restored startup, immutable-record guards, single relationship-successor
enforcement, repository-relative source resolution, destination aliases/sidecars,
concurrent destination creation, timeout/publish/upgrade failure cleanup,
incompatible layouts/versions, malformed chronology, and sanitized CLI failures.
A same-count payload mutation during initialization is rejected by checksum.

An isolated, non-root Docker smoke test (UID 10001) ran the packaged commands:
`python -m scripts.seed`, `python -m scripts.sync_worldbank --country US`,
`python -m scripts.workspace backup --output /app/data/backups/workspace.db`, and
`python -m scripts.workspace restore --backup /app/data/backups/workspace.db --output /app/data/restored.db`.
The live import retained 165 World Bank observations and three snapshots; the
combined synthetic/real backup contained 175 observations and one successful run.
Backup/restore content checksums matched. Two actual uvicorn startups using the
restored file served `/health`, `/`, `/pilot`, and `/api/indicators`, retaining
every canonical record, exact observation provenance, and the live import run ID.
Containers used `--rm`; no user's database or Compose volume was touched.

See the [README recovery procedure](../README.md#sqlite-backup-and-restore) for
PowerShell/POSIX/Docker commands, explicit activation/rollback, filesystem
requirements, and handling backups as private data. Browser-local saved indicators,
credentials/configuration, PostgreSQL recovery automation, scheduled backups,
power-loss/filesystem durability guarantees, and general versioned migrations are
not covered. Full M1 acceptance and the portable-watchlist/restore milestone gate
remain open. No commit, push, tag, or release had been created at that verification
checkpoint; the subsequent commit/PR authorization is recorded above.

### M2. Establish an evidence and accountable review workspace

**Outcome:** a reviewer can inspect a claim beside its source passage and accept,
reject, or request correction with attributable, retained history.

**Dependencies:** M1 data contracts; document permissions; approved review policy.
Document retention and evaluation design may proceed in parallel with M1, but
accepted publishing requires the complete review gate.

**Requirements**

1. Retain permitted document versions with publisher, license, content hash,
   retrieval/publication dates, and stable page/section/passage references.
2. Keep extracted claims, entity-match suggestions, and proposed relationships
   in staging. Ambiguous matches require review; missing citations and unsupported
   claims cannot silently enter accepted records.
3. Provide an inbox with source context, supporting and contradicting evidence,
   evidence gaps, alternatives, and approve/reject/needs-revision actions.
4. Establish authenticated reviewer identity and server-enforced permissions.
   Automated extraction cannot approve itself; high-impact findings require the
   review ownership and role separation defined in the approved policy.
5. Record append-only review events containing actor, timestamp, decision,
   rationale, exact record version, and predecessor. Reuse relationship
   supersession; define a compatible correction lifecycle for other claim types.
6. Retain AI-run input/passage IDs and hashes, provider/model and prompt versions,
   validated outputs, tool calls/results, review disposition, runtime, and cost.
   Canonical economic objects remain provider-neutral; model writes are scoped.
7. Evaluate extraction on a manually annotated, held-out set with an agreed error
   taxonomy, representative document formats, and per-field acceptance targets.
   Fix the dataset and thresholds before release evaluation, not after seeing results.
8. Enforce document-data/tool boundaries and permissions before shared use. A
   loopback-only deployment remains the default; authentication does not imply
   readiness for public hosting.

**Definition of done**

- [ ] Each accepted claim resolves to its exact retained source version and
      passage; unresolved citations and unsupported claims are blocked from acceptance.
- [ ] Held-out results meet the pre-approved extraction precision/recall and
      citation-correctness targets, with sample size, failure cases, and limitations
      reported. Syntax validation alone is not evaluation.
- [ ] Every acceptance/rejection/correction has an authenticated actor, timestamp,
      rationale, and exact version reference; earlier decisions remain inspectable.
- [ ] API tests prove unauthenticated/unauthorized callers cannot approve, change
      roles, or bypass promotion gates; model outputs cannot self-approve.
- [ ] Browser tests cover source inspection, contradictory evidence, rejection,
      correction, and subsequent acceptance without rewriting history.
- [ ] Relationship revisions use the existing single-successor lifecycle;
      conflicting decisions fail explicitly and require a refreshed review.
- [ ] Rejected/needs-revision proposals cannot enter new accepted assessments or
      scenarios; retained historical outputs still trace to their original inputs.
- [ ] AI runs are inspectable, bounded, and contain no credentials; adversarial
      source text cannot acquire approval or tool authority.
- [ ] The common release gate is satisfied.

**Excluded:** autonomous causal publishing, multiple-agent orchestration, a
general-purpose assistant, and unrestricted document ingestion.

### M3. Validate the first real dependency-chain workflow

**Outcome:** users can inspect one bounded real economic mechanism, its evidence,
competing explanations, review history, and empirical limitations.

**Dependencies:** M1 observations/vintages; M2 accepted evidence and review controls.

**Requirements**

1. Approve one chain, geography, time range, and intended research question before
   implementation. Rates, housing activity, and construction employment are a
   candidate, not a committed replacement for Memory & Compute.
2. Map each node to approved metrics and each proposed edge to a mechanism,
   expected lag range, context, assumptions, supporting/counter-evidence,
   alternative explanations, search gaps, and falsification criteria.
3. Keep association, hypothesized transmission, and causally supported findings
   distinct. Review approval alone is not identification; stronger classifications
   require the existing matching-evidence gates and documented methodological support.
4. Predefine the evaluation window, actual available vintages, confounders,
   baseline/alternative mechanisms, sensitivity checks, and decision rules.
   Separate exploratory analysis from held-out evaluation.
5. Reproduce analysis from retained observations and versioned calculations.
   If original historical vintages are absent, restrict the claim or label the
   analysis retrospective; do not present it as information available at the time.
6. Expose a graph/evidence workflow with proposed/reviewed/rejected states,
   reviewer rationale, evidence inspection, and version history. Keep synthetic
   data visibly separate from empirical inputs and findings.
7. Define reassessment triggers for source revisions, contradictory evidence, and
   failed falsification tests. Reassessment creates new versions rather than
   rewriting prior findings.
8. Leave unsupported dimension scores and transmission coefficients unassigned.
   Do not reuse synthetic coefficients or infer causal effects from confidence.

**Definition of done**

- [ ] The scope and evaluation protocol are approved before the final evaluation;
      every published edge has the required evidence, classification, and review history.
- [ ] A domain reviewer records the conclusion for each edge, including at least
      one investigated competing explanation and explicit remaining evidence gaps.
- [ ] A reproducible evaluation bundle contains input/vintage IDs, calculations,
      protocol/version, baseline and sensitivity results, and falsification outcomes.
- [ ] Tests prove later observations or graph revisions do not change retained
      historical lineage, and current rejected edges do not enter new outputs.
- [ ] The user can trace each published finding through evidence to its source
      and inspect revisions, counter-evidence, and reviewer decisions.
- [ ] Empirical results meet the predeclared claim-specific criteria before any
      validated causal label is used. Failed or inconclusive tests are published as
      such; a transparent workflow may ship without claiming a validated causal chain.
- [ ] A recorded reassessment exercise handles a revised source or rejected edge
      without erasing the original finding.
- [ ] The common release gate is satisfied.

**Excluded:** expansion across economic domains, validated forecasting claims,
calibrated real-world scenarios, and the grounded assistant. These require their
own evaluations after the chain workflow is demonstrated.

### Decisions required before implementation scope is locked

- M0: application baseline 0.2.0, initial owner tescolopio, and technical acceptance
  are recorded; publication remains outstanding.
- M1: approve exact FRED/ALFRED series and licenses, comparison/export behavior,
  watchlist persistence, freshness rules, and the performance benchmark/budget.
- M2: approve supported document formats, evaluation dataset/thresholds, reviewer
  roles, authentication approach, and high-impact approval policy.
- M3: choose the empirical chain and domain reviewer; approve its scope,
  identification/evaluation protocol, and criteria for each intended claim.

These decisions are not delegated to AI output. Record them in tracked issues
before the affected implementation begins; no delivery dates are implied here.

## Maintaining this plan

For each implementation PR, identify the user workflow, data/model changes, tests,
operational impact, and applicable completion criteria. Update this roadmap when
capabilities are delivered or dependencies change; use the changelog for completed
work. Create tracked issues separately rather than treating this plan as an existing
remote backlog.

## Source integration references

- [FRED/ALFRED API](https://fred.stlouisfed.org/docs/api/fred/)
- [FRED API key requirements](https://fred.stlouisfed.org/docs/api/api_key.html)
- [FRED vintage dates](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html)
- [Canonical data model](architecture/data-model.md)
- [Provider-neutral AI](architecture/ai-architecture.md)
