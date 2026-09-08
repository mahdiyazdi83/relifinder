"""MySQL and MariaDB implementations of ReliFinder's database adapter."""

from __future__ import annotations

from typing import Any, cast

from oracle_relationship_discovery.config import DatabaseConfig, SamplingConfig
from oracle_relationship_discovery.database.base import (
    ConnectionFactory,
    DatabaseError,
    DatabaseOperation,
    DatabaseSettings,
)
from oracle_relationship_discovery.providers.mysql.connection import (
    connection_pool,
    create_pool_with_credentials,
    execute_read,
)
from oracle_relationship_discovery.providers.mysql.metadata import MySQLMetadataReader
from oracle_relationship_discovery.providers.mysql.sampling import MySQLDataSampler


class MySQLAdapter:
    def __init__(self, *, mariadb: bool = False) -> None:
        self.mariadb = mariadb
        self.type_name = "mariadb" if mariadb else "mysql"
        self.display_name = "MariaDB" if mariadb else "MySQL"

    def connection_pool(self, config: DatabaseSettings, timeout_seconds: int, max_connections: int):
        return connection_pool(
            cast(DatabaseConfig, config),
            timeout_seconds,
            max_connections,
            display_name=self.display_name,
            mariadb=self.mariadb,
        )

    def create_runtime_resource(self, **credentials):
        return create_pool_with_credentials(
            host=credentials["host"],
            port=credentials["port"],
            database=credentials["database"],
            username=credentials["username"],
            password=credentials["password"],
            timeout_seconds=credentials.get("timeout_seconds", 15),
            max_connections=credentials.get("max_connections", 8),
            display_name=self.display_name,
            mariadb=self.mariadb,
        )

    def verify_connection(self, connection: Any) -> None:
        with connection.cursor() as cursor:
            row = execute_read(cursor, "SELECT 1").fetchone()
            if not row or row[0] != 1:
                raise DatabaseError(
                    "UNKNOWN_CONNECTION_ERROR",
                    f"{self.display_name} did not complete the connection verification query.",
                )

    def metadata_reader(self, connection: Any) -> MySQLMetadataReader:
        return MySQLMetadataReader(connection, mariadb=self.mariadb)

    def candidate_sampler(
        self, connection_factory: ConnectionFactory, sampling: SamplingConfig
    ) -> MySQLDataSampler:
        return MySQLDataSampler(connection_factory, sampling)

    def normalize_error(self, exc: Exception, operation: DatabaseOperation) -> DatabaseError:
        if isinstance(exc, DatabaseError):
            return exc
        value = str(exc).upper()

        if any(token in value for token in ("ACCESS DENIED FOR USER", "(1045", " 1045")):
            return DatabaseError(
                "AUTHENTICATION_FAILED",
                f"{self.display_name} rejected the supplied username or password.",
                status_code=401,
            )
        if any(token in value for token in ("UNKNOWN DATABASE", "(1049", " 1049")):
            return DatabaseError(
                "DATABASE_NOT_FOUND",
                f"The requested {self.display_name} database does not exist.",
                status_code=404,
            )
        if any(token in value for token in ("TIMEOUT", "TIMED OUT", "(1205", " 1205")):
            code = "ANALYSIS_TIMEOUT" if operation == DatabaseOperation.ANALYSIS else "TIMEOUT"
            message = (
                "Analysis timed out."
                if operation == DatabaseOperation.ANALYSIS
                else f"The {self.display_name} connection attempt timed out."
            )
            return DatabaseError(code, message, status_code=504)
        if any(
            token in value for token in ("CAN'T CONNECT", "CONNECTION REFUSED", "(2003", " 2003")
        ):
            return DatabaseError(
                "SERVICE_UNAVAILABLE",
                f"The {self.display_name} service could not be reached.",
                status_code=503,
            )
        if operation == DatabaseOperation.METADATA:
            return DatabaseError(
                "INSUFFICIENT_METADATA_ACCESS",
                f"The {self.display_name} account cannot read all metadata required by ReliFinder.",
                status_code=403,
            )
        if operation == DatabaseOperation.ANALYSIS:
            return DatabaseError(
                "DATABASE_CONNECTION_LOST", f"The {self.display_name} connection was lost."
            )
        return DatabaseError(
            "UNKNOWN_CONNECTION_ERROR",
            f"The {self.display_name} connection could not be established.",
        )
