from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

DatabaseType = Literal["oracle", "postgresql", "mysql", "mariadb"]


class ConnectionCreateRequest(BaseModel):
    database_type: DatabaseType = "oracle"
    host: str = Field(min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    service_name: str | None = Field(default=None, max_length=128)
    database: str | None = Field(default=None, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=1024)
    replace_connection_id: str | None = Field(default=None, min_length=32, max_length=128)

    @field_validator("host", "username")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator("service_name", "database")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_database_endpoint(self):
        if self.port is None:
            self.port = {
                "oracle": 1521,
                "postgresql": 5432,
                "mysql": 3306,
                "mariadb": 3306,
            }[self.database_type]
        if self.database_type == "oracle" and not self.service_name:
            raise ValueError("service_name is required for Oracle")
        if self.database_type != "oracle" and not self.database:
            raise ValueError(f"database is required for {self.database_type}")
        return self


class CapabilityCheck(BaseModel):
    key: Literal["database_connection", "metadata_visibility", "schema_discovery"]
    label: str
    status: Literal["available"] = "available"


class ConnectionResponse(BaseModel):
    connection_id: str
    database_type: DatabaseType
    status: Literal["connected"] = "connected"
    expires_in_seconds: int
    checks: tuple[CapabilityCheck, ...]


class SchemaSummaryResponse(BaseModel):
    name: str
    table_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    system_managed: bool
    oracle_maintained: bool


class SchemaListResponse(BaseModel):
    connection_id: str
    database_type: DatabaseType
    schemas: tuple[SchemaSummaryResponse, ...]
