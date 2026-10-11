"""Export canonical JSON schemas from Pydantic, without network access."""

import argparse
import json
from pathlib import Path

from schemas.models import CANONICAL_MODELS

ROOT = Path(__file__).resolve().parents[1]


def export(check=False):
    for model in CANONICAL_MODELS:
        path = ROOT / "schemas" / (model.__name__.lower() + ".schema.json")
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://dominograph.example/schemas/1.0.0/{path.name}"
        content = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise ValueError(f"schema out of date: {path.name}")
        else:
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    export(parser.parse_args().check)
