from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from gui.api.services.connection_sessions import RuntimeCredentials
from oracle_relationship_discovery.db.connection import connect_with_credentials, execute_select
from oracle_relationship_discovery.db.metadata_repository import MetadataRepository
from oracle_relationship_discovery.models import SchemaSummary


@dataclass(frozen=True, slots=True)
class OracleDiscoveryResult:
    schemas: tuple[SchemaSummary, ...]


class OracleGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class OracleGateway(Protocol):
    def verify_and_discover(self, credentials: RuntimeCredentials) -> OracleDiscoveryResult: ...


class CoreOracleGateway:
    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def verify_and_discover(self, credentials: RuntimeCredentials) -> OracleDiscoveryResult:
        try:
            with connect_with_credentials(
                host=credentials.host,
                port=credentials.port,
                service_name=credentials.service_name,
                username=credentials.username,
                password=credentials.password_text(),
                timeout_seconds=self.timeout_seconds,
            ) as connection:
                with connection.cursor() as cursor:
                    row = execute_select(cursor, "SELECT 1 FROM DUAL").fetchone()
                    if not row or row[0] != 1:
                        raise OracleGatewayError(
                            "UNKNOWN_CONNECTION_ERROR",
                            "Oracle did not complete the connection verification query.",
                            502,
                        )
                repository = MetadataRepository(connection)
                try:
                    repository.verify_required_access()
                    schemas = repository.discover_schemas()
                except OracleGatewayError:
                    raise
                except Exception:  # noqa: BLE001 - sanitize repository failures.
                    raise OracleGatewayError(
                        "INSUFFICIENT_METADATA_ACCESS",
                        "The Oracle account cannot read all metadata required by ReliFinder.",
                        403,
                    ) from None
                return OracleDiscoveryResult(tuple(schemas))
        except OracleGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001 - Oracle exposes multiple driver error types.
            raise _sanitized_connection_error(exc) from None


def _sanitized_connection_error(exc: Exception) -> OracleGatewayError:
    value = str(exc).upper()
    if "ORA-01017" in value or "DPY-4001" in value:
        return OracleGatewayError(
            "AUTHENTICATION_FAILED",
            "Oracle rejected the supplied username or password.",
            401,
        )
    if "ORA-12514" in value or "DPY-6001" in value:
        return OracleGatewayError(
            "SERVICE_NOT_FOUND",
            "The requested Oracle service is not available at that listener.",
            503,
        )
    if "ORA-12170" in value or "TIMED OUT" in value or "TIMEOUT" in value:
        return OracleGatewayError(
            "TIMEOUT",
            "The Oracle connection attempt timed out.",
            504,
        )
    if any(code in value for code in ("ORA-12541", "DPY-6005", "DPY-4011")):
        return OracleGatewayError(
            "SERVICE_UNAVAILABLE",
            "The Oracle service could not be reached.",
            503,
        )
    if any(code in value for code in ("DPY-6000", "DPY-6002", "DPY-6003", "DPY-6004")):
        return OracleGatewayError(
            "NETWORK_ERROR",
            "A network error prevented the Oracle connection.",
            503,
        )
    return OracleGatewayError(
        "UNKNOWN_CONNECTION_ERROR",
        "The Oracle connection could not be established.",
        502,
    )
