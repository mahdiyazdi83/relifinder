"""Canonical database-neutral datatype families."""

from __future__ import annotations

import re
from enum import Enum


class DatatypeFamily(str, Enum):
    NUMERIC = "NUMERIC"
    TEXT = "TEXT"
    DATETIME = "DATETIME"
    BINARY = "BINARY"
    BOOLEAN = "BOOLEAN"
    OTHER = "OTHER"


_NUMERIC = {
    "BIGINT",
    "BINARY_DOUBLE",
    "BINARY_FLOAT",
    "DECIMAL",
    "DOUBLE",
    "DOUBLE PRECISION",
    "FLOAT",
    "INT",
    "INTEGER",
    "MEDIUMINT",
    "NUMBER",
    "NUMERIC",
    "REAL",
    "SERIAL",
    "BIGSERIAL",
    "SMALLINT",
    "SMALLSERIAL",
    "TINYINT",
}
_TEXT = {
    "CHAR",
    "CHARACTER",
    "CHARACTER VARYING",
    "CLOB",
    "LONG",
    "LONGTEXT",
    "MEDIUMTEXT",
    "NCHAR",
    "NCLOB",
    "NVARCHAR",
    "NVARCHAR2",
    "TEXT",
    "TINYTEXT",
    "VARCHAR",
    "VARCHAR2",
}
_DATETIME = {
    "DATE",
    "DATETIME",
    "TIME",
    "TIME WITH TIME ZONE",
    "TIME WITHOUT TIME ZONE",
    "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE",
    "TIMESTAMP WITHOUT TIME ZONE",
}
_BINARY = {
    "BINARY",
    "BLOB",
    "BYTEA",
    "LONGBLOB",
    "LONG RAW",
    "MEDIUMBLOB",
    "RAW",
    "TINYBLOB",
    "VARBINARY",
}
_BOOLEAN = {"BOOL", "BOOLEAN"}


def _base_type(native_type: str) -> str:
    normalized = re.sub(r"\s+", " ", native_type.upper().strip())
    normalized = re.sub(r"\([^)]*\)", "", normalized).strip()
    normalized = re.sub(r"\s+UNSIGNED(?:\s+ZEROFILL)?$", "", normalized).strip()
    return normalized


def classify_native_datatype(native_type: str) -> DatatypeFamily:
    """Best-effort family for model construction and older offline artifacts."""
    normalized = _base_type(native_type)
    if normalized in _NUMERIC:
        return DatatypeFamily.NUMERIC
    if normalized in _TEXT:
        return DatatypeFamily.TEXT
    if normalized in _DATETIME or normalized.startswith(("TIMESTAMP ", "TIME ")):
        return DatatypeFamily.DATETIME
    if normalized in _BINARY:
        return DatatypeFamily.BINARY
    if normalized in _BOOLEAN:
        return DatatypeFamily.BOOLEAN
    return DatatypeFamily.OTHER
