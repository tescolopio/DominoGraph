"""Download the allowlisted WDI indicators into the configured local store."""
import argparse
import json
from collectors.worldbank import COUNTRIES, sync_worldbank
from core.store import Store

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", choices=COUNTRIES, default="US")
    args = parser.parse_args()
    store = Store()
    try:
        store.initialize()
        print(json.dumps(sync_worldbank(store, args.country)))
    finally:
        store.engine.dispose()
