"""Backward-compatible import for Oracle metadata access."""

from oracle_relationship_discovery.providers.oracle.metadata import (
    CONSERVATIVE_SYSTEM_SCHEMAS,
    REQUIRED_METADATA_VIEWS,
    MetadataRepository,
    OracleMetadataReader,
)

__all__ = [
    "CONSERVATIVE_SYSTEM_SCHEMAS",
    "REQUIRED_METADATA_VIEWS",
    "MetadataRepository",
    "OracleMetadataReader",
]
