from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Collected:
    source_url: str
    retrieval_time: datetime
    content: str
    collector_version: str


class Collector(Protocol):
    def collect(self) -> Collected: ...
