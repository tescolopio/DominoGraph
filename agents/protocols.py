from enum import StrEnum
from dataclasses import dataclass
from typing import Protocol

from schemas.models import Hypothesis


class RoutingTier(StrEnum):
    DEEP_REASONING = "1_deep_reasoning"
    ANALYTICAL = "2_analytical"
    EXTRACTION = "3_extraction"
    DETERMINISTIC = "4_deterministic"
    MONITORING = "5_monitoring"


@dataclass(frozen=True)
class TaskMetadata:
    task: str
    capability: str
    complexity: int

    def __post_init__(self):
        if not 1 <= self.complexity <= 5:
            raise ValueError("complexity must be between 1 and 5")


class Research(Protocol):
    def research(self, question: str, source_ids: list[str]) -> list[str]:
        """Return existing evidence IDs; never fabricate observations."""
        ...

    def extract(self, document: str, schema: dict) -> dict:
        """Extract schema-constrained claims with document references, not new facts."""
        ...


class Reasoning(Protocol):
    def propose(self, question: str, evidence: list[dict]) -> Hypothesis: ...


class Reviewer(Protocol):
    def review(self, hypothesis: Hypothesis, evidence: list[dict]) -> dict: ...


DETERMINISTIC_TASKS = frozenset({"collect", "normalize", "validate", "score", "persist", "scenario", "export"})


def route(task: str | TaskMetadata) -> RoutingTier:
    metadata = task if isinstance(task, TaskMetadata) else None
    name = metadata.task if metadata else task
    if name in DETERMINISTIC_TASKS:
        return RoutingTier.DETERMINISTIC
    mapping = {"research": RoutingTier.ANALYTICAL, "source_compare": RoutingTier.ANALYTICAL,
               "hypothesize": RoutingTier.DEEP_REASONING, "review": RoutingTier.ANALYTICAL,
               "extract": RoutingTier.EXTRACTION, "extraction": RoutingTier.EXTRACTION,
               "monitor": RoutingTier.MONITORING, "monitoring": RoutingTier.MONITORING}
    if name not in mapping:
        raise ValueError("unknown task; no implicit AI fallback")
    tier = mapping[name]
    if metadata and tier not in {RoutingTier.MONITORING, RoutingTier.DETERMINISTIC}:
        if metadata.capability not in {"reasoning", "research", "review", "extraction", "analysis"}:
            raise ValueError("unsupported capability")
        if metadata.complexity >= 4:
            return RoutingTier.DEEP_REASONING
    return tier
