# ADR-0001: Canonical, source-linked relational model

Status: accepted for the local pilot.

## Decision

Use a provider-neutral canonical model for ten economic objects. Generate JSON
schemas from executable Pydantic definitions. Keep directed relationships in the
relational store, alongside provenance, evidence, and versioned assessments.

## Rationale

Opaque scores and transient AI narratives cannot support falsification or historical
reproduction. Immutable observations and source-linked relationships make conclusions
inspectable. PostgreSQL can support the initial relationship model without the
operational complexity of a second graph database; SQLite enables a runnable local demo.

## Consequences

Evidence quality, causality, and legal redistribution still need human governance.
Schema validity is necessary but insufficient. Dedicated graph storage and analytical
Parquet pipelines may be added later without changing the canonical entity contracts.
