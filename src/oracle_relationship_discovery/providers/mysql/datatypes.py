"""MySQL and MariaDB native datatype normalization."""

import re

from oracle_relationship_discovery.database.types import DatatypeFamily, classify_native_datatype

_TEXT_TYPES = {"TINYTEXT", "MEDIUMTEXT", "LONGTEXT", "ENUM", "SET"}
_BINARY_TYPES = {"TINYBLOB", "MEDIUMBLOB", "LONGBLOB"}


def normalize_mysql_datatype(native_type: str) -> DatatypeFamily:
    normalized = re.sub(r"\s+", " ", native_type.upper().strip())
    base = normalized.split("(", 1)[0].strip()
    if base in _TEXT_TYPES:
        return DatatypeFamily.TEXT
    if base in _BINARY_TYPES:
        return DatatypeFamily.BINARY
    if base == "JSON":
        return DatatypeFamily.OTHER
    # TINYINT(1) is intentionally numeric: metadata cannot prove it was declared BOOL.
    return classify_native_datatype(normalized)
