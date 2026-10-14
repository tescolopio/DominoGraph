"""Back up configured SQLite storage or restore a backup to a new database."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from core.backup import WorkspaceError, backup_workspace, restore_workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a consistent snapshot of DATABASE_URL.")
    backup.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore", help="Validate and restore into a new SQLite file.")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (backup_workspace(args.output) if args.command == "backup"
                  else restore_workspace(args.backup, args.output))
    except WorkspaceError as error:
        print(f"Workspace {args.command} failed: {error}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error, SQLAlchemyError, ValueError, TypeError, KeyError):
        print(f"Workspace {args.command} failed. Check storage access, available space, "
              "backup integrity, and application compatibility. Existing files were not replaced.",
              file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
