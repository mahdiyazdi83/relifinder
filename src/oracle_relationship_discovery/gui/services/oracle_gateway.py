from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from oracle_relationship_discovery.database.base import DatabaseError, DatabaseOperation
from oracle_relationship_discovery.gui.services.connection_sessions import (
    RuntimeCredentials,
    RuntimeResource,
)
from oracle_relationship_discovery.models import SchemaSummary
from oracle_relationship_discovery.providers.oracle import ORACLE_ADAPTER


@dataclass(frozen=True, slots=True)
class OracleDiscoveryResult:
    schemas: tuple[SchemaSummary, ...]
    resource: RuntimeResource | None = None


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
        resource = None
        try:
            resource = ORACLE_ADAPTER.create_runtime_resource(
                host=credentials.host,
                port=credentials.port,
                service_name=credentials.service_name,
                username=credentials.username,
                password=credentials.password_text(),
            )
            with resource.acquire(self.timeout_seconds) as connection:
                ORACLE_ADAPTER.verify_connection(connection)
                repository = ORACLE_ADAPTER.metadata_reader(connection)
                try:
                    repository.verify_required_access()
                    schemas = repository.discover_schemas()
                except OracleGatewayError:
                    raise
                except Exception as exc:  # noqa: BLE001 - sanitize repository failures.
                    error = ORACLE_ADAPTER.normalize_error(exc, DatabaseOperation.METADATA)
                    raise _gateway_error(error) from None
            return OracleDiscoveryResult(tuple(schemas), resource)
        except OracleGatewayError:
            if resource:
                resource.close()
            raise
        except Exception as exc:  # noqa: BLE001 - Oracle exposes multiple driver error types.
            if resource:
                resource.close()
            error = ORACLE_ADAPTER.normalize_error(exc, DatabaseOperation.CONNECT)
            raise _gateway_error(error) from None


def _gateway_error(error: DatabaseError) -> OracleGatewayError:
    return OracleGatewayError(error.code, error.message, error.status_code)


def _sanitized_connection_error(exc: Exception) -> OracleGatewayError:
    """Retain the historical helper while delegating classification to the provider."""
    return _gateway_error(ORACLE_ADAPTER.normalize_error(exc, DatabaseOperation.CONNECT))
