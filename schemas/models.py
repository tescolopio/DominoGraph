"""Canonical contracts. Source tiers indicate verification workflow, never truth."""

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"
Id = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$")]
Score = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1)]


class EvidenceState(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    CORRELATED = "correlated"
    CAUSALLY_SUPPORTED = "causally_supported"
    FORECAST = "forecast"
    ADVOCATED = "advocated"
    POLICY_PROPOSED = "policy_proposed"
    POLICY_ADOPTED = "policy_adopted"
    IMPLEMENTED = "implemented"
    DOCUMENTED_COORDINATION = "documented_coordination"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class Canonical(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: Id


class Node(Canonical):
    name: Text
    domain: Text
    geography: Text
    description: Text


class Metric(Canonical):
    node_id: Id
    name: Text
    dataset: Text
    unit: Text
    frequency: Literal["daily", "monthly", "quarterly", "annual"]
    description: Text
    baseline: float
    scale: Annotated[float, Field(gt=0)]
    contextual_direction: Literal["higher_is_pressure", "lower_is_pressure"]
    context: Text


class Source(Canonical):
    name: Text
    publisher: Text
    url: Text
    verification_tier: Literal["A", "B", "C", "D", "E", "F", "G", "H"]
    verification_notes: Text
    license: Text
    redistribution_allowed: bool
    license_url: Text
    synthetic: bool = False
    methodology: Text
    update_cadence: Text
    revision_policy: Text
    limitations: list[Text] = Field(min_length=1)


class RawSnapshot(Canonical):
    source_id: Id
    source_url: Text
    retrieval_time: datetime
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    content: str
    collector_version: Text

    @model_validator(mode="after")
    def validate_hash(self):
        from hashlib import sha256

        if sha256(self.content.encode()).hexdigest() != self.content_sha256:
            raise ValueError("raw snapshot content hash mismatch")
        if self.retrieval_time.tzinfo is None:
            raise ValueError("retrieval_time must be timezone aware")
        return self


class Observation(Canonical):
    metric_id: Id
    value: float
    source_id: Id
    source_url: Text
    retrieval_time: datetime
    publication_date: date
    observation_date: date
    vintage: Text
    collector_version: Text
    transformation_version: Text
    validation_state: Literal["valid", "quarantined", "rejected"]
    raw_snapshot_id: Id
    normalization_lineage: list[Text] = Field(min_length=1)
    revision_of: Id | None = None
    confidence: Confidence
    evidence_state: EvidenceState

    @model_validator(mode="after")
    def chronology(self):
        if self.retrieval_time.tzinfo is None:
            raise ValueError("retrieval_time must be timezone aware")
        if self.publication_date > self.retrieval_time.astimezone(timezone.utc).date():
            raise ValueError("publication_date is after retrieval")
        if self.observation_date > self.publication_date:
            raise ValueError("observation_date is after publication")
        if self.revision_of == self.id:
            raise ValueError("self revision is not allowed")
        return self


class Evidence(Canonical):
    claim: Text
    evidence_state: EvidenceState
    kind: Literal["observation", "intent"]
    polarity: Literal["supporting", "contradicting", "neutral"]
    source_id: Id
    observation_ids: list[Id]
    statement_ids: list[Id]
    confidence: Confidence
    limitations: list[Text] = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    causal_identification: Text | None = None

    @model_validator(mode="after")
    def separate_intent(self):
        if self.kind == "observation" and (not self.observation_ids or self.statement_ids):
            raise ValueError("observation evidence requires observations, not intent statements")
        if self.kind == "intent" and (not self.statement_ids or self.observation_ids):
            raise ValueError("intent evidence requires statements, not observations")
        if self.evidence_state == EvidenceState.CAUSALLY_SUPPORTED and (
            self.kind != "observation" or not self.causal_identification
            or self.review_status != ReviewStatus.APPROVED
        ):
            raise ValueError("causal evidence requires observed inputs, identification and human approval")
        if self.evidence_state == EvidenceState.DOCUMENTED_COORDINATION and (
            not self.statement_ids or self.review_status != ReviewStatus.APPROVED
        ):
            raise ValueError("coordination requires direct documented statements and human approval")
        return self


class Relationship(Canonical):
    from_node: Id
    to_node: Id
    mechanism: Text
    direction: Literal["positive", "negative", "ambiguous"]
    estimated_lag: Annotated[int, Field(ge=0, le=120)]
    confidence: Confidence
    evidence_state: EvidenceState
    evidence_ids: list[Id] = Field(min_length=1)
    counter_evidence_ids: list[Id]
    alternative_explanations: list[Text] = Field(min_length=1)
    evidence_gaps: list[Text]
    relationship_type: Literal["association", "hypothesized_transmission"] = "hypothesized_transmission"
    assumptions: list[Text] = Field(min_length=1)
    illustrative_coefficient: Annotated[float, Field(ge=0, le=1)]
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED

    @model_validator(mode="after")
    def not_causal(self):
        if self.from_node == self.to_node:
            raise ValueError("self relationship is not supported")
        if not self.counter_evidence_ids and not self.evidence_gaps:
            raise ValueError("empty relationship counter-evidence requires explicit gaps")
        if set(self.evidence_ids) & set(self.counter_evidence_ids):
            raise ValueError("relationship support and counter-evidence must be distinct")
        return self


class InstitutionalStatement(Canonical):
    institution: Text
    speaker: Text
    statement: Text
    statement_date: date
    source_id: Id
    source_url: Text
    retrieval_time: datetime
    intended_outcome: Text
    policy_id: Id | None
    evidence_state: EvidenceState
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    document: Text
    context: Text
    prediction: Text | None
    advocacy: Text | None
    policy_proposal: Text | None
    implemented_policy: Text | None
    subsequent_action: Text | None
    economic_outcome: Text | None
    confidence: Confidence

    @model_validator(mode="after")
    def aware_retrieval(self):
        if self.retrieval_time.tzinfo is None:
            raise ValueError("retrieval_time must be timezone aware")
        if self.statement_date > self.retrieval_time.astimezone(timezone.utc).date():
            raise ValueError("statement_date cannot follow retrieval")
        return self


class Intervention(Canonical):
    node_ids: list[Id] = Field(min_length=1)
    name: Text
    policy_type: Text
    description: Text
    status: Literal["proposed", "announced", "implemented", "withdrawn"]
    observation_evidence_ids: list[Id]
    intent_evidence_ids: list[Id]
    limitations: list[Text] = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


class Hypothesis(Canonical):
    statement: Text
    node_ids: list[Id] = Field(min_length=1)
    relationship_ids: list[Id]
    dataset_ids: list[Id] = Field(min_length=1)
    policy_ids: list[Id]
    institutional_statement_ids: list[Id]
    supporting_evidence_ids: list[Id]
    contradicting_evidence_ids: list[Id]
    evidence_gaps: list[Text]
    falsification_criteria: list[Text] = Field(min_length=1)
    falsification_status: Literal["untested", "not_falsified", "falsified", "inconclusive"]
    confidence: Confidence
    evidence_state: EvidenceState
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED

    @model_validator(mode="after")
    def explicit_gaps(self):
        if (not self.supporting_evidence_ids or not self.contradicting_evidence_ids) and not self.evidence_gaps:
            raise ValueError("empty evidence arrays require explicit evidence gaps")
        if set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids):
            raise ValueError("same evidence cannot support and contradict a hypothesis")
        return self


class DimensionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    score: Score | None
    confidence: Score
    observation_ids: list[Id]
    rules: list[dict]
    uncertainty: list[Text] = Field(min_length=1)


class Assessment(Canonical):
    node_id: Id
    as_of: date
    scoring_version: Literal["pilot-weighted-v1"]
    dimensions: dict[str, DimensionResult]
    pressure: Score | None
    firebreak: Score | None
    support: Score | None
    dependency: Score | None
    transmission: Score | None
    metric_ids: list[Id]
    observation_ids: list[Id]
    relationship_ids: list[Id]
    evidence_ids: list[Id]
    confidence: Score
    limitations: list[Text] = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED

    @model_validator(mode="after")
    def five_dimensions(self):
        if set(self.dimensions) != set(DIMENSIONS):
            raise ValueError(f"dimensions must be exactly {DIMENSIONS}")
        if any(getattr(self, name) != self.dimensions[name].score for name in DIMENSIONS):
            raise ValueError("top-level scores must match dimension lineage scores")
        return self


class Scenario(Canonical):
    node_id: Id
    shock: Annotated[float, Field(ge=-100, le=100)]
    horizon_months: Annotated[int, Field(ge=1, le=120)]
    kind: Literal["illustrative_not_forecast"] = "illustrative_not_forecast"
    propagation_version: Literal["bounded-path-v1"] = "bounded-path-v1"
    impacts: list[dict]
    relationship_ids: list[Id]
    evidence_ids: list[Id]
    skipped_relationships: list[dict]
    assumptions: list[Text] = Field(min_length=1)
    limitations: list[Text] = Field(min_length=1)
    confidence: Confidence
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


DIMENSIONS = ("pressure", "firebreak", "support", "dependency", "transmission")
CANONICAL_MODELS = (Node, Metric, Source, Observation, Relationship, Intervention,
                    Hypothesis, Evidence, Scenario, Assessment)
MODELS = {cls.__name__.lower(): cls for cls in (*CANONICAL_MODELS, RawSnapshot, InstitutionalStatement)}
