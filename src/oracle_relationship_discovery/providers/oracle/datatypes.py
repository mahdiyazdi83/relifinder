"""Oracle-native datatype normalization."""

from oracle_relationship_discovery.database.types import DatatypeFamily

_ORACLE_NUMERIC = {
    "BINARY_DOUBLE",
    "BINARY_FLOAT",
    "DECIMAL",
    "FLOAT",
    "INTEGER",
    "NUMBER",
    "NUMERIC",
}
_ORACLE_TEXT = {"CHAR", "CLOB", "LONG", "NCHAR", "NCLOB", "NVARCHAR2", "VARCHAR", "VARCHAR2"}
_ORACLE_TEMPORAL = {
    "DATE",
    "INTERVAL DAY TO SECOND",
    "INTERVAL YEAR TO MONTH",
    "TIMESTAMP",
    "TIMESTAMP WITH LOCAL TIME ZONE",
    "TIMESTAMP WITH TIME ZONE",
}
_ORACLE_BINARY = {"BFILE", "BLOB", "LONG RAW", "RAW"}


def normalize_oracle_datatype(native_type: str) -> DatatypeFamily:
    """Map an Oracle-reported native datatype to a canonical family."""
    normalized = native_type.upper().strip()
    if normalized in _ORACLE_NUMERIC:
        return DatatypeFamily.NUMERIC
    if normalized in _ORACLE_TEXT:
        return DatatypeFamily.TEXT
    if normalized in _ORACLE_TEMPORAL or normalized.startswith("TIMESTAMP"):
        return DatatypeFamily.DATETIME
    if normalized in _ORACLE_BINARY:
        return DatatypeFamily.BINARY
    if normalized == "BOOLEAN":
        return DatatypeFamily.BOOLEAN
    return DatatypeFamily.OTHER
