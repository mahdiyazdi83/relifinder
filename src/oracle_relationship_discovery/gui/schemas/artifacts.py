from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArtifactMetadata(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    type: Literal["csv", "html", "dbml"]
    filename: str
    available: bool
    size_bytes: int | None = Field(default=None, ge=0)
    scope: str | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=100)
    input_relationships: int | None = Field(default=None, ge=0)
    duplicate_relationships_omitted: int | None = Field(default=None, ge=0)
    highest_detected_confidence: float | None = Field(default=None, ge=0, le=100)
    below_confidence_threshold: int | None = Field(default=None, ge=0)
    omitted_by_validation_filter: int | None = Field(default=None, ge=0)
    omitted_by_scope_filter: int | None = Field(default=None, ge=0)
    omitted_by_generic_filter: int | None = Field(default=None, ge=0)
    omitted_by_limit: int | None = Field(default=None, ge=0)
    eligible_relationships: int | None = Field(default=None, ge=0)
    rendered_relationships: int | None = Field(default=None, ge=0)
    unknown_cardinality_omitted: int | None = Field(default=None, ge=0)


class ArtifactListResponse(BaseModel):
    run_id: str
    database_type: Literal["oracle", "postgresql", "mysql", "mariadb"]
    artifacts: tuple[ArtifactMetadata, ...]


class DbmlRegenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(ge=0, le=100)


class DbmlRegenerationResponse(ArtifactListResponse):
    generated_artifact_ids: tuple[str, ...] = Field(min_length=1)
