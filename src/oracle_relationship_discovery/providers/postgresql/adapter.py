"""PostgreSQL implementation of ReliFinder's database adapter."""

from __future__ import annotations

from typing import Any, cast

from oracle_relationship_discovery.config import DatabaseConfig, SamplingConfig
from oracle_relationship_discovery.database.base import (
    ConnectionFactory,
    DatabaseError,
    DatabaseOperation,
    DatabaseSettings,
)
from oracle_relationship_discovery.providers.postgresql.connection import (
    connection_pool,
    create_pool_with_credentials,
    execute_read,
)
from oracle_relationship_discovery.providers.postgresql.metadata import PostgreSQLMetadataReader
from oracle_relationship_discovery.providers.postgresql.sampling import PostgreSQLDataSampler


class PostgreSQLAdapter:
    type_name = "postgresql"
    display_name = "PostgreSQL"

    def connection_pool(self, config: DatabaseSettings, timeout_seconds: int, max_connections: int):
        return connection_pool(cast(DatabaseConfig, config), timeout_seconds, max_connections)

    def create_runtime_resource(self, **credentials):
        return create_pool_with_credentials(
            host=credentials["host"],
            port=credentials["port"],
            database=credentials["database"],
            username=credentials["username"],
            password=credentials["password"],
            timeout_seconds=credentials.get("timeout_seconds", 15),
            max_connections=credentials.get("max_connections", 8),
        )

    def verify_connection(self, connection: Any) -> None:
        with connection.cursor() as cursor:
            row = execute_read(cursor, "SELECT 1").fetchone()
            if not row or row[0] != 1:
                raise DatabaseError(
                    "UNKNOWN_CONNECTION_ERROR",
                    "PostgreSQL did not complete the connection verification query.",
                )

    def metadata_reader(self, connection: Any) -> PostgreSQLMetadataReader:
        return PostgreSQLMetadataReader(connection)

    def candidate_sampler(
        self, connection_factory: ConnectionFactory, sampling: SamplingConfig
    ) -> PostgreSQLDataSampler:
        return PostgreSQLDataSampler(connection_factory, sampling)

    def normalize_error(self, exc: Exception, operation: DatabaseOperation) -> DatabaseError:
        if isinstance(exc, DatabaseError):
            return exc
        value = str(exc).upper()

        if any(token in value for token in ("PASSWORD AUTHENTICATION FAILED", "28P01")):
            return DatabaseError(
                "AUTHENTICATION_FAILED",
                "PostgreSQL rejected the supplied username or password.",
                status_code=401,
            )
        if any(token in value for token in ("INVALID CATALOG NAME", "3D000", "DOES NOT EXIST")):
            return DatabaseError(
                "DATABASE_NOT_FOUND",
                "The requested PostgreSQL database does not exist.",
                status_code=404,
            )
        if any(token in value for token in ("TIMEOUT", "TIMED OUT", "QUERY CANCELED", "57014")):
            code = "ANALYSIS_TIMEOUT" if operation == DatabaseOperation.ANALYSIS else "TIMEOUT"
            message = (
                "Analysis timed out."
                if operation == DatabaseOperation.ANALYSIS
                else "The PostgreSQL connection attempt timed out."
            )
            return DatabaseError(code, message, status_code=504)
        if any(
            token in value for token in ("CONNECTION REFUSED", "COULD NOT TRANSLATE HOST", "08001")
        ):
            return DatabaseError(
                "SERVICE_UNAVAILABLE",
                "The PostgreSQL service could not be reached.",
                status_code=503,
            )
        if operation == DatabaseOperation.METADATA:
            return DatabaseError(
                "INSUFFICIENT_METADATA_ACCESS",
                "The PostgreSQL account cannot read all metadata required by ReliFinder.",
                status_code=403,
            )
        if operation == DatabaseOperation.ANALYSIS:
            return DatabaseError("DATABASE_CONNECTION_LOST", "The PostgreSQL connection was lost.")
        return DatabaseError(
            "UNKNOWN_CONNECTION_ERROR",
            "The PostgreSQL connection could not be established.",
        )
