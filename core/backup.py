"""Consistent SQLite snapshots and validated, non-replacing workspace restores."""

import json
import os
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from core.store import Store, entities, ingestion_runs, links, references, resolve_database_url
from schemas.models import MODELS

SIDECARS = ("-wal", "-shm", "-journal")
COPY_TIMEOUT_SECONDS = 30


class WorkspaceError(ValueError):
    """An actionable diagnostic that contains no retained data or credentials."""


def _destination(path: Path) -> Path:
    destination = path.expanduser().absolute()
    if destination.name.endswith(SIDECARS):
        raise WorkspaceError("Destination must not use a SQLite sidecar filename.")
    if any(os.path.lexists(str(destination) + suffix) for suffix in ("", *SIDECARS)):
        raise WorkspaceError("Destination or its SQLite sidecars already exist; choose a new path.")
    if not destination.parent.is_dir():
        raise WorkspaceError("Destination directory does not exist; create it first.")
    return destination


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def _copy(source: Path, destination: Path):
    deadline = time.monotonic() + COPY_TIMEOUT_SECONDS

    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise WorkspaceError("Snapshot exceeded 30 seconds; retry when the workspace is less busy.")

    with closing(_read_only(source)) as reader, closing(sqlite3.connect(destination)) as writer:
        reader.backup(writer, pages=256, progress=progress, sleep=0.1)
        # A standalone snapshot must not depend on WAL files at its new location.
        mode = writer.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if mode != "delete":
            raise WorkspaceError("Could not finalize a standalone SQLite snapshot.")


def _validate(path: Path) -> dict:
    with closing(_read_only(path)) as connection:
        connection.row_factory = sqlite3.Row
        if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
            raise WorkspaceError("SQLite integrity validation failed.")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise WorkspaceError("Workspace contains broken database references.")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'") if not row[0].startswith("sqlite_")}
        required = {entities.name, links.name}
        if not required <= tables or tables - required - {ingestion_runs.name}:
            raise WorkspaceError("Unsupported workspace layout; use a compatible application version.")
        for table in (entities, links, ingestion_runs):
            if table.name in tables:
                columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table.name})")}
                if columns != set(table.c.keys()):
                    raise WorkspaceError("Unsupported workspace columns; use a compatible application version.")
        combined = {}
        counts = {kind: 0 for kind in MODELS}
        fingerprint = sha256()
        for row in connection.execute("SELECT kind, id, payload FROM entities ORDER BY kind, id"):
            if row["kind"] not in MODELS:
                raise WorkspaceError("Unsupported canonical record type.")
            if not isinstance(row["payload"], str):
                raise WorkspaceError("Canonical payload must be stored as JSON text.")
            payload = MODELS[row["kind"]].model_validate(json.loads(row["payload"])).model_dump(mode="json")
            key = (row["kind"], row["id"])
            if payload["id"] != row["id"] or key in combined:
                raise WorkspaceError("Canonical record identity validation failed.")
            combined[key] = payload
            counts[row["kind"]] += 1
            fingerprint.update(json.dumps(("entities", *tuple(row))).encode("utf-8"))
        expected = set()
        for (kind, identity), payload in combined.items():
            for target_kind, target_id in references(kind, payload):
                if (target_kind, target_id) not in combined:
                    raise WorkspaceError("Canonical record has an unresolved reference.")
                expected.add((kind, identity, target_kind, target_id))
            Store._validate_semantics(kind, payload, combined)
        actual = [tuple(row) for row in connection.execute(
            "SELECT owner_kind, owner_id, target_kind, target_id FROM entity_references "
            "ORDER BY owner_kind, owner_id, target_kind, target_id")]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise WorkspaceError("Stored provenance does not match canonical references.")
        for row in actual:
            fingerprint.update(json.dumps(("entity_references", *row)).encode("utf-8"))
        runs = 0
        if ingestion_runs.name in tables:
            identities = set()
            sequences = set()
            for row in connection.execute("SELECT * FROM ingestion_runs ORDER BY sequence"):
                _validate_run(dict(row))
                if row["id"] in identities or row["sequence"] in sequences:
                    raise WorkspaceError("Duplicate ingestion run identity.")
                identities.add(row["id"])
                sequences.add(row["sequence"])
                runs += 1
                fingerprint.update(json.dumps(("ingestion_runs", *(
                    row[field] for field in ingestion_runs.c.keys()))).encode("utf-8"))
        return {"entities": counts, "references": len(actual), "ingestion_runs": runs,
                "legacy_layout": ingestion_runs.name not in tables,
                "content_sha256": fingerprint.hexdigest()}


