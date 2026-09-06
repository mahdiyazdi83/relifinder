"""Canonical database-neutral datatype families."""

from __future__ import annotations

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
    "FLOAT",
    "INT",
    "INTEGER",
    "NUMBER",
    "NUMERIC",
    "REAL",
    "SMALLINT",
}
_TEXT = {
    "CHAR",
    "CLOB",
    "LONG",
    "NCHAR",
    "NCLOB",
    "NVARCHAR",
    "NVARCHAR2",
    "TEXT",
    "VARCHAR",
    "VARCHAR2",
}
_DATETIME = {"DATE", "DATETIME", "TIME", "TIMESTAMP"}
_BINARY = {"BINARY", "BLOB", "LONG RAW", "RAW", "VARBINARY"}
_BOOLEAN = {"BOOL", "BOOLEAN"}


def classify_native_datatype(native_type: str) -> DatatypeFamily:
    """Best-effort family for legacy model construction and offline artifacts."""
    normalized = native_type.upper().strip()
    if normalized in _NUMERIC:
        return DatatypeFamily.NUMERIC
    if normalized in _TEXT or normalized.startswith(("CHAR(", "VARCHAR(")):
        return DatatypeFamily.TEXT
    if normalized in _DATETIME or normalized.startswith(("TIMESTAMP", "TIME(")):
        return DatatypeFamily.DATETIME
    if normalized in _BINARY:
        return DatatypeFamily.BINARY
    if normalized in _BOOLEAN:
        return DatatypeFamily.BOOLEAN
    return DatatypeFamily.OTHER
