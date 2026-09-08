"""PostgreSQL-native datatype normalization."""

from oracle_relationship_discovery.database.types import DatatypeFamily, classify_native_datatype

_POSTGRES_OTHER = {"JSON", "JSONB", "UUID", "XML", "INET", "CIDR", "MACADDR"}


def normalize_postgresql_datatype(native_type: str) -> DatatypeFamily:
    normalized = native_type.upper().strip()
    family = classify_native_datatype(normalized)
    if family != DatatypeFamily.OTHER:
        return family
    if normalized in _POSTGRES_OTHER or normalized.endswith("[]"):
        return DatatypeFamily.OTHER
    return DatatypeFamily.OTHER
