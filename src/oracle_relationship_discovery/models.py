"""Domain models kept independent from Oracle and reporting code."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class KeyType(str, Enum):
    PRIMARY = "PRIMARY_KEY"
    UNIQUE = "UNIQUE_KEY"
    NONE = "NONE"
    COMPOSITE_COMPONENT = "COMPOSITE_KEY_COMPONENT"


class ValidationStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    VALIDATED = "VALIDATED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    schema: str
    table: str
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
    num_distinct: int | None = None
    num_nulls: int | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}.{self.name}"

    @property
    def key_type(self) -> KeyType:
        if self.composite_constraints:
            return KeyType.COMPOSITE_COMPONENT
        if self.pk_constraints:
            return KeyType.PRIMARY
        if self.unique_constraints:
            return KeyType.UNIQUE
        return KeyType.NONE

    @property
    def is_single_column_key(self) -> bool:
        return (
            bool(self.pk_constraints or self.unique_constraints) and not self.composite_constraints
        )


@dataclass(slots=True)
class TableMetadata:
    schema: str
    name: str
    estimated_rows: int | None = None
    last_analyzed: datetime | None = None
    columns: list[ColumnMetadata] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    name: float = 0
    datatype: float = 0
    target_key: float = 0
    overlap: float = 0
    consistency: float = 0
    structure: float = 0

    @property
    def total(self) -> float:
        return round(
            min(
                100.0,
                max(
                    0.0,
                    sum(
                        (
                            self.name,
                            self.datatype,
                            self.target_key,
                            self.overlap,
                            self.consistency,
                            self.structure,
                        )
                    ),
                ),
            ),
            2,
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "name": self.name,
            "datatype": self.datatype,
            "target_key": self.target_key,
            "overlap": self.overlap,
            "consistency": self.consistency,
            "structure": self.structure,
        }


@dataclass(slots=True)
class ValidationEvidence:
    status: ValidationStatus = ValidationStatus.NOT_RUN
    sample_size: int = 0
    matched_values: int = 0
    unmatched_values: int = 0
    match_ratio: float | None = None
    source_uniqueness_ratio: float | None = None
    target_uniqueness_ratio: float | None = None
    target_sample_size: int = 0
    source_null_ratio: float | None = None
    sampling_used: bool = False
    message: str = ""


@dataclass(slots=True)
class RelationshipCandidate:
    source: ColumnMetadata
    target: ColumnMetadata
    preliminary: ScoreBreakdown
    reasons: list[str] = field(default_factory=list)
    evidence: ValidationEvidence = field(default_factory=ValidationEvidence)
    final_score: ScoreBreakdown | None = None
    cardinality: str = "Unknown / Insufficient Evidence"
    cardinality_confidence: float = 0
    cardinality_explanation: str = "Data validation has not been performed."

    @property
    def score(self) -> float:
        return (self.final_score or self.preliminary).total

    def explanation(self) -> str:
        parts = list(self.reasons)
        if self.evidence.message:
            parts.append(self.evidence.message)
        parts.append(self.cardinality_explanation)
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class AnalysisStats:
    schemas: int
    tables: int
    columns: int
    candidates_generated: int
    candidates_validated: int
    candidates_skipped_by_limit: int = 0


def dataclass_value(value: Any) -> Any:
    """Convert enum-like values for serialization without leaking samples."""
    return value.value if isinstance(value, Enum) else value
