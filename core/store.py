"""Append-only canonical records and transactionally completed ingestion runs."""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (JSON, CheckConstraint, Column, ForeignKeyConstraint, Index,
                        Integer, MetaData, String, Table, create_engine, event, insert,
                        select, update)
from sqlalchemy.engine import Connection
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import StaticPool

from schemas.models import MODELS, Canonical

ROOT = Path(__file__).resolve().parents[1]


def resolve_database_url(database_url: str | None = None) -> URL:
    url = make_url(database_url or os.environ.get("DATABASE_URL", "sqlite:///data/dominograph.db"))
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        path = Path(url.database)
        path = path if path.is_absolute() else ROOT / path
        url = url.set(database=str(path.resolve()))
    return url


def instant(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


metadata = MetaData()
entities = Table("entities", metadata,
                 Column("kind", String(40), primary_key=True),
                 Column("id", String(200), primary_key=True),
                 Column("payload", JSON, nullable=False))
links = Table("entity_references", metadata,
              Column("owner_kind", String(40), primary_key=True),
              Column("owner_id", String(200), primary_key=True),
              Column("target_kind", String(40), primary_key=True),
              Column("target_id", String(200), primary_key=True),
              ForeignKeyConstraint(["owner_kind", "owner_id"], ["entities.kind", "entities.id"]),
              ForeignKeyConstraint(["target_kind", "target_id"], ["entities.kind", "entities.id"]))

# A relationship version has at most one successor, including concurrent writers.
_supersession = (links.c.owner_kind == "relationship") & (links.c.target_kind == "relationship")
Index("one_relationship_successor", links.c.target_kind, links.c.target_id,
      unique=True, sqlite_where=_supersession, postgresql_where=_supersession)

ingestion_runs = Table(
    "ingestion_runs", metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("id", String(200), nullable=False, unique=True),
    Column("connector", String(40), nullable=False),
    Column("country", String(2), nullable=False),
    Column("started_at", String(40), nullable=False),
    Column("finished_at", String(40)),
    Column("status", String(20), nullable=False),
    Column("series_checked", Integer, nullable=False),
    Column("observations_added", Integer, nullable=False),
    Column("snapshots_added", Integer, nullable=False),
    Column("error", String(200)),
    CheckConstraint("series_checked >= 0 AND observations_added >= 0 AND snapshots_added >= 0"),
    CheckConstraint(
        "(status = 'running' AND finished_at IS NULL AND error IS NULL) OR "
        "(status = 'succeeded' AND finished_at IS NOT NULL AND error IS NULL) OR "
        "(status = 'failed' AND finished_at IS NOT NULL AND error IS NOT NULL)"),
)
Index("ingestion_runs_by_country", ingestion_runs.c.connector, ingestion_runs.c.country,
      ingestion_runs.c.started_at, ingestion_runs.c.sequence)

REFERENCE_FIELDS = {
    "metric": {"node_id": "node"},
    "rawsnapshot": {"source_id": "source"},
    "observation": {"metric_id": "metric", "source_id": "source",
                    "raw_snapshot_id": "rawsnapshot", "revision_of": "observation"},
    "evidence": {"source_id": "source", "observation_ids": "observation",
                 "statement_ids": "institutionalstatement"},
    "relationship": {"from_node": "node", "to_node": "node", "evidence_ids": "evidence",
                     "counter_evidence_ids": "evidence", "supersedes": "relationship"},
    "institutionalstatement": {"source_id": "source", "policy_id": "intervention"},
    "intervention": {"node_ids": "node", "observation_evidence_ids": "evidence",
                     "intent_evidence_ids": "evidence"},
    "hypothesis": {"node_ids": "node", "relationship_ids": "relationship",
                   "dataset_ids": "metric", "policy_ids": "intervention",
                   "institutional_statement_ids": "institutionalstatement",
                   "supporting_evidence_ids": "evidence", "contradicting_evidence_ids": "evidence"},
    "assessment": {"node_id": "node", "metric_ids": "metric", "observation_ids": "observation",
                   "relationship_ids": "relationship", "evidence_ids": "evidence"},
    "scenario": {"node_id": "node", "relationship_ids": "relationship", "evidence_ids": "evidence"},
}


def references(kind, payload):
    result = set()
    for field, target in REFERENCE_FIELDS.get(kind, {}).items():
        value = payload.get(field)
        values = value if isinstance(value, list) else [value]
        result.update((target, item) for item in values if item is not None)
    if kind == "assessment":
        for dimension in payload["dimensions"].values():
            result.update(("observation", item) for item in dimension["observation_ids"])
    if kind == "scenario":
        result.update(("node", impact["node_id"]) for impact in payload["impacts"])
    return result


class Store:
    def __init__(self, database_url=None):
        url = resolve_database_url(database_url)
        options = {}
        if url.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False}
            if not url.database or url.database == ":memory:":
                options["poolclass"] = StaticPool
            else:
                Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, **options)
        if url.get_backend_name() == "sqlite":
            @event.listens_for(self.engine, "connect")
            def enable_fks(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")

    def initialize(self):
        metadata.create_all(self.engine)
        # create_all does not add indexes to tables in an existing pilot database.
        for index in links.indexes:
            index.create(self.engine, checkfirst=True)
        # Protect raw revisions even from accidental direct SQL writes in SQLite.
        if self.engine.dialect.name == "sqlite":
            with self.engine.begin() as connection:
                for action in ("UPDATE", "DELETE"):
                    connection.exec_driver_sql(
                        f"CREATE TRIGGER IF NOT EXISTS immutable_entities_{action.lower()} "
                        f"BEFORE {action} ON entities BEGIN "
                        "SELECT RAISE(ABORT, 'canonical entities are append-only'); END")
        elif self.engine.dialect.name == "postgresql":
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE OR REPLACE FUNCTION dominograph_deny_mutation() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN "
                    "RAISE EXCEPTION 'canonical entities are append-only'; END; $$")
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS immutable_entities ON entities")
                connection.exec_driver_sql(
                    "CREATE TRIGGER immutable_entities BEFORE UPDATE OR DELETE ON entities "
                    "FOR EACH ROW EXECUTE FUNCTION dominograph_deny_mutation()")

    def all(self, kind):
        with self.engine.connect() as connection:
            return [row[0] for row in connection.execute(
                select(entities.c.payload).where(entities.c.kind == kind).order_by(entities.c.id))]

    def get(self, kind, identity):
        with self.engine.connect() as connection:
            result = connection.execute(select(entities.c.payload).where(
                entities.c.kind == kind, entities.c.id == identity)).scalar_one_or_none()
        if result is None:
            raise KeyError(f"unknown {kind}: {identity}")
        return result

    def current_relationships(self):
        """Resolve immutable version chains; include rejected tips for inspection."""
        records = self.all("relationship")
        superseded = {r.get("supersedes") for r in records if r.get("supersedes")}
        return [r for r in records if r["id"] not in superseded]

    def start_ingestion_run(self, connector: str, country: str, started_at: datetime) -> str:
        if started_at.tzinfo is None:
            raise ValueError("ingestion start time must be timezone aware")
        identity = "run-" + uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(insert(ingestion_runs).values(
                id=identity, connector=connector, country=country,
                started_at=started_at.astimezone(timezone.utc).isoformat(),
                status="running", series_checked=0, observations_added=0, snapshots_added=0))
        return identity

    def list_ingestion_runs(self, connector: str, country: str | None = None,
                            *, limit: int = 20, offset: int = 0, successful_only: bool = False):
        query = select(ingestion_runs).where(ingestion_runs.c.connector == connector)
        if country is not None:
            query = query.where(ingestion_runs.c.country == country)
        if successful_only:
            query = query.where(ingestion_runs.c.status == "succeeded")
            ordering = ingestion_runs.c.finished_at
        else:
            ordering = ingestion_runs.c.started_at
        query = query.order_by(ordering.desc(), ingestion_runs.c.sequence.desc()).limit(limit).offset(offset)
        with self.engine.connect() as connection:
            return [{key: value for key, value in row._mapping.items() if key != "sequence"}
                    for row in connection.execute(query)]

    def complete_ingestion_run(self, identity: str, objects: list[Canonical], finished_at: datetime,
                               series_checked: int, observations_added: int, snapshots_added: int):
        with self.engine.begin() as connection:
            self._put_many(connection, objects)
            self._finish_ingestion_run(connection, identity, finished_at, "succeeded",
                                       series_checked, observations_added, snapshots_added, None)

    def fail_ingestion_run(self, identity: str, finished_at: datetime, series_checked: int, error: str):
        with self.engine.begin() as connection:
            self._finish_ingestion_run(connection, identity, finished_at, "failed",
                                       series_checked, 0, 0, error)

    @staticmethod
    def _finish_ingestion_run(connection: Connection, identity: str, finished_at: datetime,
                              status: str, series_checked: int, observations_added: int,
                              snapshots_added: int, error: str | None):
        if finished_at.tzinfo is None:
            raise ValueError("ingestion finish time must be timezone aware")
        started = connection.execute(select(ingestion_runs.c.started_at).where(
            ingestion_runs.c.id == identity, ingestion_runs.c.status == "running")).scalar_one_or_none()
        if started is None:
            raise ValueError("ingestion run is unknown or already finished")
        if finished_at.astimezone(timezone.utc) < instant(started):
            raise ValueError("ingestion finish time precedes its start")
        result = connection.execute(update(ingestion_runs).where(
            ingestion_runs.c.id == identity, ingestion_runs.c.status == "running").values(
                finished_at=finished_at.astimezone(timezone.utc).isoformat(), status=status,
                series_checked=series_checked, observations_added=observations_added,
                snapshots_added=snapshots_added, error=error))
        if result.rowcount != 1:
            raise ValueError("ingestion run was finished by another writer")

    def put_many(self, objects: list[Canonical]):
        with self.engine.begin() as connection:
            self._put_many(connection, objects)

    def _put_many(self, connection: Connection, objects: list[Canonical]):
        pending = {}
        for obj in objects:
            kind = obj.__class__.__name__.lower()
            if kind not in MODELS:
                raise ValueError("unknown canonical object")
            payload = MODELS[kind].model_validate(obj.model_dump()).model_dump(mode="json")
            key = (kind, obj.id)
            if key in pending and pending[key] != payload:
                raise ValueError(f"conflicting immutable ID: {key}")
            pending[key] = payload
        existing = {(row.kind, row.id): row.payload for row in connection.execute(select(entities))}
        combined = existing | pending
        for key, payload in pending.items():
            if key in existing and MODELS[key[0]].model_validate(existing[key]).model_dump(mode="json") != payload:
                raise ValueError(f"immutable ID already exists: {key}")
            for target in references(key[0], payload):
                if target not in combined:
                    raise ValueError(f"missing reference {target} for {key}")
            self._validate_semantics(key[0], payload, combined)
        for (kind, identity), payload in pending.items():
            if (kind, identity) not in existing:
                connection.execute(insert(entities).values(kind=kind, id=identity, payload=payload))
        for (kind, identity), payload in pending.items():
            if (kind, identity) not in existing:
                for target_kind, target_id in sorted(references(kind, payload)):
                    connection.execute(insert(links).values(owner_kind=kind, owner_id=identity,
                                                           target_kind=target_kind, target_id=target_id))

    @staticmethod
    def _validate_semantics(kind, payload, combined):
        def get(target_kind, identity):
            return combined[target_kind, identity]

        if kind in {"rawsnapshot", "observation", "institutionalstatement"}:
            source = get("source", payload["source_id"])
            if not source["redistribution_allowed"]:
                raise ValueError("source license does not permit storing redistributable content")
            if payload["source_url"] != source["url"]:
                raise ValueError("source URL does not match registered source")
        if kind == "observation":
            raw = get("rawsnapshot", payload["raw_snapshot_id"])
            if raw["source_id"] != payload["source_id"]:
                raise ValueError("snapshot source mismatch")
            if instant(raw["retrieval_time"]) != instant(payload["retrieval_time"]):
                raise ValueError("snapshot retrieval time mismatch")
            if raw["collector_version"] != payload["collector_version"]:
                raise ValueError("snapshot collector version mismatch")
            if payload["revision_of"]:
                prior = get("observation", payload["revision_of"])
                if prior["metric_id"] != payload["metric_id"] or prior["observation_date"] != payload["observation_date"]:
                    raise ValueError("revision must retain metric and observation date")
                if prior["source_id"] != payload["source_id"]:
                    raise ValueError("revision must retain source")
                if instant(prior["retrieval_time"]) > instant(payload["retrieval_time"]):
                    raise ValueError("revision retrieval must not precede original")
                revision_chain = {payload["id"]}
                while prior:
                    if prior["id"] in revision_chain:
                        raise ValueError("revision lineage must not contain cycles")
                    revision_chain.add(prior["id"])
                    prior = get("observation", prior["revision_of"]) if prior["revision_of"] else None
        if kind == "evidence":
            for obs_id in payload["observation_ids"]:
                obs = get("observation", obs_id)
                if obs["source_id"] != payload["source_id"]:
                    raise ValueError("evidence source mismatch")
                if payload["confidence"] > obs["confidence"]:
                    raise ValueError("evidence confidence exceeds its observations")
            for statement_id in payload["statement_ids"]:
                statement = get("institutionalstatement", statement_id)
                if statement["source_id"] != payload["source_id"]:
                    raise ValueError("intent evidence source mismatch")
                if payload["confidence"] > statement["confidence"]:
                    raise ValueError("intent confidence exceeds statement")
            if payload["evidence_state"] == "causally_supported" and get("source", payload["source_id"])["synthetic"]:
                raise ValueError("synthetic sources cannot support empirical causal claims")
            if payload["evidence_state"] == "documented_coordination":
                if not payload["statement_ids"] or get("source", payload["source_id"])["synthetic"]:
                    raise ValueError("coordination requires direct non-synthetic institutional documentation")
        if kind in {"relationship", "hypothesis"} and payload["evidence_state"] == "causally_supported":
            support_ids = payload["evidence_ids"] if kind == "relationship" else payload["supporting_evidence_ids"]
            support = [get("evidence", item) for item in support_ids]
            if payload["review_status"] != "approved" or not any(
                e["evidence_state"] == "causally_supported" and e["polarity"] == "supporting"
                for e in support
            ):
                raise ValueError(f"causal {kind} needs reviewed causal identification evidence")
        if kind in {"relationship", "hypothesis"} and payload["evidence_state"] == "documented_coordination":
            support_ids = payload["evidence_ids"] if kind == "relationship" else payload["supporting_evidence_ids"]
            if payload["review_status"] != "approved" or not any(
                get("evidence", item)["evidence_state"] == "documented_coordination"
                and get("evidence", item)["polarity"] == "supporting"
                for item in support_ids
            ):
                raise ValueError(f"coordination {kind} requires reviewed documentation evidence")
        if kind in {"relationship", "hypothesis", "assessment", "scenario"}:
            evidence_ids = (payload.get("evidence_ids", []) +
                            payload.get("counter_evidence_ids", []) +
                            payload.get("supporting_evidence_ids", []) +
                            payload.get("contradicting_evidence_ids", []))
            if not evidence_ids and payload["confidence"] != 0:
                raise ValueError("unsupported claims must have zero confidence")
            claim_confidence = payload["confidence"] / 100 if kind == "assessment" else payload["confidence"]
            if evidence_ids and claim_confidence > max(get("evidence", item)["confidence"] for item in evidence_ids):
                raise ValueError("claim confidence exceeds evidence")
        if kind == "scenario":
            if any(get("relationship", item)["review_status"] in {"rejected", "needs_revision"}
                   for item in payload["relationship_ids"]):
                raise ValueError("scenario cannot use rejected relationships")
            if payload["relationship_ids"] and payload["confidence"] > min(
                get("relationship", item)["confidence"] for item in payload["relationship_ids"]
            ):
                raise ValueError("scenario confidence exceeds relationship confidence")
        if kind == "relationship":
            previous_id = payload.get("supersedes")
            if previous_id:
                previous = get("relationship", previous_id)
                if (previous["from_node"], previous["to_node"]) != (payload["from_node"], payload["to_node"]):
                    raise ValueError("relationship revision must retain endpoints")
                if any(k == "relationship" and p["id"] != payload["id"]
                       and p.get("supersedes") == previous_id for (k, _), p in combined.items()):
                    raise ValueError("relationship version already has a successor")
                seen = {payload["id"]}
                while previous:
                    if previous["id"] in seen:
                        raise ValueError("relationship supersession must not contain cycles")
                    seen.add(previous["id"])
                    previous = get("relationship", previous["supersedes"]) if previous.get("supersedes") else None
            if any(get("evidence", item)["polarity"] != "supporting" for item in payload["evidence_ids"]):
                raise ValueError("relationship supporting evidence polarity mismatch")
            if any(get("evidence", item)["polarity"] != "contradicting" for item in payload["counter_evidence_ids"]):
                raise ValueError("relationship counter-evidence polarity mismatch")
        if kind == "hypothesis":
            for field, polarity in (("supporting_evidence_ids", "supporting"),
                                    ("contradicting_evidence_ids", "contradicting")):
                if any(get("evidence", item)["polarity"] != polarity for item in payload[field]):
                    raise ValueError("hypothesis evidence polarity mismatch")
        if kind == "intervention":
            for field, evidence_kind in (("observation_evidence_ids", "observation"),
                                         ("intent_evidence_ids", "intent")):
                if any(get("evidence", item)["kind"] != evidence_kind for item in payload[field]):
                    raise ValueError("intervention intent/observation evidence must be separate")
        if kind == "assessment":
            for obs_id in payload["observation_ids"]:
                metric = get("metric", get("observation", obs_id)["metric_id"])
                if metric["node_id"] != payload["node_id"] or metric["id"] not in payload["metric_ids"]:
                    raise ValueError("assessment observation does not belong to its node/metrics")
            for dimension in payload["dimensions"].values():
                if not set(dimension["observation_ids"]) <= set(payload["observation_ids"]):
                    raise ValueError("dimension lineage must appear in assessment lineage")

    def provenance(self, kind, identity):
        visited = set()
        resolved = []
        with self.engine.connect() as connection:
            records = {(row.kind, row.id): row.payload for row in connection.execute(select(entities))}
        adjacency = {key: references(key[0], payload) for key, payload in records.items()}
        # Only retained forward references define provenance. Graph exploration
        # and node detail expose current neighbors without contaminating history.

        def walk(key):
            if key in visited:
                return
            visited.add(key)
            if key not in records:
                raise KeyError(f"unknown {key[0]}: {key[1]}")
            payload = records[key]
            targets = sorted(adjacency[key])
            resolved.append({"entity_type": key[0], "entity": payload,
                             "references": [{"entity_type": k, "entity_id": i} for k, i in targets]})
            for target in targets:
                walk(target)

        walk((kind, identity))
        return {"root": {"entity_type": kind, "entity_id": identity}, "lineage": resolved}
