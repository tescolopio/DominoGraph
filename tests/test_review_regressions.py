"""Regression coverage for historical lineage, ingestion and graph review."""

from dataclasses import replace
from datetime import datetime, timezone
from itertools import permutations
from unittest import TestCase

from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from api.main import create_app
from collectors.synthetic import SyntheticCollector
from core.scenarios import run_scenario
from core.store import Store, entities, links
from schemas.models import MODELS, EvidenceState, ReviewStatus
from scripts.seed import seed
from transforms.normalize import normalize_csv, snapshot


class ReviewRegressions(TestCase):
    def setUp(self):
        self.store = Store("sqlite:///:memory:")
        seed(self.store)

    def tearDown(self):
        self.store.engine.dispose()

    def model(self, kind, identity):
        return MODELS[kind].model_validate(self.store.get(kind, identity))

    def observations(self):
        return [MODELS["observation"].model_validate(o) for o in self.store.all("observation")]

    def raw(self, month, source="synthetic-memory-v1"):
        return snapshot(replace(SyntheticCollector().collect(),
                                retrieval_time=datetime(2026, month, 15, tzinfo=timezone.utc)), source)

    def test_historical_provenance_is_unchanged_by_future_ingestion(self):
        assessment = self.store.all("assessment")[0]
        before = self.store.provenance("assessment", assessment["id"])
        raw = self.raw(2)
        revised = normalize_csv(raw, self.observations())
        self.store.put_many([raw, *revised])
        self.assertEqual(before, self.store.provenance("assessment", assessment["id"]))
        future_ids = {o.id for o in revised}
        self.assertFalse(future_ids.intersection(r["entity"]["id"] for r in before["lineage"]))
        # Current node exploration still exposes all available vintages.
        with TestClient(create_app(self.store)) as client:
            result = client.get("/api/nodes/" + assessment["node_id"]).json()
            self.assertTrue(future_ids.intersection(o["id"] for o in result["observations"]))

    def test_revised_snapshot_retry_preserves_predecessor_even_after_later_ingestion(self):
        raw = self.raw(2)
        revised = normalize_csv(raw, self.observations())
        self.store.put_many([raw, *revised])
        later = self.raw(3)
        self.store.put_many([later, *normalize_csv(later, self.observations())])
        before = self.store.all("observation")
        retry = normalize_csv(raw, iter(self.observations()))
        self.assertEqual(revised, retry)
        self.store.put_many([raw, *retry])
        self.assertEqual(before, self.store.all("observation"))

    def test_out_of_order_snapshot_never_revises_a_future_release(self):
        original = self.observations()
        later = self.raw(3)
        self.store.put_many([later, *normalize_csv(later, original)])
        earlier = self.raw(2)
        revised = normalize_csv(earlier, self.observations())
        self.assertEqual({o.id for o in original}, {o.revision_of for o in revised})
        self.store.put_many([earlier, *revised])

    def test_revision_predecessor_must_share_source(self):
        other_raw = self.raw(2, "other-source")
        self.assertTrue(all(o.revision_of is None for o in normalize_csv(other_raw, self.observations())))
        source = self.model("source", "synthetic-memory-v1").model_copy(update={"id": "other-source"})
        obs = normalize_csv(other_raw)[0]
        old = next(o for o in self.observations() if o.metric_id == obs.metric_id)
        with self.assertRaisesRegex(ValueError, "retain source"):
            self.store.put_many([source, other_raw, obs.model_copy(update={"revision_of": old.id})])

    def test_hypotheses_cannot_promote_synthetic_evidence_even_with_approval(self):
        hypothesis = self.model("hypothesis", "hypothesis-memory-chain")
        for state in (EvidenceState.CAUSALLY_SUPPORTED, EvidenceState.DOCUMENTED_COORDINATION):
            for status in (ReviewStatus.UNREVIEWED, ReviewStatus.APPROVED):
                with self.subTest(state=state, status=status), self.assertRaisesRegex(ValueError, "hypothesis"):
                    self.store.put_many([hypothesis.model_copy(update={
                        "id": "promoted", "evidence_state": state, "review_status": status})])

    def test_hypothesis_promotion_requires_review_and_matching_evidence(self):
        # Fictional test fixtures exercise the non-synthetic validation branch.
        source = self.model("source", "synthetic-memory-v1").model_copy(update={
            "id": "test-primary-source", "synthetic": False})
        old = self.observations()[0]
        raw = self.model("rawsnapshot", old.raw_snapshot_id).model_copy(update={
            "id": "test-primary-raw", "source_id": source.id})
        obs = old.model_copy(update={"id": "test-primary-observation", "source_id": source.id,
                                     "raw_snapshot_id": raw.id})
        evidence = self.model("evidence", "evidence-" + old.metric_id).model_copy(update={
            "id": "test-causal-evidence", "source_id": source.id, "observation_ids": [obs.id],
            "evidence_state": EvidenceState.CAUSALLY_SUPPORTED, "causal_identification": "Test identification",
            "review_status": ReviewStatus.APPROVED})
        self.store.put_many([source, raw, obs, evidence])
        hypothesis = self.model("hypothesis", "hypothesis-memory-chain").model_copy(update={
            "id": "causal-hypothesis", "supporting_evidence_ids": [evidence.id],
            "evidence_state": EvidenceState.CAUSALLY_SUPPORTED})
        with self.assertRaisesRegex(ValueError, "causal hypothesis"):
            self.store.put_many([hypothesis])
        approved = hypothesis.model_copy(update={"review_status": ReviewStatus.APPROVED})
        self.store.put_many([approved])
        with self.assertRaisesRegex(ValueError, "coordination hypothesis"):
            self.store.put_many([approved.model_copy(update={"id": "wrong-kind",
                                 "evidence_state": EvidenceState.DOCUMENTED_COORDINATION})])

    def test_scenario_sums_before_clamping_independent_of_relationship_ids(self):
        template = self.store.get("relationship", "edge-1")

        class Graph:
            def get(self, *args):
                return {}

            def current_relationships(self):
                return self.edges

        graph = Graph()
        for signs in set(permutations(("positive", "positive", "negative"))):
            graph.edges = [template | {"id": str(i), "direction": sign, "illustrative_coefficient": .8}
                           for i, sign in enumerate(signs)]
            for shock, expected in ((100, 80), (-100, -80)):
                result = run_scenario(graph, "ai-capex", shock, 24)
                target = next(i for i in result.impacts if i["node_id"] == "hbm-demand")
                self.assertAlmostEqual(expected, target["illustrative_change_percent"])
                self.assertEqual("bounded-path-v2", result.propagation_version)
        graph.edges = [template | {"id": str(i), "illustrative_coefficient": .8} for i in range(3)]
        result = run_scenario(graph, "ai-capex", 100, 24)
        self.assertEqual(100, next(i for i in result.impacts if i["node_id"] == "hbm-demand")["illustrative_change_percent"])

    def test_rejection_supersedes_current_edge_without_rewriting_history(self):
        edge = self.model("relationship", "edge-1")
        original = self.store.provenance("relationship", edge.id)
        historical = run_scenario(self.store, "ai-capex", 20, 24)
        self.store.put_many([historical])
        before = self.store.provenance("scenario", historical.id)
        rejected = edge.model_copy(update={"id": "edge-1-v2", "supersedes": edge.id,
                                           "review_status": ReviewStatus.REJECTED})
        self.store.put_many([rejected])
        self.store.put_many([rejected])
        self.assertEqual(original, self.store.provenance("relationship", edge.id))
        self.assertEqual(before, self.store.provenance("scenario", historical.id))
        current = run_scenario(self.store, "ai-capex", 20, 24)
        self.assertEqual([], current.relationship_ids)
        self.assertEqual(rejected.id, current.skipped_relationships[0]["relationship_id"])
        with TestClient(create_app(self.store)) as client:
            for path in ("/api/graph", "/api/nodes/ai-capex"):
                ids = {r["id"] for r in client.get(path).json()["relationships"]}
                self.assertIn(rejected.id, ids)
                self.assertNotIn(edge.id, ids)
        restored = rejected.model_copy(update={"id": "edge-1-v3", "supersedes": rejected.id,
                                               "review_status": ReviewStatus.APPROVED})
        self.store.put_many([restored])
        rerun = run_scenario(self.store, "ai-capex", 20, 24)
        self.assertIn(restored.id, rerun.relationship_ids)
        self.assertNotIn(edge.id, rerun.relationship_ids)

    def test_supersession_rejects_branches_cycles_and_changed_endpoints(self):
        edge = self.model("relationship", "edge-1")
        child = edge.model_copy(update={"id": "child", "supersedes": edge.id})
        with self.assertRaisesRegex(ValueError, "endpoints"):
            self.store.put_many([child.model_copy(update={"to_node": "consumer-demand"})])
        with self.assertRaisesRegex(ValueError, "cycles"):
            self.store.put_many([edge.model_copy(update={"id": "a", "supersedes": "b"}),
                                 edge.model_copy(update={"id": "b", "supersedes": "a"})])
        self.store.put_many([child])
        with self.assertRaisesRegex(ValueError, "successor"):
            self.store.put_many([child.model_copy(update={"id": "branch"})])

    def test_database_prevents_two_relationship_successors(self):
        with self.store.engine.begin() as connection:
            connection.execute(insert(links).values(owner_kind="relationship", owner_id="edge-2",
                                                   target_kind="relationship", target_id="edge-1"))
        with self.assertRaises(IntegrityError):
            with self.store.engine.begin() as connection:
                connection.execute(insert(links).values(owner_kind="relationship", owner_id="edge-3",
                                                       target_kind="relationship", target_id="edge-1"))

    def test_legacy_scenario_remains_readable(self):
        payload = run_scenario(self.store, "ai-capex", 20, 24).model_dump()
        payload["propagation_version"] = "bounded-path-v1"
        self.assertEqual("bounded-path-v1", MODELS["scenario"].model_validate(payload).propagation_version)

    def test_existing_database_upgrade_preserves_legacy_payloads(self):
        legacy = Store("sqlite:///:memory:")
        try:
            legacy.initialize()
            # Simulate the original schema and relationship JSON payloads.
            for index in links.indexes:
                index.drop(legacy.engine)
            with self.store.engine.connect() as source, legacy.engine.begin() as target:
                for row in source.execute(select(entities)):
                    payload = dict(row.payload)
                    if row.kind == "relationship":
                        payload.pop("supersedes", None)
                    target.execute(insert(entities).values(kind=row.kind, id=row.id, payload=payload))
                for row in source.execute(select(links)):
                    target.execute(insert(links).values(**dict(row._mapping)))
            before = {kind: legacy.all(kind) for kind in MODELS}
            legacy.initialize()
            seed(legacy)
            self.assertEqual(before, {kind: legacy.all(kind) for kind in MODELS})
            self.assertEqual(5, len(legacy.current_relationships()))
            with legacy.engine.begin() as connection:
                connection.execute(insert(links).values(owner_kind="relationship", owner_id="edge-2",
                                                       target_kind="relationship", target_id="edge-1"))
            with self.assertRaises(IntegrityError):
                with legacy.engine.begin() as connection:
                    connection.execute(insert(links).values(owner_kind="relationship", owner_id="edge-3",
                                                           target_kind="relationship", target_id="edge-1"))
        finally:
            legacy.engine.dispose()
