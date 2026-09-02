from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator


class ConnectionCreateRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1521, ge=1, le=65535)
    service_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=1024)
    replace_connection_id: str | None = Field(default=None, min_length=32, max_length=128)

    @field_validator("host", "service_name", "username")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class CapabilityCheck(BaseModel):
    key: Literal["oracle_connection", "metadata_visibility", "schema_discovery"]
    label: str
    status: Literal["available"] = "available"


class ConnectionResponse(BaseModel):
    connection_id: str
    status: Literal["connected"] = "connected"
    expires_in_seconds: int
    checks: tuple[CapabilityCheck, ...]


class SchemaSummaryResponse(BaseModel):
    name: str
    table_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    oracle_maintained: bool


class SchemaListResponse(BaseModel):
    connection_id: str
    schemas: tuple[SchemaSummaryResponse, ...]
