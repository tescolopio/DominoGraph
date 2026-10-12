# Architecture

```text
Dashboard → FastAPI → canonical models → relational metadata/evidence/relationships
                         ↑
          deterministic collectors → raw snapshots → validation → normalization
                         ↑
          metadata routing → replaceable AI interfaces → human review
```

The runnable pilot uses Python, Pydantic, FastAPI, and a relational store. SQLite
keeps local setup small; PostgreSQL is the intended operational metadata store.
Relationships are data, not invisible model-generated links. The browser dashboard
requires no build tool. No provider is mandatory.

Separate durable source records, immutable observations, documented transformations,
versioned rules, and assessments. A conclusion without resolvable source lineage is
an evidence gap. Preserve historical releases rather than overwriting revised data.

Parquet analytics, distributed scheduling, production human-review UI, and a React
dashboard are roadmap items. A dedicated graph database is deliberately deferred.
