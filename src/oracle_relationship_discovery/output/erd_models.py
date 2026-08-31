"""Visualization-only models shared by ERD exporters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ErdColumn:
    name: str
    data_type: str
    data_length: int | None = None
    precision: int | None = None
    scale: int | None = None
    nullable: bool = True
    position: int = 0
    pk_constraints: tuple[str, ...] = ()
    unique_constraints: tuple[str, ...] = ()
    composite_constraints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ErdTable:
    schema: str
    name: str
    columns: tuple[ErdColumn, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return self.schema, self.name


@dataclass(frozen=True, slots=True)
class ErdRelationship:
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str
    cardinality: str
    confidence_score: float
    confidence_label: str
    match_ratio: float | None = None
    validation_status: str = ""

    @property
    def cross_schema(self) -> bool:
        return self.source_schema != self.target_schema


@dataclass(frozen=True, slots=True)
class ErdModel:
    tables: tuple[ErdTable, ...]
    relationships: tuple[ErdRelationship, ...]


@dataclass(frozen=True, slots=True)
class ErdExportOptions:
    format: str = "dbml"
    scope: str = "full"
    min_confidence: float = 80
    schemas: tuple[str, ...] = ()
    max_relationships: int | None = None
    exclude_generic: bool = False
    generic_entities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ErdExportResult:
    path: Path
    format: str
    scope: str
    min_confidence: float
    relationship_count: int
    omitted_by_limit: int = 0
    unknown_cardinality_count: int = 0


class ErdExporter(Protocol):
    def export(
        self,
        model: ErdModel,
        destination: Path,
        options: ErdExportOptions,
        *,
        external_to_schema: str | None = None,
    ) -> int: ...
