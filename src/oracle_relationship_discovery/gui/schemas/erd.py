from pydantic import BaseModel, Field

from oracle_relationship_discovery.gui.schemas.relationships import RelationshipListItem


class ErdGraphColumn(BaseModel):
    name: str
    datatype: str
    nullable: bool
    position: int = Field(ge=0)
    primary_key: bool
    unique_key: bool
    composite_key: bool
    relationship_connected: bool


class ErdGraphTable(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_name: str
    table_name: str
    estimated_rows: int | None = Field(default=None, ge=0)
    columns: tuple[ErdGraphColumn, ...]


class ErdGraphResponse(BaseModel):
    run_id: str
    default_min_confidence: float = Field(ge=0, le=100)
    schemas: tuple[str, ...]
    tables: tuple[ErdGraphTable, ...]
    relationships: tuple[RelationshipListItem, ...]
