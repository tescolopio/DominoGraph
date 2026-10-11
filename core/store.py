"""Relational canonical payloads and FK lineage; all writes are append-only."""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (JSON, Column, ForeignKeyConstraint, MetaData, String, Table,
                        create_engine, event, insert, select)
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from schemas.models import MODELS, Canonical

ROOT = Path(__file__).resolve().parents[1]


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

REFERENCE_FIELDS = {
    "metric": {"node_id": "node"},
    "rawsnapshot": {"source_id": "source"},
    "observation": {"metric_id": "metric", "source_id": "source",
                    "raw_snapshot_id": "rawsnapshot", "revision_of": "observation"},
    "evidence": {"source_id": "source", "observation_ids": "observation",
                 "statement_ids": "institutionalstatement"},
    "relationship": {"from_node": "node", "to_node": "node", "evidence_ids": "evidence",
                     "counter_evidence_ids": "evidence"},
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
        url = make_url(database_url or os.environ.get("DATABASE_URL", "sqlite:///data/dominograph.db"))
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        options = {}
        if url.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False}
            if not url.database or url.database == ":memory:":
                options["poolclass"] = StaticPool
            else:
                path = Path(url.database)
                path = path if path.is_absolute() else ROOT / path
                path.parent.mkdir(parents=True, exist_ok=True)
                url = url.set(database=str(path.resolve()))
        self.engine = create_engine(url, **options)
        if url.get_backend_name() == "sqlite":
            @event.listens_for(self.engine, "connect")
            def enable_fks(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")

    def initialize(self):
        metadata.create_all(self.engine)
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

    def put_many(self, objects: list[Canonical]):
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
        with self.engine.begin() as connection:
            existing = {(row.kind, row.id): row.payload for row in connection.execute(select(entities))}
            combined = existing | pending
            for key, payload in pending.items():
                if key in existing and existing[key] != payload:
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
        if kind == "relationship" and payload["evidence_state"] == "causally_supported":
            support = [get("evidence", item) for item in payload["evidence_ids"]]
            if payload["review_status"] != "approved" or not any(
                e["evidence_state"] == "causally_supported" and e["polarity"] == "supporting"
                for e in support
            ):
                raise ValueError("causal relationship needs reviewed causal identification evidence")
        if kind == "relationship" and payload["evidence_state"] == "documented_coordination":
            if payload["review_status"] != "approved" or not any(
                get("evidence", item)["evidence_state"] == "documented_coordination"
                and get("evidence", item)["polarity"] == "supporting"
                for item in payload["evidence_ids"]
            ):
                raise ValueError("coordination relationship requires reviewed documentation evidence")
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
        # Nodes and metric definitions also expose their measured lineage. These
        # reverse ownership links are read-only navigation, not FK dependencies.
        for key, payload in records.items():
            if key[0] == "metric":
                adjacency[("node", payload["node_id"])].add(key)
            if key[0] == "observation":
                adjacency[("metric", payload["metric_id"])].add(key)
            if key[0] == "assessment":
                adjacency[("node", payload["node_id"])].add(key)
            if key[0] == "evidence":
                for observation_id in payload["observation_ids"]:
                    adjacency[("observation", observation_id)].add(key)
            if key[0] == "relationship":
                for field in ("from_node", "to_node"):
                    adjacency[("node", payload[field])].add(key)

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
