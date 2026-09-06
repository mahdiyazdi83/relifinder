"""Database-neutral datatype-family compatibility rules."""

from __future__ import annotations

from dataclasses import dataclass

from oracle_relationship_discovery.database.types import (
    DatatypeFamily,
    classify_native_datatype,
)
from oracle_relationship_discovery.models import ColumnMetadata


def datatype_family(data_type: str) -> str:
    """Compatibility helper for callers that have not built canonical metadata."""
    return classify_native_datatype(data_type).value


@dataclass(frozen=True, slots=True)
class DatatypeEvidence:
    ratio: float
    compatible: bool
    explanation: str


def compare_datatypes(source: ColumnMetadata, target: ColumnMetadata) -> DatatypeEvidence:
    sf = source.data_type_family or DatatypeFamily.OTHER
    tf = target.data_type_family or DatatypeFamily.OTHER
    if sf != tf:
        return DatatypeEvidence(
            0, False, f"incompatible datatype families: {sf.value} and {tf.value}"
        )
    if sf == DatatypeFamily.OTHER:
        source_native = source.data_type.upper().strip()
        target_native = target.data_type.upper().strip()
        if source_native != target_native:
            return DatatypeEvidence(
                0,
                False,
                f"incompatible native datatypes: {source_native} and {target_native}",
            )
        return DatatypeEvidence(1.0, True, "native datatypes match exactly")
    if sf == DatatypeFamily.NUMERIC:
        if source.scale is not None and target.scale is not None and source.scale != target.scale:
            return DatatypeEvidence(
                0.75, True, "numeric types are compatible with different scales"
            )
        return DatatypeEvidence(1.0, True, "numeric datatype families are compatible")
    if sf == DatatypeFamily.TEXT:
        if source.data_length and target.data_length and source.data_length > target.data_length:
            return DatatypeEvidence(
                0.72, True, "text types are compatible but source length exceeds target"
            )
        return DatatypeEvidence(1.0, True, "text datatype families and lengths are compatible")
    if source.data_type.upper() == target.data_type.upper():
        return DatatypeEvidence(1.0, True, "datatypes match exactly")
    return DatatypeEvidence(0.8, True, f"compatible datatype family: {sf.value}")
