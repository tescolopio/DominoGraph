from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from agents.protocols import RoutingTier, TaskMetadata, route
from api.main import create_app
from collectors.fred import FredCollector
from collectors.synthetic import SyntheticCollector
from core.scenarios import ScenarioLimitError, run_scenario
from core.scoring import assess
from core.store import Store, entities, links
from orchestration.pipeline import execute
from schemas.models import (CANONICAL_MODELS, DIMENSIONS, MODELS, Evidence, EvidenceState,
                            Hypothesis, Metric, Observation, Relationship, Source)
from scripts.export import export
from scripts.seed import seed
from transforms.normalize import normalize_csv, snapshot


class PilotCase(unittest.TestCase):
    def setUp(self):
        self.store = Store("sqlite:///:memory:")
        seed(self.store)

    def tearDown(self):
        self.store.engine.dispose()

    def model(self, kind, identity):
        return MODELS[kind].model_validate(self.store.get(kind, identity))

    def test_seed_complete_idempotent_and_valid(self):
        before = {kind: self.store.all(kind) for kind in MODELS}
        seed(self.store)
        self.assertEqual(before, {kind: self.store.all(kind) for kind in MODELS})
        self.assertEqual(10, len(before["metric"]))
        self.assertEqual(10, len(before["observation"]))
        self.assertIn("HBM price", self.store.get("metric", "hbm")["name"])
        self.assertIn("uncertain demand proxy", self.store.get("metric", "hbm")["context"])
        self.assertEqual(6, len(before["assessment"]))
        for kind, records in before.items():
            for record in records:
                MODELS[kind].model_validate(record)
        self.assertEqual(12, len(EvidenceState))
        self.assertEqual(10, len(CANONICAL_MODELS))

    def test_provenance_recursively_resolves_and_handles_cycles(self):
        assessment = self.store.all("assessment")[0]
        provenance = self.store.provenance("assessment", assessment["id"])
        kinds = {item["entity_type"] for item in provenance["lineage"]}
        self.assertTrue({"assessment", "node", "metric", "observation", "evidence", "source", "rawsnapshot"} <= kinds)
        result = self.store.provenance("hypothesis", "hypothesis-memory-chain")
        keys = [(row["entity_type"], row["entity"]["id"]) for row in result["lineage"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn(("institutionalstatement", "statement-pilot"), keys)
        node_lineage = self.store.provenance("node", "ai-capex")
        self.assertIn("observation", {row["entity_type"] for row in node_lineage["lineage"]})

    def test_missing_reference_rolls_back_entire_batch(self):
        node = self.model("node", "ai-capex").model_copy(update={"id": "new-node"})
        metric = self.model("metric", "dram").model_copy(update={"id": "bad", "node_id": "missing"})
        with self.assertRaisesRegex(ValueError, "missing reference"):
            self.store.put_many([node, metric])
        with self.assertRaises(KeyError):
            self.store.get("node", "new-node")

    def test_database_fk_enforced(self):
        with self.assertRaises(IntegrityError):
            with self.store.engine.begin() as connection:
                connection.execute(insert(links).values(owner_kind="node", owner_id="missing",
                                                       target_kind="node", target_id="also-missing"))

    def test_append_only_and_revision_lineage(self):
        obs = MODELS["observation"].model_validate(self.store.all("observation")[0])
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.store.put_many([obs.model_copy(update={"value": 999})])
        revised = obs.model_copy(update={"id": "revision-v2", "revision_of": obs.id,
                                        "value": obs.value + 1, "vintage": "pilot-v2"})
        self.store.put_many([revised])
        self.assertEqual(obs.value, self.store.get("observation", obs.id)["value"])
        lineage = self.store.provenance("observation", revised.id)
        lineage_ids = {r["entity"]["id"] for r in lineage["lineage"] if r["entity_type"] == "observation"}
        self.assertTrue({obs.id, revised.id} <= lineage_ids)
        with self.assertRaises(IntegrityError):
            with self.store.engine.begin() as connection:
                connection.execute(entities.delete().where(entities.c.id == obs.id))
        with self.assertRaisesRegex(ValueError, "retain metric"):
            self.store.put_many([revised.model_copy(update={"id": "bad-revision", "metric_id": "hbm"})])
        with self.assertRaisesRegex(ValueError, "cycles"):
            self.store.put_many([
                obs.model_copy(update={"id": "cycle-a", "revision_of": "cycle-b"}),
                obs.model_copy(update={"id": "cycle-b", "revision_of": "cycle-a"})])
        with self.assertRaisesRegex(ValueError, "collector version"):
            self.store.put_many([obs.model_copy(update={"id": "bad-version", "collector_version": "mismatch"})])
        earlier = datetime.fromisoformat("2026-01-15T01:00:00+02:00")
        earlier_raw = self.model("rawsnapshot", obs.raw_snapshot_id).model_copy(
            update={"id": "raw-offset", "retrieval_time": earlier})
        with self.assertRaisesRegex(ValueError, "precede"):
            self.store.put_many([earlier_raw, obs.model_copy(update={
                "id": "bad-offset-revision", "revision_of": obs.id,
                "raw_snapshot_id": earlier_raw.id, "retrieval_time": earlier})])

    def test_source_license_and_snapshot_hash(self):
        source = self.model("source", "synthetic-memory-v1")
        restricted = source.model_copy(update={"id": "restricted", "redistribution_allowed": False})
        raw = self.model("rawsnapshot", self.store.all("rawsnapshot")[0]["id"])
        with self.assertRaisesRegex(ValueError, "license"):
            self.store.put_many([restricted, raw.model_copy(update={"id": "restricted-raw", "source_id": restricted.id})])
        with self.assertRaises(ValidationError):
            MODELS["rawsnapshot"].model_validate(raw.model_dump() | {"content": "modified"})
        self.assertEqual(sha256(raw.content.encode()).hexdigest(), raw.content_sha256)

    def test_confidence_and_intent_are_validated(self):
        evidence = self.model("evidence", "evidence-dram")
        with self.assertRaisesRegex(ValueError, "confidence"):
            self.store.put_many([evidence.model_copy(update={"id": "overclaim", "confidence": .9})])
        with self.assertRaises(ValidationError):
            Evidence.model_validate(evidence.model_dump() | {"kind": "intent"})
        policy = self.model("intervention", "pilot-capacity-policy")
        with self.assertRaisesRegex(ValueError, "separate"):
            self.store.put_many([policy.model_copy(update={"id": "bad-policy",
                                                         "observation_evidence_ids": ["evidence-intent"]})])
        edge = self.model("relationship", "edge-1")
        with self.assertRaises(ValidationError):
            Relationship.model_validate(edge.model_dump() | {"relationship_type": "causal"})
        with self.assertRaises(ValidationError):
            Relationship.model_validate(edge.model_dump() | {"confidence": 1.01})
        with self.assertRaises(ValidationError):
            Relationship.model_validate(edge.model_dump() | {"counter_evidence_ids": [], "evidence_gaps": []})
        with self.assertRaisesRegex(ValueError, "causal relationship"):
            self.store.put_many([edge.model_copy(update={"id": "unsupported-causal",
                                                        "evidence_state": EvidenceState.CAUSALLY_SUPPORTED})])
        with self.assertRaises(ValidationError):
            Evidence.model_validate(evidence.model_dump() | {"evidence_state": "causally_supported"})
        with self.assertRaises(ValidationError):
            Evidence.model_validate(evidence.model_dump() | {"evidence_state": "documented_coordination"})

    def test_hypothesis_evidence_arrays_mandatory_and_polarity(self):
        hypothesis = self.model("hypothesis", "hypothesis-memory-chain")
        payload = hypothesis.model_dump()
        payload.pop("contradicting_evidence_ids")
        with self.assertRaises(ValidationError):
            Hypothesis.model_validate(payload)
        with self.assertRaises(ValidationError):
            Hypothesis.model_validate(hypothesis.model_dump() | {
                "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "evidence_gaps": []})
        with self.assertRaisesRegex(ValueError, "polarity"):
            self.store.put_many([hypothesis.model_copy(update={"id": "bad-hypothesis",
                                                               "supporting_evidence_ids": ["evidence-counter"],
                                                               "contradicting_evidence_ids": []})])

    def test_scoring_is_deterministic_explicit_and_missing_is_null(self):
        metrics = [Metric.model_validate(m) for m in self.store.all("metric")]
        observations = [Observation.model_validate(o) for o in self.store.all("observation")]
        args = ("consumer-memory", metrics, observations, ["evidence-dram", "evidence-nand"], [], date(2026, 1, 15))
        assessment = assess(*args)
        again = assess(args[0], list(reversed(metrics)), list(reversed(observations)), *args[3:])
        self.assertEqual(assessment, again)
        self.assertEqual(set(DIMENSIONS), set(assessment.dimensions))
        self.assertAlmostEqual(56.4, assessment.dimensions["pressure"].score)
        self.assertEqual(assessment.pressure, assessment.dimensions["pressure"].score)
        self.assertIsNone(assessment.support)
        self.assertEqual(25, assessment.dimensions["pressure"].confidence)
        self.assertTrue(all(d.score is None for name, d in assessment.dimensions.items() if name != "pressure"))
        self.assertTrue(assessment.dimensions["pressure"].rules)
        self.assertNotIn("composite", assessment.model_dump())
        changed_vintage = [o.model_copy(update={"vintage": "changed-vintage"}) for o in observations]
        revised_assessment = assess(args[0], metrics, changed_vintage, *args[3:])
        self.assertNotEqual(assessment.id, revised_assessment.id)
        missing = assess("device-prices", metrics, observations, [], [], date(2026, 1, 15))
        self.assertTrue(all(d.score is None and d.confidence == 0 for d in missing.dimensions.values()))
        historical = assess("consumer-memory", metrics, observations, [], [], date(2025, 12, 31))
        self.assertTrue(all(d.score is None for d in historical.dimensions.values()))

    def test_contextual_direction_bounds_and_latest_revision(self):
        metric = self.model("metric", "inventory")
        obs = next(Observation.model_validate(o) for o in self.store.all("observation") if o["metric_id"] == "inventory")
        result = assess("memory-capacity", [metric], [obs], ["evidence-inventory"], [], date(2026, 1, 15))
        self.assertEqual(65, result.dimensions["pressure"].score)
        revision = obs.model_copy(update={"id": "newer", "value": -10000,
                                         "retrieval_time": datetime(2026, 1, 16, tzinfo=timezone.utc)})
        result = assess("memory-capacity", [metric], [obs, revision], [], [], date(2026, 1, 16))
        self.assertEqual(100, result.dimensions["pressure"].score)
        self.assertEqual(["newer"], result.observation_ids)
        equivalent = obs.model_copy(update={
            "retrieval_time": datetime.fromisoformat("2026-01-14T19:00:00-05:00")})
        cutoff = assess("memory-capacity", [metric], [equivalent], [], [], date(2026, 1, 14))
        self.assertIsNone(cutoff.pressure)
        available = assess("memory-capacity", [metric], [equivalent], [], [], date(2026, 1, 15))
        self.assertEqual(65, available.pressure)

    def test_scenarios_sign_lag_bounds_and_no_mutation(self):
        before = self.store.all("scenario")
        short = run_scenario(self.store, "ai-capex", 20, 2)
        self.assertEqual(1, len(short.impacts))
        result = run_scenario(self.store, "ai-capex", 20, 24)
        self.assertEqual(6, len(result.impacts))
        impacts = {i["node_id"]: i for i in result.impacts}
        self.assertEqual(10, impacts["hbm-demand"]["illustrative_change_percent"])
        self.assertLess(impacts["consumer-demand"]["illustrative_change_percent"], 0)
        self.assertEqual("illustrative_not_forecast", result.kind)
        self.assertEqual(before, self.store.all("scenario"))
        self.assertEqual(result, run_scenario(self.store, "ai-capex", 20, 24))
        with self.assertRaises(ScenarioLimitError):
            run_scenario(self.store, "ai-capex", 20, 24, max_steps=1)
        with self.assertRaises(ScenarioLimitError):
            run_scenario(self.store, "ai-capex", 20, 24, max_paths=1)
        self.store.put_many([result])
        with self.assertRaisesRegex(ValueError, "confidence"):
            self.store.put_many([result.model_copy(update={"id": "overconfident-scenario", "confidence": .9})])
        rejected = self.model("relationship", "edge-1").model_copy(update={
            "id": "edge-rejected", "review_status": MODELS["relationship"].model_validate(
                self.store.get("relationship", "edge-1") | {"review_status": "rejected"}).review_status})
        self.store.put_many([rejected])
        rerun = run_scenario(self.store, "ai-capex", 20, 24)
        self.assertNotIn(rejected.id, rerun.relationship_ids)
        self.assertEqual(rejected.id, rerun.skipped_relationships[0]["relationship_id"])

    def test_api_contracts_errors_validation_and_static(self):
        with TestClient(create_app(self.store)) as client:
            self.assertEqual(200, client.get("/health").status_code)
            self.assertEqual(6, len(client.get("/api/nodes").json()))
            self.assertEqual({"nodes", "relationships"}, set(client.get("/api/graph").json()))
            detail = client.get("/api/nodes/ai-capex").json()
            self.assertEqual({"node", "metrics", "observations", "relationships", "assessment",
                              "hypotheses", "interventions", "institutional_statements",
                              "evidence", "sources"}, set(detail))
            self.assertTrue(detail["institutional_statements"])
            self.assertTrue(client.get("/api/sources").json()[0]["synthetic"])
            identity = detail["assessment"]["id"]
            self.assertEqual(200, client.get("/api/provenance/assessment/" + identity).status_code)
            self.assertEqual(404, client.get("/api/nodes/missing").status_code)
            self.assertEqual(404, client.get("/api/provenance/invalid/foo").status_code)
            self.assertEqual(404, client.get("/api/provenance/node/missing").status_code)
            body = {"node_id": "ai-capex", "shock": 20, "horizon_months": 24}
            self.assertEqual(200, client.post("/api/scenarios/run", json=body).status_code)
            for updates in ({"shock": 101}, {"horizon_months": 0}, {"horizon_months": 121},
                            {"horizon_months": 1.5}, {"unexpected": True}):
                self.assertEqual(422, client.post("/api/scenarios/run", json=body | updates).status_code)
            self.assertEqual(404, client.post("/api/scenarios/run", json=body | {"node_id": "missing"}).status_code)
            with patch("api.main.run_scenario", side_effect=ScenarioLimitError("path limit")):
                self.assertEqual(422, client.post("/api/scenarios/run", json=body).status_code)
            self.assertNotIn("access-control-allow-origin", client.get("/api/nodes", headers={"Origin": "https://evil.invalid"}).headers)
            index = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
            if index.is_file():
                self.assertEqual(200, client.get("/").status_code)

    def test_empty_database_startup_does_not_seed(self):
        empty = Store("sqlite:///:memory:")
        try:
            with TestClient(create_app(empty)) as client:
                self.assertEqual([], client.get("/api/nodes").json())
                self.assertFalse(client.get("/health").json()["seeded"])
        finally:
            empty.engine.dispose()

    def test_schemas_match_models_and_enforce_canonical_fields(self):
        export(check=True)
        for model in CANONICAL_MODELS:
            schema = model.model_json_schema()
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual("1.0.0", schema["properties"]["schema_version"]["const"])
            json.dumps(schema)

    def test_collectors_are_fixed_and_normalization_has_lineage(self):
        collection = SyntheticCollector().collect()
        raw = snapshot(collection, "synthetic-memory-v1")
        observations = normalize_csv(raw)
        self.assertEqual(10, len(observations))
        self.assertTrue(all(o.normalization_lineage and o.raw_snapshot_id == raw.id for o in observations))
        renormalized = normalize_csv(raw, observations, transformation_version="csv-normalization-v2")
        self.assertNotEqual(observations[0].id, renormalized[0].id)
        self.assertEqual(observations[0].id, renormalized[0].revision_of)
        self.assertIn("transformation:csv-normalization-v2", renormalized[0].normalization_lineage)
        with self.assertRaises(ValueError):
            normalize_csv(raw.model_copy(update={"content": "bad,columns\n1,2\n"}))
        with self.assertRaises(ValueError):
            FredCollector("https://evil.invalid")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "FRED_API_KEY"):
                FredCollector("GDP").collect()

    def test_routing_forbids_ai_for_deterministic_tasks(self):
        self.assertEqual(RoutingTier.DETERMINISTIC, route("score"))
        self.assertEqual(RoutingTier.ANALYTICAL, route("research"))
        self.assertEqual(5, len(RoutingTier))
        self.assertEqual(RoutingTier.ANALYTICAL, route("source_compare"))
        self.assertEqual(RoutingTier.EXTRACTION, route(TaskMetadata("extract", "extraction", 2)))
        self.assertEqual(RoutingTier.DEEP_REASONING, route(TaskMetadata("research", "research", 5)))
        self.assertEqual(RoutingTier.MONITORING, route("monitor"))
        with self.assertRaisesRegex(ValueError, "prohibited"):
            execute(TaskMetadata("monitor", "monitoring", 5), lambda: 3, provider=object())
        self.assertEqual(3, execute("score", lambda: 3))
        with self.assertRaisesRegex(ValueError, "prohibited"):
            execute("score", lambda: 3, provider=object())
        with self.assertRaises(ValueError):
            route("unknown")
        with self.assertRaises(ValueError):
            execute("research", lambda: 3)


if __name__ == "__main__":
    unittest.main()
