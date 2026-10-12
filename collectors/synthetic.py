from datetime import datetime, timezone
from pathlib import Path

from collectors.base import Collected

PILOT_CSV = Path(__file__).resolve().parents[1] / "data" / "examples" / "memory_pilot.csv"
SOURCE_URL = "synthetic://dominograph/memory-pilot-v1"


class SyntheticCollector:
    """The CLI's only default collector; reads a fixed, redistributable fixture."""

    def collect(self) -> Collected:
        return Collected(SOURCE_URL, datetime(2026, 1, 15, tzinfo=timezone.utc),
                         PILOT_CSV.read_text(encoding="utf-8"), "synthetic-csv-v1")
