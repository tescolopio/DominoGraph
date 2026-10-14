import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from api.main import create_app
from api.indicators import selected_history, worldbank_refresh_status
from collectors.base import Collected
from collectors.worldbank import SERIES, WorldBankCollector, normalize, sync_worldbank
from core.store import Store, ingestion_runs
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

    def sync_at(self, checked_at, store=None, factory=None):
        with patch("collectors.worldbank.datetime", wraps=datetime) as clock:
            clock.now.return_value = checked_at
            return sync_worldbank(store or self.store, "US", factory or self.factory)

    def check_status(self, now, store=None):
        database = store or self.store
        return worldbank_refresh_status(database, "US", database.all("rawsnapshot"), now)

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
                       lambda p: p[1][0].update(value=float("nan")), lambda p: p[1][0].update(value=True),
                       lambda p: p[1].__setitem__(0, "invalid"), lambda p: p[1][0].update(indicator="invalid")):
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

    def test_unchanged_check_advances_history_without_new_vintages(self):
        first = self.sync_at(self.retrieved)
        before = {kind: self.store.all(kind) for kind in MODELS}
        later = self.retrieved + timedelta(days=1)
        second = self.sync_at(later)
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(0, second["observations_added"])
        self.assertEqual(0, second["snapshots_added"])
        self.assertEqual(before, {kind: self.store.all(kind) for kind in MODELS})
        runs = self.store.list_ingestion_runs("worldbank", "US")
        self.assertEqual({"id", "connector", "country", "started_at", "finished_at", "status",
                          "series_checked", "observations_added", "snapshots_added", "error"}, set(runs[0]))
        self.assertEqual(["succeeded", "succeeded"], [r["status"] for r in runs])
        self.assertEqual(3, runs[0]["series_checked"])
        self.assertEqual(3, runs[1]["snapshots_added"])
        check = self.check_status(later)
        self.assertEqual(later.isoformat(), check["last_checked_at"])
        self.assertEqual(self.retrieved, datetime.fromisoformat(check["last_changed_at"]))
        self.assertEqual((later + timedelta(days=7)).isoformat(), check["next_check_due_at"])

    def test_exact_seven_day_boundary_is_about_checks_not_reference_years(self):
        self.sync_at(self.retrieved)
        deadline = self.retrieved + timedelta(days=7)
        self.assertEqual("fresh", self.check_status(deadline - timedelta(microseconds=1))["check_status"])
        self.assertEqual("stale", self.check_status(deadline)["check_status"])
        self.assertEqual("stale", self.check_status(deadline + timedelta(microseconds=1))["check_status"])
        self.assertEqual(7, self.check_status(deadline)["check_interval_days"])

    def test_failure_is_sanitized_and_does_not_reset_success_or_change_data(self):
        self.sync_at(self.retrieved)
        before = {kind: self.store.all(kind) for kind in MODELS}
        self.values = [3, 2, None]
        def failing(country, indicator):
            if indicator == list(SERIES)[1]:
                raise ValueError("private-token=do-not-retain")
            return self.factory(country, indicator)
        later = self.retrieved + timedelta(days=8)
        with self.assertLogs("collectors.worldbank", level="WARNING") as logs:
            with self.assertRaises(ValueError):
                self.sync_at(later, factory=failing)
        check = self.check_status(later)
        self.assertEqual("stale", check["check_status"])
        self.assertEqual(self.retrieved.isoformat(), check["last_checked_at"])
        self.assertEqual(self.retrieved, datetime.fromisoformat(check["last_changed_at"]))
        run = check["latest_run"]
        self.assertEqual("failed", run["status"])
        self.assertEqual(1, run["series_checked"])
        self.assertEqual(0, run["observations_added"])
        self.assertEqual(0, run["snapshots_added"])
        self.assertEqual(later.isoformat(), run["finished_at"])
        self.assertNotIn("private-token", json.dumps(check) + "".join(logs.output))
        self.assertEqual(before, {kind: self.store.all(kind) for kind in MODELS})

    def test_success_data_and_run_completion_share_one_transaction(self):
        original_finish = self.store._finish_ingestion_run
        def fail_success(connection, identity, finished_at, status, *args):
            if status == "succeeded":
                raise ValueError("completion rejected")
            return original_finish(connection, identity, finished_at, status, *args)
        with patch.object(self.store, "_finish_ingestion_run", side_effect=fail_success):
            with self.assertRaisesRegex(ValueError, "completion rejected"):
                self.sync_at(self.retrieved)
        self.assertTrue(all(not self.store.all(kind) for kind in MODELS))
        run = self.store.list_ingestion_runs("worldbank", "US")[0]
        self.assertEqual("failed", run["status"])
        self.assertEqual(3, run["series_checked"])
        self.assertEqual(0, run["observations_added"])

    def test_failed_first_refresh_is_visible_without_indicators(self):
        def failing(country, indicator):
            raise ValueError("private-token=do-not-retain")
        with TestClient(create_app(self.store)) as client:
            with patch("api.indicators.sync_worldbank",
                       side_effect=lambda store, country: self.sync_at(self.retrieved, store, failing)):
                response = client.post("/api/connectors/worldbank/refresh",
                                       headers={"X-DominoGraph-Request": "1"}, json={"country": "US"})
            self.assertEqual(502, response.status_code)
            catalog = client.get("/api/indicators").json()
            self.assertEqual([], catalog["indicators"])
            self.assertEqual("never_checked", catalog["refreshes"]["US"]["check_status"])
            self.assertEqual("failed", catalog["refreshes"]["US"]["latest_run"]["status"])
            self.assertIsNone(catalog["refreshes"]["CA"]["latest_run"])
            self.assertNotIn("private-token", response.text + json.dumps(catalog))
            self.assertIn("Current workspace source checks", client.get("/").text)

    def test_success_selection_is_not_limited_to_recent_history_and_runs_paginate(self):
        self.sync_at(self.retrieved)
        for i in range(12):
            at = self.retrieved + timedelta(days=i + 1)
            identity = self.store.start_ingestion_run("worldbank", "US", at)
            self.store.fail_ingestion_run(identity, at, 0, "Source unavailable.")
        check = self.check_status(at)
        self.assertEqual(10, len(check["recent_runs"]))
        self.assertEqual(self.retrieved.isoformat(), check["last_checked_at"])
        self.assertEqual("stale", check["check_status"])
        with TestClient(create_app(self.store)) as client:
            path = "/api/connectors/worldbank/runs"
            page = client.get(path + "?country=US&limit=10").json()
            self.assertEqual(10, len(page["runs"]))
            self.assertTrue(page["has_more"])
            tail = client.get(path + "?country=US&limit=10&offset=10").json()
            self.assertEqual(3, len(tail["runs"]))
            self.assertFalse(tail["has_more"])
            self.assertEqual("succeeded", tail["runs"][-1]["status"])
            self.assertEqual([], client.get(path + "?country=CA").json()["runs"])
            for query in ("?country=XX", "?limit=0", "?limit=101", "?offset=-1"):
                self.assertEqual(422, client.get(path + query).status_code)

    def test_restart_preserves_success_failure_and_unfinished_attempts(self):
        with TemporaryDirectory() as directory:
            url = "sqlite:///" + str(Path(directory) / "history.db")
            first = Store(url)
            first.initialize()
            try:
                self.sync_at(self.retrieved, first)
                at = self.retrieved + timedelta(days=1)
                identity = first.start_ingestion_run("worldbank", "US", at)
                first.fail_ingestion_run(identity, at, 0, "Source unavailable.")
                first.start_ingestion_run("worldbank", "CA", at)
                before = {kind: first.all(kind) for kind in MODELS}
                history = first.list_ingestion_runs("worldbank")
            finally:
                first.engine.dispose()
            reopened = Store(url)
            try:
                reopened.initialize()
                self.assertEqual(before, {kind: reopened.all(kind) for kind in MODELS})
                self.assertEqual(history, reopened.list_ingestion_runs("worldbank"))
                self.assertEqual("failed", self.check_status(at, reopened)["latest_run"]["status"])
                with TestClient(create_app(reopened)) as client:
                    status = client.get("/api/indicators").json()["refreshes"]["CA"]
                    self.assertEqual("never_checked", status["check_status"])
                    self.assertEqual("running", status["latest_run"]["status"])
                    self.assertIsNone(status["latest_run"]["finished_at"])
            finally:
                reopened.engine.dispose()

    def test_additive_upgrade_does_not_invent_legacy_check_history(self):
        seed(self.store)
        self.sync_at(self.retrieved)
        before = {kind: self.store.all(kind) for kind in MODELS}
        ingestion_runs.drop(self.store.engine)
        self.store.initialize()
        self.store.initialize()
        self.assertEqual(before, {kind: self.store.all(kind) for kind in MODELS})
        check = self.check_status(self.retrieved)
        self.assertEqual("never_checked", check["check_status"])
        self.assertIsNone(check["last_checked_at"])
        self.assertEqual(self.retrieved, datetime.fromisoformat(check["last_changed_at"]))

    def test_historical_detail_does_not_use_current_check_history_as_a_vintage(self):
        self.sync_at(self.retrieved)
        later = self.retrieved + timedelta(days=1)
        self.sync_at(later)
        with TestClient(create_app(self.store)) as client:
            detail = client.get("/api/indicators/wb-US-NY.GDP.MKTP.KD.ZG?as_of=2025-01-01").json()
            self.assertEqual([], detail["points"])
            self.assertEqual([], detail["snapshots"])
            self.assertEqual("US", detail["refresh"]["country"])
            self.assertEqual(later.isoformat(), detail["refresh"]["last_checked_at"])
        self.assertEqual(3, len(self.store.all("rawsnapshot")))

    def test_completed_run_cannot_be_rewritten(self):
        result = self.sync_at(self.retrieved)
        history = self.store.list_ingestion_runs("worldbank", "US")
        with self.assertRaisesRegex(ValueError, "already finished"):
            self.store.fail_ingestion_run(result["run_id"], self.retrieved, 0, "Not allowed.")
        self.assertEqual(history, self.store.list_ingestion_runs("worldbank", "US"))

    def test_storage_failure_is_recorded_with_sanitized_error(self):
        with patch.object(self.store, "complete_ingestion_run",
                          side_effect=SQLAlchemyError("private-password=do-not-retain")):
            with self.assertLogs("collectors.worldbank", level="WARNING") as logs:
                with self.assertRaises(SQLAlchemyError):
                    self.sync_at(self.retrieved)
        run = self.store.list_ingestion_runs("worldbank", "US")[0]
        self.assertEqual("failed", run["status"])
        self.assertIn("Could not save imported data", run["error"])
        self.assertNotIn("private-password", json.dumps(run) + "".join(logs.output))
        self.assertTrue(all(not self.store.all(kind) for kind in MODELS))

    def test_finish_time_validation_preserves_running_attempt(self):
        identity = self.store.start_ingestion_run("worldbank", "US", self.retrieved)
        for end in (self.retrieved.replace(tzinfo=None), self.retrieved - timedelta(seconds=1)):
            with self.assertRaises(ValueError):
                self.store.fail_ingestion_run(identity, end, 0, "Source unavailable.")
        run = self.store.list_ingestion_runs("worldbank", "US")[0]
        self.assertEqual("running", run["status"])
        self.assertIsNone(run["finished_at"])

    def test_cli_reports_configuration_failure_without_secret_traceback(self):
        environment = dict(os.environ, DATABASE_URL="unknown-driver://private-password-do-not-retain")
        result = subprocess.run([sys.executable, "-m", "scripts.sync_worldbank", "--country", "US"],
                                cwd=Path(__file__).resolve().parents[1], env=environment,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(1, result.returncode)
        self.assertIn("World Bank refresh failed", result.stderr)
        self.assertNotIn("private-password", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
