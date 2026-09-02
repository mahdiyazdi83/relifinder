from typing import Literal

from pydantic import BaseModel, Field

from oracle_relationship_discovery.gui.schemas.runs import RunSummary

ConfidenceLabel = Literal["HIGH", "MEDIUM-HIGH", "MEDIUM", "LOW", "VERY LOW"]
ValidationStatus = Literal["VALIDATED", "NOT_RUN", "SKIPPED", "FAILED"]
TargetKeyType = Literal["PRIMARY_KEY", "UNIQUE_KEY", "NONE", "COMPOSITE_KEY_COMPONENT"]


class RelationshipEndpoint(BaseModel):
    schema_name: str
    table_name: str
    column_name: str
    datatype: str


class RelationshipListItem(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: RelationshipEndpoint
    target: RelationshipEndpoint
    confidence_score: float = Field(ge=0, le=100)
    confidence_label: ConfidenceLabel
    cardinality: str
    validation_status: ValidationStatus
    match_ratio: float | None = Field(default=None, ge=0, le=1)
    cross_schema: bool
    target_key_type: TargetKeyType


class RelationshipScoreBreakdown(BaseModel):
    name: float = Field(ge=0)
    datatype: float = Field(ge=0)
    target_key: float = Field(ge=0)
    overlap: float = Field(ge=0)
    consistency: float = Field(ge=0)
    structure: float = Field(ge=0)


class RelationshipValidationEvidence(BaseModel):
    status: ValidationStatus
    sample_size: int = Field(ge=0)
    matched_values: int = Field(ge=0)
    unmatched_values: int = Field(ge=0)
    match_ratio: float | None = Field(default=None, ge=0, le=1)
    source_uniqueness_ratio: float | None = Field(default=None, ge=0, le=1)
    target_uniqueness_ratio: float | None = Field(default=None, ge=0, le=1)
    target_sample_size: int = Field(ge=0)
    source_null_ratio: float | None = Field(default=None, ge=0, le=1)
    sampling_used: bool


class RelationshipDetail(RelationshipListItem):
    score_breakdown: RelationshipScoreBreakdown
    validation: RelationshipValidationEvidence
    cardinality_confidence: float = Field(ge=0, le=1)
    cardinality_explanation: str
    explanation: str


class RelationshipListResponse(BaseModel):
    run_id: str
    summary: RunSummary
    total: int = Field(ge=0)
    relationships: tuple[RelationshipListItem, ...]
