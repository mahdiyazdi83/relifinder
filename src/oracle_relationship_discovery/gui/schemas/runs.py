from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AnalysisProfile(str, Enum):
    FAST = "FAST"
    BALANCED = "BALANCED"
    THOROUGH = "THOROUGH"
    CUSTOM = "CUSTOM"


PROFILE_VALUES: dict[AnalysisProfile, dict[str, object]] = {
    AnalysisProfile.FAST: {
        "metadata_candidate_threshold": 55.0,
        "max_source_rows": 1000,
        "max_target_rows": 2000,
        "bind_batch_size": 250,
        "sampling_mode": "first",
        "max_workers": 1,
        "candidate_validation_limit": 300,
        "query_timeout_seconds": 10,
    },
    AnalysisProfile.BALANCED: {
        "metadata_candidate_threshold": 40.0,
        "max_source_rows": 3000,
        "max_target_rows": 5000,
        "bind_batch_size": 500,
        "sampling_mode": "first",
        "max_workers": 2,
        "candidate_validation_limit": 1000,
        "query_timeout_seconds": 15,
    },
    AnalysisProfile.THOROUGH: {
        "metadata_candidate_threshold": 30.0,
        "max_source_rows": 5000,
        "max_target_rows": 10000,
        "bind_batch_size": 500,
        "sampling_mode": "sample",
        "max_workers": 4,
        "candidate_validation_limit": 3000,
        "query_timeout_seconds": 30,
    },
}


class AnalysisConfiguration(BaseModel):
    profile: AnalysisProfile = AnalysisProfile.BALANCED
    metadata_candidate_threshold: float = Field(default=40, ge=0, le=100)
    min_report_confidence: float = Field(default=40, ge=0, le=100)
    sampling_enabled: bool = True
    max_source_rows: int = Field(default=3000, ge=1, le=100000)
    max_target_rows: int = Field(default=5000, ge=1, le=100000)
    bind_batch_size: int = Field(default=500, ge=1, le=1000)
    sampling_mode: Literal["first", "sample"] = "first"
    max_workers: int = Field(default=2, ge=1, le=8)
    candidate_validation_limit: int = Field(default=1000, ge=1, le=100000)
    query_timeout_seconds: int = Field(default=15, ge=1, le=300)
    erd_min_confidence: float = Field(default=80, ge=0, le=100)
    erd_scope: Literal["full", "schema", "cross-schema"] = "full"
    erd_exclude_generic: bool = False

    @model_validator(mode="after")
    def validate_profile_values(self) -> AnalysisConfiguration:
        expected = PROFILE_VALUES.get(self.profile)
        if expected:
            changed = [name for name, value in expected.items() if getattr(self, name) != value]
            if changed:
                raise ValueError(
                    "Preset profile values were modified; use the CUSTOM profile for advanced edits."
                )
        return self


class RunCreateRequest(BaseModel):
    connection_id: str = Field(min_length=16, max_length=128)
    schemas: tuple[str, ...] = Field(min_length=1, max_length=100)
    configuration: AnalysisConfiguration = Field(default_factory=AnalysisConfiguration)

    @field_validator("schemas")
    @classmethod
    def normalize_schemas(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(
            dict.fromkeys(value.strip().upper() for value in values if value.strip())
        )
        if not normalized:
            raise ValueError("At least one schema must be selected")
        return normalized


class RunState(str, Enum):
    QUEUED = "QUEUED"
    READING_METADATA = "READING_METADATA"
    BUILDING_CANDIDATES = "BUILDING_CANDIDATES"
    VALIDATING_CANDIDATES = "VALIDATING_CANDIDATES"
    SCORING = "SCORING"
    WRITING_ARTIFACTS = "WRITING_ARTIFACTS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


class RunSummary(BaseModel):
    schemas_analyzed: int = Field(ge=0)
    tables: int = Field(ge=0)
    columns: int = Field(ge=0)
    candidates_generated: int = Field(ge=0)
    candidates_validated: int = Field(ge=0)
    candidates_skipped: int = Field(ge=0)
    relationships_in_report: int = Field(ge=0)
    run_mode: Literal["sampled", "metadata-only"]
    elapsed_seconds: float = Field(ge=0)


class RunProgressEvent(BaseModel):
    sequence: int = Field(ge=0)
    run_id: str
    state: RunState
    message: str
    current: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    stats: dict[str, int] = Field(default_factory=dict)
    summary: RunSummary | None = None
    error_code: str | None = None


class RunCreateResponse(BaseModel):
    run_id: str
    status: RunState


class RunStatusResponse(RunProgressEvent):
    connection_id: str
    selected_schemas: tuple[str, ...]


class RunCancelResponse(BaseModel):
    run_id: str
    status: RunState
