"""Small database contracts at the boundary of the analysis core."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from oracle_relationship_discovery.config import SamplingConfig
    from oracle_relationship_discovery.models import (
        RelationshipCandidate,
        SchemaSummary,
        TableMetadata,
    )

ConnectionFactory = Callable[[], AbstractContextManager[Any]]


class DatabaseOperation(str, Enum):
    CONNECT = "connect"
    METADATA = "metadata"
    ANALYSIS = "analysis"


class DatabaseError(RuntimeError):
    """Sanitized provider error safe to expose at application boundaries."""

    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DatabaseSettings(Protocol):
    type: str


class RuntimeResource(Protocol):
    def acquire(self, timeout_seconds: int) -> AbstractContextManager[Any]: ...

    def close(self) -> None: ...


class MetadataReader(Protocol):
    def verify_required_access(self) -> None: ...

    def discover_schemas(self) -> list[SchemaSummary]: ...

    def load(self, schemas: tuple[str, ...]) -> list[TableMetadata]: ...


class CandidateSampler(Protocol):
    def validate(self, candidate: RelationshipCandidate) -> None: ...


class DatabaseAdapter(Protocol):
    """Only the capabilities required by discovery orchestration."""

    type_name: str
    display_name: str

    def connection_pool(
        self,
        config: DatabaseSettings,
        timeout_seconds: int,
        max_connections: int,
    ) -> AbstractContextManager[ConnectionFactory]: ...

    def metadata_reader(self, connection: Any) -> MetadataReader: ...

    def candidate_sampler(
        self,
        connection_factory: ConnectionFactory,
        sampling: SamplingConfig,
    ) -> CandidateSampler: ...

    def normalize_error(self, exc: Exception, operation: DatabaseOperation) -> DatabaseError: ...
