"""Oracle datatype family and compatibility rules."""

from __future__ import annotations

from dataclasses import dataclass

from oracle_relationship_discovery.models import ColumnMetadata

NUMERIC = {"NUMBER", "FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE", "INTEGER", "DECIMAL"}
TEXT = {"CHAR", "NCHAR", "VARCHAR", "VARCHAR2", "NVARCHAR2"}
DATE_TIME = {"DATE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP WITH LOCAL TIME ZONE"}
RAW = {"RAW", "LONG RAW"}


def datatype_family(data_type: str) -> str:
    normalized = data_type.upper().strip()
    if normalized in NUMERIC:
        return "NUMERIC"
    if normalized in TEXT:
        return "TEXT"
    if normalized in DATE_TIME or normalized.startswith("TIMESTAMP"):
        return "DATETIME"
    if normalized in RAW:
        return "RAW"
    return normalized


@dataclass(frozen=True, slots=True)
class DatatypeEvidence:
    ratio: float
    compatible: bool
    explanation: str


def compare_datatypes(source: ColumnMetadata, target: ColumnMetadata) -> DatatypeEvidence:
    sf, tf = datatype_family(source.data_type), datatype_family(target.data_type)
    if sf != tf:
        return DatatypeEvidence(0, False, f"incompatible datatype families: {sf} and {tf}")
    if sf == "NUMERIC":
        if source.scale is not None and target.scale is not None and source.scale != target.scale:
            return DatatypeEvidence(
                0.75, True, "numeric types are compatible with different scales"
            )
        return DatatypeEvidence(1.0, True, "numeric datatype families are compatible")
    if sf == "TEXT":
        if source.data_length and target.data_length and source.data_length > target.data_length:
            return DatatypeEvidence(
                0.72, True, "text types are compatible but source length exceeds target"
            )
        return DatatypeEvidence(1.0, True, "text datatype families and lengths are compatible")
    if source.data_type.upper() == target.data_type.upper():
        return DatatypeEvidence(1.0, True, "datatypes match exactly")
    return DatatypeEvidence(0.8, True, f"compatible datatype family: {sf}")
