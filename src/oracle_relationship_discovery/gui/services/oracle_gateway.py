from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from oracle_relationship_discovery.database.base import (
    DatabaseAdapter,
    DatabaseError,
    DatabaseOperation,
    RuntimeResource,
)
from oracle_relationship_discovery.database.factory import adapter_for
from oracle_relationship_discovery.gui.services.connection_sessions import RuntimeCredentials
from oracle_relationship_discovery.models import SchemaSummary
from oracle_relationship_discovery.providers.oracle import ORACLE_ADAPTER


@dataclass(frozen=True, slots=True)
class DatabaseDiscoveryResult:
    schemas: tuple[SchemaSummary, ...]
    resource: RuntimeResource | None = None
    adapter: DatabaseAdapter = ORACLE_ADAPTER
    database_type: str = "oracle"


class DatabaseGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DatabaseGateway(Protocol):
    def verify_and_discover(self, credentials: RuntimeCredentials) -> DatabaseDiscoveryResult: ...


class CoreDatabaseGateway:
    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def verify_and_discover(self, credentials: RuntimeCredentials) -> DatabaseDiscoveryResult:
        adapter = adapter_for(credentials)
        resource = None
        try:
            resource = adapter.create_runtime_resource(
                host=credentials.host,
                port=credentials.port,
                service_name=credentials.service_name,
                database=credentials.database,
                username=credentials.username,
                password=credentials.password_text(),
                timeout_seconds=self.timeout_seconds,
            )
            with resource.acquire(self.timeout_seconds) as connection:
                adapter.verify_connection(connection)
                repository = adapter.metadata_reader(connection)
                try:
                    repository.verify_required_access()
                    schemas = repository.discover_schemas()
                except DatabaseGatewayError:
                    raise
                except Exception as exc:  # noqa: BLE001 - normalize provider failures.
                    error = adapter.normalize_error(exc, DatabaseOperation.METADATA)
                    raise _gateway_error(error) from None
            return DatabaseDiscoveryResult(tuple(schemas), resource, adapter, adapter.type_name)
        except DatabaseGatewayError:
            if resource:
                resource.close()
            raise
        except Exception as exc:  # noqa: BLE001 - drivers expose unrelated error hierarchies.
            if resource:
                resource.close()
            error = adapter.normalize_error(exc, DatabaseOperation.CONNECT)
            raise _gateway_error(error) from None


def _gateway_error(error: DatabaseError) -> DatabaseGatewayError:
    return DatabaseGatewayError(error.code, error.message, error.status_code)


# Historical names retained for API/test/downstream compatibility.
OracleDiscoveryResult = DatabaseDiscoveryResult
OracleGatewayError = DatabaseGatewayError
OracleGateway = DatabaseGateway
CoreOracleGateway = CoreDatabaseGateway


def _sanitized_connection_error(exc: Exception) -> DatabaseGatewayError:
    return _gateway_error(ORACLE_ADAPTER.normalize_error(exc, DatabaseOperation.CONNECT))
