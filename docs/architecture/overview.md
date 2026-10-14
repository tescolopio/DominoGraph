# Architecture

```text
Dashboard → FastAPI → canonical models → relational metadata/evidence/relationships
                         ↑
          deterministic collectors → raw snapshots → validation → normalization
                         ↑
          metadata routing → replaceable AI interfaces → human review
```

The runnable local application uses Python, Pydantic, FastAPI, and a relational
store. SQLite is the default for a single workspace. PostgreSQL is configurable;
adopt it when concurrent workers or shared review justify a tested migration.
Relationships are data, not invisible model-generated links. The browser dashboard
requires no build tool. No provider is mandatory.

Separate durable source records, immutable observations, documented transformations,
versioned rules, and assessments. A conclusion without resolvable source lineage is
an evidence gap. Preserve historical releases rather than overwriting revised data.

Operational ingestion attempts live separately in `ingestion_runs`. An attempt is
persisted before collection; accepted data and a successful terminal outcome commit
in one transaction. Known collection/validation/storage failures retain a sanitized
terminal outcome without accepting partial data. Unfinished attempts remain visible
as incomplete rather than being assumed successful after restart.

Current World Bank check status is economy-scoped: a seven-day manual-check policy
uses the last successful completion, while the latest retained raw-response change
determines the last changed snapshot. Neither timestamp is an original publication
date or a substitute for historical observation availability. Existing canonical
payloads, schema/scoring versions, and provenance are unchanged by this operational
table.

File-backed SQLite recovery uses the native online backup API, not live file
copying. Backup and restore validate a standalone temporary snapshot, including
canonical semantics, exact stored provenance, and operational run chronology.
Restore applies the existing additive initialization only to that temporary copy;
a retained-content checksum must remain identical before publication. Publication
uses a same-filesystem hard link to atomically refuse existing destinations, even
when another writer creates one during the operation. Restore never swaps the
running application's database; activation is an explicit stopped-service
configuration change. Browser-local preferences are outside this database boundary.
Versioned migration management and PostgreSQL recovery automation remain future work.

Authenticated human review and ingestion operations are planned capabilities.
Parquet analytics, distributed scheduling, and React are possible responses to
demonstrated needs, not prerequisites for the next release. A dedicated graph
database is deferred until measured traversal requirements justify it.
