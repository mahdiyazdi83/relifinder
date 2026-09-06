"""Database-neutral contracts used by the relationship analysis engine."""

from oracle_relationship_discovery.database.base import (
    CandidateSampler,
    ConnectionFactory,
    DatabaseAdapter,
    DatabaseError,
    DatabaseOperation,
    DatabaseSettings,
    MetadataReader,
    RuntimeResource,
)
from oracle_relationship_discovery.database.types import DatatypeFamily

__all__ = [
    "CandidateSampler",
    "ConnectionFactory",
    "DatabaseAdapter",
    "DatabaseError",
    "DatabaseOperation",
    "DatabaseSettings",
    "DatatypeFamily",
    "MetadataReader",
    "RuntimeResource",
]
