import json
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import create_app
from api.indicators import selected_history
from collectors.base import Collected
from collectors.worldbank import SERIES, WorldBankCollector, normalize, sync_worldbank
from core.store import Store
from schemas.models import MODELS
from scripts.seed import seed
from transforms.normalize import snapshot


class IndicatorTests(TestCase):
    def setUp(self):
        self.store = Store("sqlite:///:memory:")
        self.store.initialize()
        self.retrieved = datetime(2026, 1, 15, tzinfo=timezone.utc)
        self.values = [2.5, 2.0, None]

    def tearDown(self):
        self.store.engine.dispose()

    def factory(self, country, indicator):
        collector = WorldBankCollector(country, indicator)
        rows = [{"indicator": {"id": indicator}, "countryiso3code": "USA", "date": str(2025-i), "value": value}
                for i, value in enumerate(self.values)]
        content = json.dumps([{"pages": 1, "total": len(rows), "sourceid": "2", "lastupdated": "2026-01-10"}, rows])
        collector.collect = lambda: Collected(collector.url, self.retrieved, content, "worldbank-wdi-v1")
        return collector

    def sync(self):
        return sync_worldbank(self.store, "US", self.factory)

    def test_atomic_import_and_unchanged_retry(self):
        self.assertEqual(6, self.sync()["observations_added"])
        before = {kind: self.store.all(kind) for kind in MODELS}
        self.retrieved = datetime(2026, 2, 15, tzinfo=timezone.utc)
        self.assertEqual(0, self.sync()["observations_added"])
        self.assertEqual(before, {kind: self.store.all(kind) for kind in MODELS})
        self.assertTrue(all(o["publication_date"] is None for o in self.store.all("observation")))
        self.assertTrue(all(m["baseline"] is None for m in self.store.all("metric")))

    def test_refresh_failure_does_not_partially_write(self):
        self.sync()
        before = self.store.all("observation")
        self.values = [3, 2, None]
        def failing(country, indicator):
            if indicator == list(SERIES)[1]:
                raise ValueError("source unavailable")
            return self.factory(country, indicator)
        with self.assertRaises(ValueError):
            sync_worldbank(self.store, "US", failing)
        self.assertEqual(before, self.store.all("observation"))

    def test_vintages_cutoff_and_withdrawal(self):
        self.sync()
        metric = "wb-US-NY.GDP.MKTP.KD.ZG"
        original = selected_history(self.store, metric)[0]
        self.values = [None, 1.5, None]
        self.retrieved = datetime(2026, 2, 15, tzinfo=timezone.utc)
        self.sync()
        current = selected_history(self.store, metric)[0]
        self.assertEqual([1.5], [o["value"] for o in current])
        self.assertEqual("2024-12-31", current[0]["observation_date"])
        self.assertIsNotNone(current[0]["revision_of"])
        self.assertEqual(original, selected_history(self.store, metric, datetime(2026, 1, 31).date())[0])
        self.assertEqual([], selected_history(self.store, metric, datetime(2025, 12, 31).date())[0])
        # A source reverting to an earlier response is a new revision, not a skipped download.
        self.values = [2.5, 2.0, None]
        self.retrieved = datetime(2026, 3, 15, tzinfo=timezone.utc)
        self.assertEqual(6, self.sync()["observations_added"])
        self.assertEqual([2, 2.5], [o["value"] for o in selected_history(self.store, metric)[0]])

    def test_bad_payloads_and_allowlist(self):
        code = next(iter(SERIES))
        raw = snapshot(self.factory("US", code).collect(), "test-source")
        payload = json.loads(raw.content)
        for mutate in (lambda p: p[0].update(pages=2), lambda p: p[1][0].update(countryiso3code="CAN"),
                       lambda p: p[1][0].update(value=float("nan")), lambda p: p[1][0].update(value=True)):
            candidate = json.loads(raw.content)
            mutate(candidate)
            with self.subTest(payload=candidate), self.assertRaises(ValueError):
                normalize(raw.model_copy(update={"content": json.dumps(candidate)}), "US", code)
        with self.assertRaises(ValueError):
            WorldBankCollector("https://example.com", code)
        with self.assertRaises(ValueError):
            WorldBankCollector("US", "unknown")

    def test_api_isolates_demo_and_shows_provenance(self):
        seed(self.store)
        self.sync()
        with TestClient(create_app(self.store)) as client:
            catalog = client.get("/api/indicators").json()
            self.assertEqual(3, len(catalog["indicators"]))
            self.assertTrue(all(not r["metric"]["id"].startswith("dram") for r in catalog["indicators"]))
            identity = catalog["indicators"][0]["metric"]["id"]
            detail = client.get("/api/indicators/" + identity).json()
            self.assertEqual(2, len(detail["points"]))
            observation = detail["points"][0]
            trace = client.get("/api/provenance/observation/" + observation["id"]).json()
            self.assertIn("rawsnapshot", {r["entity_type"] for r in trace["lineage"]})
            self.assertEqual([], client.get("/api/indicators/" + identity + "?as_of=2025-01-01").json()["points"])
            self.assertEqual(422, client.get("/api/indicators/" + identity + "?as_of=bad").status_code)
            self.assertEqual(404, client.get("/api/indicators/missing").status_code)
            self.assertIn("Economic indicators", client.get("/").text)
            self.assertIn("Synthetic demonstration", client.get("/pilot").text)

    def test_refresh_rejects_foreign_origins_and_bad_countries(self):
        with TestClient(create_app(self.store)) as client:
            path = "/api/connectors/worldbank/refresh"
            self.assertEqual(403, client.post(path, json={"country": "US"}).status_code)
            headers = {"X-DominoGraph-Request": "1", "Origin": "https://example.com"}
            self.assertEqual(403, client.post(path, headers=headers, json={"country": "US"}).status_code)
            headers["Origin"] = "http://testserver"
            self.assertEqual(422, client.post(path, headers=headers, json={"country": "XX"}).status_code)
            with patch("api.indicators.sync_worldbank", return_value={"series": 3}) as sync:
                self.assertEqual(200, client.post(path, headers=headers, json={"country": "US"}).status_code)
                sync.assert_called_once()
            with patch("api.indicators.sync_worldbank", side_effect=ValueError("bad data")):
                self.assertEqual(502, client.post(path, headers=headers, json={"country": "US"}).status_code)
            self.assertEqual(400, client.get("/health", headers={"Host": "attacker.example"}).status_code)