def _validate_run(run: dict):
    if any(not isinstance(run[field], int) or run[field] < minimum
           for field, minimum in (("sequence", 1), ("series_checked", 0),
                                  ("observations_added", 0), ("snapshots_added", 0))):
        raise WorkspaceError("Invalid ingestion run counts.")
    if any(not isinstance(run[field], str) or not run[field] for field in ("id", "connector", "country")):
        raise WorkspaceError("Invalid ingestion run identity.")
    started = datetime.fromisoformat(run["started_at"])
    finished = datetime.fromisoformat(run["finished_at"]) if run["finished_at"] else None
    if started.tzinfo is None or (finished is not None and
                                (finished.tzinfo is None or finished < started)):
        raise WorkspaceError("Invalid ingestion run chronology.")
    status = run["status"]
    if status == "running":
        valid = finished is None and run["error"] is None
    elif status == "succeeded":
        valid = finished is not None and run["error"] is None
    elif status == "failed":
        valid = (finished is not None and isinstance(run["error"], str) and bool(run["error"])
                 and run["observations_added"] == 0 and run["snapshots_added"] == 0)
    else:
        valid = False
    if not valid:
        raise WorkspaceError("Invalid ingestion run outcome.")


@contextmanager
def _staging(destination: Path):
    with NamedTemporaryFile(prefix=".dominograph-", suffix=".db", dir=destination.parent, delete=False) as file:
        temporary = Path(file.name)
    try:
        yield temporary
    finally:
        for suffix in ("", *SIDECARS):
            candidate = Path(str(temporary) + suffix)
            if candidate.exists():
                candidate.unlink()


def _publish(temporary: Path, destination: Path):
    _destination(destination)
    with temporary.open("rb+") as file:
        os.fsync(file.fileno())
    # Unlike rename/replace, a hard link atomically refuses a concurrently created destination.
    os.link(temporary, destination)


def backup_workspace(destination: Path, database_url: str | None = None) -> dict:
    url = resolve_database_url(database_url)
    if (url.drivername not in {"sqlite", "sqlite+pysqlite"} or not url.database
            or url.database == ":memory:" or url.query or url.host is not None
            or url.username is not None or url.password is not None or url.port is not None):
        raise WorkspaceError("Backup supports file-backed SQLite URLs without query parameters only.")
    source = Path(url.database)
    if not source.is_file():
        raise WorkspaceError("Configured SQLite workspace does not exist; no database was created.")
    destination = _destination(destination)
    with _staging(destination) as temporary:
        _copy(source, temporary)
        summary = _validate(temporary)
        _publish(temporary, destination)
    return {"status": "backed_up", "path": str(destination), **summary}


def restore_workspace(source: Path, destination: Path) -> dict:
    source = source.expanduser().absolute()
    if not source.is_file():
        raise WorkspaceError("Backup file does not exist.")
    destination = _destination(destination)
    with _staging(destination) as temporary:
        _copy(source, temporary)
        before = _validate(temporary)
        store = Store("sqlite:///" + str(temporary))
        try:
            store.initialize()
        finally:
            store.engine.dispose()
        after = _validate(temporary)
        if before["content_sha256"] != after["content_sha256"]:
            raise WorkspaceError("Upgrade changed retained records; restore was not published.")
        _publish(temporary, destination)
    return {"status": "restored", "path": str(destination),
            "upgraded_legacy_layout": before["legacy_layout"], **after}
