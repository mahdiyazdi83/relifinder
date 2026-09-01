"""Visualization-only models shared by ERD exporters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

DEFAULT_ERD_VALIDATION_STATUSES = ("VALIDATED", "NOT_RUN", "SKIPPED")


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
    validation_status: str = "NOT_RUN"
    source_datatype: str = ""
    target_datatype: str = ""
    target_key_type: str = "NONE"
    cardinality_confidence: float = 0
    cardinality_explanation: str = ""
    name_score: float = 0
    datatype_score: float = 0
    key_score: float = 0
    data_overlap_score: float = 0
    consistency_score: float = 0
    structure_score: float = 0
    sample_size: int = 0
    matched_values: int = 0
    unmatched_values: int = 0
    source_uniqueness_ratio: float | None = None
    target_uniqueness_ratio: float | None = None
    target_sample_size: int = 0
    source_null_ratio: float | None = None
    sampling_used: bool = False
    explanation: str = ""

    @property
    def cross_schema(self) -> bool:
        return self.source_schema != self.target_schema

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.source_schema,
            self.source_table,
            self.source_column,
            self.target_schema,
            self.target_table,
            self.target_column,
        )


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
    include_isolated_tables: bool = False
    validation_statuses: tuple[str, ...] = DEFAULT_ERD_VALIDATION_STATUSES


@dataclass(frozen=True, slots=True)
class ErdExportResult:
    path: Path
    format: str
    scope: str
    min_confidence: float
    eligible_relationships: int = 0
    validation_statuses: tuple[str, ...] = DEFAULT_ERD_VALIDATION_STATUSES
    input_relationships: int = 0
    duplicate_relationships_omitted: int = 0
    confidence_qualified_relationships: int = 0
    validation_qualified_relationships: int = 0
    omitted_by_validation_filter: int = 0
    omitted_by_limit: int = 0
    unknown_cardinality_relationships: int = 0
    rendered_relationships: int = 0
    included_tables: int = 0
    isolated_tables_included: int = 0

    @property
    def relationship_count(self) -> int:
        """Compatibility alias for relationships selected before cardinality rendering."""
        return self.eligible_relationships - self.omitted_by_limit

    @property
    def unknown_cardinality_count(self) -> int:
        """Compatibility alias used by callers of the first ERD implementation."""
        return self.unknown_cardinality_relationships


class ErdExporter(Protocol):
    def export(
        self,
        model: ErdModel,
        destination: Path,
        options: ErdExportOptions,
        *,
        external_to_schema: str | None = None,
    ) -> int: ...
