"""Oracle implementation of ReliFinder's minimal database adapter."""

from __future__ import annotations

from typing import Any, cast

from oracle_relationship_discovery.config import DatabaseConfig, SamplingConfig
from oracle_relationship_discovery.database.base import (
    ConnectionFactory,
    DatabaseError,
    DatabaseOperation,
    DatabaseSettings,
)
from oracle_relationship_discovery.providers.oracle.connection import (
    connection_pool,
    create_pool_with_credentials,
    execute_select,
)
from oracle_relationship_discovery.providers.oracle.metadata import OracleMetadataReader
from oracle_relationship_discovery.providers.oracle.sampling import OracleDataSampler


class OracleAdapter:
    type_name = "oracle"
    display_name = "Oracle"

    def connection_pool(self, config: DatabaseSettings, timeout_seconds: int, max_connections: int):
        return connection_pool(
            cast(DatabaseConfig, config),
            timeout_seconds,
            max_connections,
        )

    def create_runtime_resource(self, **credentials):
        return create_pool_with_credentials(**credentials)

    def verify_connection(self, connection: Any) -> None:
        with connection.cursor() as cursor:
            row = execute_select(cursor, "SELECT 1 FROM DUAL").fetchone()
            if not row or row[0] != 1:
                raise DatabaseError(
                    "UNKNOWN_CONNECTION_ERROR",
                    "Oracle did not complete the connection verification query.",
                )

    def metadata_reader(self, connection: Any) -> OracleMetadataReader:
        return OracleMetadataReader(connection)

    def candidate_sampler(
        self, connection_factory: ConnectionFactory, sampling: SamplingConfig
    ) -> OracleDataSampler:
        return OracleDataSampler(connection_factory, sampling)

    def normalize_error(self, exc: Exception, operation: DatabaseOperation) -> DatabaseError:
        if isinstance(exc, DatabaseError):
            return exc
        value = str(exc).upper()
        if operation == DatabaseOperation.METADATA:
            return DatabaseError(
                "INSUFFICIENT_METADATA_ACCESS",
                "The Oracle account cannot read all metadata required by ReliFinder.",
                status_code=403,
            )
        if "ORA-01017" in value or "DPY-4001" in value:
            return DatabaseError(
                "AUTHENTICATION_FAILED",
                "Oracle rejected the supplied username or password.",
                status_code=401,
            )
        if "ORA-12514" in value or "DPY-6001" in value:
            return DatabaseError(
                "SERVICE_NOT_FOUND",
                "The requested Oracle service is not available at that listener.",
                status_code=503,
            )
        if "ORA-01013" in value or "CANCEL" in value:
            return DatabaseError("ANALYSIS_CANCELLED", "Analysis was cancelled safely.")
        if "ORA-12170" in value or "TIMED OUT" in value or "TIMEOUT" in value:
            message = (
                "Analysis timed out."
                if operation == DatabaseOperation.ANALYSIS
                else "The Oracle connection attempt timed out."
            )
            code = "ANALYSIS_TIMEOUT" if operation == DatabaseOperation.ANALYSIS else "TIMEOUT"
            return DatabaseError(code, message, status_code=504)
        if any(code in value for code in ("ORA-03113", "ORA-03114", "DPY-1001")):
            return DatabaseError("ORACLE_CONNECTION_LOST", "Oracle connection was lost.")
        if any(code in value for code in ("ORA-12541", "DPY-6005", "DPY-4011")):
            if operation == DatabaseOperation.ANALYSIS:
                return DatabaseError("ORACLE_CONNECTION_LOST", "Oracle connection was lost.")
            return DatabaseError(
                "SERVICE_UNAVAILABLE",
                "The Oracle service could not be reached.",
                status_code=503,
            )
        if any(code in value for code in ("DPY-6000", "DPY-6002", "DPY-6003", "DPY-6004")):
            return DatabaseError(
                "NETWORK_ERROR",
                "A network error prevented the Oracle connection.",
                status_code=503,
            )
        if operation == DatabaseOperation.ANALYSIS and any(
            name in value for name in ("ALL_TABLES", "ALL_TAB_COLUMNS", "ALL_CONSTRAINTS")
        ):
            return DatabaseError("METADATA_ACCESS_FAILED", "Oracle metadata access failed.")
        message = (
            "Unexpected analysis failure."
            if operation == DatabaseOperation.ANALYSIS
            else "The Oracle connection could not be established."
        )
        code = (
            "UNEXPECTED_ANALYSIS_FAILURE"
            if operation == DatabaseOperation.ANALYSIS
            else "UNKNOWN_CONNECTION_ERROR"
        )
        return DatabaseError(code, message)
