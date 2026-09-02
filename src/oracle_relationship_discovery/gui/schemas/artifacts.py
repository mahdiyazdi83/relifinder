from typing import Literal

from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    type: Literal["csv", "html", "dbml"]
    filename: str
    available: bool
    size_bytes: int | None = Field(default=None, ge=0)
    scope: str | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=100)
    eligible_relationships: int | None = Field(default=None, ge=0)
    rendered_relationships: int | None = Field(default=None, ge=0)
    unknown_cardinality_omitted: int | None = Field(default=None, ge=0)


class ArtifactListResponse(BaseModel):
    run_id: str
    artifacts: tuple[ArtifactMetadata, ...]
