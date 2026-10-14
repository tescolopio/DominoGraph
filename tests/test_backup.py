"""File-backed recovery, non-destructive failure, and additive upgrade coverage."""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.indicators import selected_history
from api.main import create_app
from collectors.base import Collected
from collectors.worldbank import WorldBankCollector, sync_worldbank
from core.backup import WorkspaceError, backup_workspace, restore_workspace
from core.store import ROOT, Store, ingestion_runs, links
from schemas.models import MODELS
from scripts.seed import seed


class BackupTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "workspace.db"
        self.url = "sqlite:///" + str(self.path)
        self.store = Store(self.url)
        self.addCleanup(self.store.engine.dispose)
        seed(self.store)
        self.value = 2.5
        self.retrieved = datetime(2026, 1, 15, tzinfo=timezone.utc)

    def factory(self, country, indicator):
        collector = WorldBankCollector(country, indicator)
        content = json.dumps([{"pages": 1, "total": 1, "sourceid": "2", "lastupdated": "2026-01-10"},
                              [{"indicator": {"id": indicator}, "countryiso3code": "USA",
                                "date": "2025", "value": self.value}]])
        collector.collect = lambda: Collected(collector.url, self.retrieved, content, "worldbank-wdi-v1")
        return collector

    def populate(self):
        sync_worldbank(self.store, "US", self.factory)
        self.value = 3.0
        self.retrieved += timedelta(days=31)
        sync_worldbank(self.store, "US", self.factory)
        sync_worldbank(self.store, "US", self.factory)
        at = datetime.now(timezone.utc)
        failed = self.store.start_ingestion_run("worldbank", "US", at)
        self.store.fail_ingestion_run(failed, at, 0, "Source unavailable.")
        self.store.start_ingestion_run("worldbank", "CA", at)

    def records(self, store):
        return {kind: store.all(kind) for kind in MODELS}

    def raw_rows(self, path):
        with closing(sqlite3.connect(path)) as connection:
            return connection.execute("SELECT kind, id, payload FROM entities ORDER BY kind, id").fetchall()

    def assert_no_staging(self):
        self.assertEqual([], list(self.root.glob(".dominograph-*")))

    def test_round_trip_preserves_exact_records_provenance_history_and_restart(self):
        self.populate()
        before = self.records(self.store)
        runs = self.store.list_ingestion_runs("worldbank")
        observation = self.store.all("observation")[0]
        lineage = self.store.provenance("observation", observation["id"])
        raw_rows = self.raw_rows(self.path)
        backup = self.root / "backup.db"
        restored = self.root / "restored.db"
        result = backup_workspace(backup, self.url)
        self.assertEqual(5, result["ingestion_runs"])
        self.assertFalse(result["legacy_layout"])
        fingerprint = result["content_sha256"]
        result = restore_workspace(backup, restored)
        self.assertFalse(result["upgraded_legacy_layout"])
        self.assertEqual(fingerprint, result["content_sha256"])
        self.assertEqual(raw_rows, self.raw_rows(backup))
        self.assertEqual(raw_rows, self.raw_rows(restored))
        for _ in range(2):
            reopened = Store("sqlite:///" + str(restored))
            try:
                with TestClient(create_app(reopened)) as client:
                    self.assertEqual(before, self.records(reopened))
                    self.assertEqual(runs, reopened.list_ingestion_runs("worldbank"))
                    self.assertEqual(lineage, client.get(
                        "/api/provenance/observation/" + observation["id"]).json())
                    self.assertEqual(200, client.get("/").status_code)
                    self.assertEqual(200, client.get("/pilot").status_code)
                    self.assertEqual("running", client.get("/api/indicators").json()[
                        "refreshes"]["CA"]["latest_run"]["status"])
                    historical = selected_history(reopened, "wb-US-NY.GDP.MKTP.KD.ZG",
                                                  datetime(2026, 1, 31).date())[0]
                    self.assertEqual([2.5], [item["value"] for item in historical])
                with reopened.engine.begin() as connection, self.assertRaises(IntegrityError):
                    connection.exec_driver_sql("DELETE FROM entities")
            finally:
                reopened.engine.dispose()
        self.assert_no_staging()

    def test_hard_link_destination_alias_is_protected(self):
        alias = self.root / "alias.db"
        os.link(self.path, alias)
        before = self.path.read_bytes()
        with self.assertRaises(WorkspaceError):
            backup_workspace(alias, self.url)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(before, alias.read_bytes())

    def test_backup_includes_committed_wal_but_not_uncommitted_transaction(self):
        with closing(sqlite3.connect(self.path)) as writer:
            self.assertEqual("wal", writer.execute("PRAGMA journal_mode=WAL").fetchone()[0])
            at = datetime.now(timezone.utc)
            identity = self.store.start_ingestion_run("worldbank", "US", at)
            writer.execute("UPDATE ingestion_runs SET series_checked=1 WHERE id=?", (identity,))
            backup = self.root / "wal-backup.db"
            backup_workspace(backup, self.url)
            with closing(sqlite3.connect(backup)) as reader:
                self.assertEqual(0, reader.execute(
                    "SELECT series_checked FROM ingestion_runs WHERE id=?", (identity,)).fetchone()[0])
                self.assertEqual("delete", reader.execute("PRAGMA journal_mode").fetchone()[0])
            writer.rollback()
            for suffix in ("-wal", "-shm", "-journal"):
                self.assertFalse(Path(str(backup) + suffix).exists())
        self.assert_no_staging()

    def test_legacy_restore_adds_history_and_guards_without_rewriting_payloads(self):
        self.populate()
        ingestion_runs.drop(self.store.engine)
        for index in links.indexes:
            index.drop(self.store.engine)
        with self.store.engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER immutable_entities_update")
            connection.exec_driver_sql("DROP TRIGGER immutable_entities_delete")
            for payload in self.store.all("relationship"):
                payload.pop("supersedes", None)
                connection.exec_driver_sql("UPDATE entities SET payload=? WHERE kind='relationship' AND id=?",
                                           (json.dumps(payload), payload["id"]))
        original = self.raw_rows(self.path)
        backup = self.root / "legacy.db"
        restored = self.root / "upgraded.db"
        self.assertTrue(backup_workspace(backup, self.url)["legacy_layout"])
        self.assertTrue(restore_workspace(backup, restored)["upgraded_legacy_layout"])
        self.assertEqual(original, self.raw_rows(backup))
        self.assertEqual(original, self.raw_rows(restored))
        reopened = Store("sqlite:///" + str(restored))
        try:
            reopened.initialize()
            reopened.initialize()
            self.assertEqual([], reopened.list_ingestion_runs("worldbank"))
            with TestClient(create_app(reopened)) as client:
                self.assertEqual("never_checked", client.get("/api/indicators").json()[
                    "refreshes"]["US"]["check_status"])
            with reopened.engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO entity_references VALUES ('relationship','edge-2','relationship','edge-1')")
            with reopened.engine.begin() as connection, self.assertRaises(IntegrityError):
                connection.exec_driver_sql(
                    "INSERT INTO entity_references VALUES ('relationship','edge-3','relationship','edge-1')")
            with reopened.engine.begin() as connection, self.assertRaises(IntegrityError):
                connection.exec_driver_sql("UPDATE entities SET payload='{}'")
        finally:
            reopened.engine.dispose()
        self.assert_no_staging()

    def test_existing_destinations_and_aliases_are_never_replaced(self):
        backup = self.root / "backup.db"
        backup_workspace(backup, self.url)
        for operation, source in ((backup_workspace, self.url), (restore_workspace, backup)):
            for destination in (backup, self.path):
                before = destination.read_bytes()
                with self.assertRaises(WorkspaceError):
                    if operation == backup_workspace:
                        operation(destination, source)
                    else:
                        operation(source, destination)
                self.assertEqual(before, destination.read_bytes())
        self.assert_no_staging()

    def test_sidecars_and_reserved_filenames_are_rejected(self):
        for suffix in ("-wal", "-shm", "-journal"):
            destination = self.root / ("restore" + suffix + ".db")
            sidecar = Path(str(destination) + suffix)
            sidecar.write_bytes(b"existing sidecar")
            with self.assertRaises(WorkspaceError):
                backup_workspace(destination, self.url)
            self.assertEqual(b"existing sidecar", sidecar.read_bytes())
            self.assertFalse(destination.exists())
            with self.assertRaises(WorkspaceError):
                backup_workspace(self.root / ("reserved.db" + suffix), self.url)

    def test_missing_workspace_is_not_created_and_unsupported_urls_fail(self):
        missing = self.root / "missing.db"
        output = self.root / "output.db"
        for url in ("sqlite:///" + str(missing), "sqlite:///:memory:", "sqlite://",
                    "postgresql://user:private-password@localhost/db",
                    "sqlite://user:private-password@localhost/workspace.db",
                    self.url + "?mode=memory&uri=true"):
            with self.assertRaises(WorkspaceError):
                backup_workspace(output, url)
        self.assertFalse(missing.exists())
        self.assertFalse(output.exists())
        self.assert_no_staging()

    def test_missing_backup_and_output_directory_fail(self):
        with self.assertRaises(WorkspaceError):
            restore_workspace(self.root / "absent.db", self.root / "restored.db")
        with self.assertRaises(WorkspaceError):
            backup_workspace(self.root / "absent-directory" / "backup.db", self.url)
        self.assertFalse((self.root / "absent-directory").exists())

    def test_corrupt_foreign_and_future_layouts_are_not_published(self):
        for name in ("corrupt", "foreign", "future"):
            source = self.root / (name + ".db")
            if name == "corrupt":
                source.write_bytes(b"not a SQLite database")
            else:
                with closing(sqlite3.connect(source)) as connection:
                    connection.execute("CREATE TABLE unexpected (id INTEGER)")
            if name == "future":
                source.unlink()
                backup_workspace(source, self.url)
                with closing(sqlite3.connect(source)) as connection:
                    connection.execute("ALTER TABLE entities ADD COLUMN future_field TEXT")
            before = source.read_bytes()
            destination = self.root / (name + "-restored.db")
            with self.assertRaises((WorkspaceError, sqlite3.Error)):
                restore_workspace(source, destination)
            self.assertEqual(before, source.read_bytes())
            self.assertFalse(destination.exists())
            self.assert_no_staging()

    def test_missing_provenance_is_rejected(self):
        backup = self.root / "bad-provenance.db"
        backup_workspace(backup, self.url)
        with closing(sqlite3.connect(backup)) as connection:
            connection.execute("DELETE FROM entity_references")
            connection.commit()
        with self.assertRaisesRegex(WorkspaceError, "provenance"):
            restore_workspace(backup, self.root / "restored.db")
        self.assert_no_staging()

    def test_broken_foreign_keys_and_future_canonical_versions_are_rejected(self):
        for name in ("foreign-key", "canonical-version"):
            backup = self.root / (name + ".db")
            backup_workspace(backup, self.url)
            with closing(sqlite3.connect(backup)) as connection:
                if name == "foreign-key":
                    connection.execute("UPDATE entity_references SET target_id='missing' WHERE rowid="
                                       "(SELECT min(rowid) FROM entity_references)")
                else:
                    connection.execute("DROP TRIGGER immutable_entities_update")
                    payload = dict(self.store.all("node")[0], schema_version="99.0.0")
                    connection.execute("UPDATE entities SET payload=? WHERE kind='node' AND id=?",
                                       (json.dumps(payload), payload["id"]))
                connection.commit()
            with self.assertRaises(ValueError):
                restore_workspace(backup, self.root / (name + "-restored.db"))
            self.assertFalse((self.root / (name + "-restored.db")).exists())
            self.assert_no_staging()

    def test_invalid_run_chronology_is_rejected(self):
        at = datetime.now(timezone.utc)
        identity = self.store.start_ingestion_run("worldbank", "US", at)
        self.store.fail_ingestion_run(identity, at, 0, "Unavailable.")
        backup = self.root / "bad-history.db"
        backup_workspace(backup, self.url)
        with closing(sqlite3.connect(backup)) as connection:
            connection.execute("UPDATE ingestion_runs SET finished_at=? WHERE id=?",
                               ((at - timedelta(days=1)).isoformat(), identity))
            connection.commit()
        with self.assertRaisesRegex(WorkspaceError, "chronology"):
            restore_workspace(backup, self.root / "restored.db")
        self.assert_no_staging()

    def test_upgrade_failure_does_not_publish_or_change_backup(self):
        backup = self.root / "backup.db"
        backup_workspace(backup, self.url)
        before = backup.read_bytes()
        with patch("core.backup.Store.initialize", side_effect=SQLAlchemyError("storage unavailable")):
            with self.assertRaises(SQLAlchemyError):
                restore_workspace(backup, self.root / "restored.db")
        self.assertEqual(before, backup.read_bytes())
        self.assertFalse((self.root / "restored.db").exists())
        self.assert_no_staging()

    def test_same_count_payload_change_during_upgrade_is_rejected(self):
        backup = self.root / "backup.db"
        backup_workspace(backup, self.url)
        initialize = Store.initialize
        def changing_initialize(store):
            initialize(store)
            with store.engine.begin() as connection:
                connection.exec_driver_sql("DROP TRIGGER immutable_entities_update")
                payload = dict(store.all("node")[0], name="Altered during upgrade")
                connection.exec_driver_sql("UPDATE entities SET payload=? WHERE kind='node' AND id=?",
                                           (json.dumps(payload), payload["id"]))
        with patch("core.backup.Store.initialize", changing_initialize):
            with self.assertRaisesRegex(WorkspaceError, "changed retained records"):
                restore_workspace(backup, self.root / "restored.db")
        self.assertFalse((self.root / "restored.db").exists())
        self.assert_no_staging()

    def test_publish_failure_and_destination_race_clean_staging(self):
        destination = self.root / "backup.db"
        with patch("core.backup.os.link", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                backup_workspace(destination, self.url)
        self.assertFalse(destination.exists())
        self.assert_no_staging()
        link = os.link
        def racing_link(source, target):
            target.write_bytes(b"another writer")
            link(source, target)
        with patch("core.backup.os.link", side_effect=racing_link):
            with self.assertRaises(FileExistsError):
                backup_workspace(destination, self.url)
        self.assertEqual(b"another writer", destination.read_bytes())
        self.assert_no_staging()

    def test_copy_timeout_does_not_publish_partial_backup(self):
        with patch("core.backup.time.monotonic", side_effect=[0, 31]):
            with self.assertRaisesRegex(WorkspaceError, "30 seconds"):
                backup_workspace(self.root / "timeout.db", self.url)
        self.assertFalse((self.root / "timeout.db").exists())
        self.assert_no_staging()

    def test_configured_relative_database_resolves_from_repository(self):
        with patch("core.store.ROOT", self.root):
            result = backup_workspace(self.root / "backup.db", "sqlite:///workspace.db")
        self.assertEqual("backed_up", result["status"])
        self.assertEqual(len(self.store.all("observation")), result["entities"]["observation"])

    def test_cli_round_trip_and_secret_free_failure(self):
        environment = dict(os.environ, DATABASE_URL=self.url)
        backup = self.root / "cli.db"
        restored = self.root / "cli-restored.db"
        def command(*args, env=environment):
            return subprocess.run([sys.executable, "-m", "scripts.workspace", *args],
                                  cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
        result = command("backup", "--output", str(backup))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("backed_up", json.loads(result.stdout)["status"])
        result = command("restore", "--backup", str(backup), "--output", str(restored))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("restored", json.loads(result.stdout)["status"])
        result = command("restore", "--backup", str(backup), "--output", str(restored))
        self.assertEqual(1, result.returncode)
        self.assertIn("already exist", result.stderr)
        result = command("backup", "--output", str(self.root / "bad.db"),
                         env=dict(environment, DATABASE_URL="invalid-driver://private-password-do-not-retain"))
        self.assertEqual(1, result.returncode)
        self.assertNotIn("private-password", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assert_no_staging()
