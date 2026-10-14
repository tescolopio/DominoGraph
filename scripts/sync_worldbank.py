"""Download the allowlisted WDI indicators into the configured local store."""
import argparse
import json
import sys
from sqlalchemy.exc import SQLAlchemyError
from collectors.worldbank import COUNTRIES, sync_worldbank
from core.store import Store

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", choices=COUNTRIES, default="US")
    args = parser.parse_args()
    store = None
    try:
        store = Store()
        store.initialize()
        print(json.dumps(sync_worldbank(store, args.country)))
    except (ValueError, KeyError, TypeError, OverflowError, SQLAlchemyError):
        print("World Bank refresh failed. No new observations were accepted. "
              "Check configuration or source availability; inspect run history when storage is available.",
              file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if store is not None:
            store.engine.dispose()
