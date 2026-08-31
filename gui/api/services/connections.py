from gui.api.errors import ApiProblem
from gui.api.schemas.connections import (
    CapabilityCheck,
    ConnectionCreateRequest,
    ConnectionResponse,
    SchemaListResponse,
    SchemaSummaryResponse,
)
from gui.api.services.connection_sessions import (
    ConnectionSessionStore,
    RuntimeCredentials,
    SessionNotFoundError,
)
from gui.api.services.oracle_gateway import OracleGateway, OracleGatewayError
from oracle_relationship_discovery.models import SchemaSummary

CAPABILITY_CHECKS = (
    CapabilityCheck(key="oracle_connection", label="Oracle connection"),
    CapabilityCheck(key="metadata_visibility", label="Metadata visibility"),
    CapabilityCheck(key="schema_discovery", label="Schema discovery"),
)


class ConnectionService:
    def __init__(self, gateway: OracleGateway, sessions: ConnectionSessionStore) -> None:
        self.gateway = gateway
        self.sessions = sessions

    def create(self, request: ConnectionCreateRequest) -> ConnectionResponse:
        credentials = RuntimeCredentials.create(
            host=request.host,
            port=request.port,
            service_name=request.service_name,
            username=request.username,
            password=request.password.get_secret_value(),
        )
        try:
            result = self.gateway.verify_and_discover(credentials)
            schemas = _normalize_schemas(result.schemas)
            session = self.sessions.create(
                schemas,
                replace_connection_id=request.replace_connection_id,
            )
        except OracleGatewayError as exc:
            raise ApiProblem(exc.status_code, exc.code, exc.message) from None
        finally:
            credentials.clear()
        return ConnectionResponse(
            connection_id=session.connection_id,
            expires_in_seconds=self.sessions.idle_timeout_seconds,
            checks=CAPABILITY_CHECKS,
        )

    def list_schemas(self, connection_id: str) -> SchemaListResponse:
        session = self._session(connection_id)
        return SchemaListResponse(
            connection_id=session.connection_id,
            schemas=tuple(
                SchemaSummaryResponse(
                    name=item.name,
                    table_count=item.table_count,
                    column_count=item.column_count,
                    oracle_maintained=item.oracle_maintained,
                )
                for item in session.schemas
            ),
        )

    def disconnect(self, connection_id: str) -> None:
        if not self.sessions.delete(connection_id):
            raise _session_problem()

    def close(self) -> None:
        self.sessions.clear()

    def _session(self, connection_id: str):
        try:
            return self.sessions.get(connection_id)
        except SessionNotFoundError:
            raise _session_problem() from None


def _normalize_schemas(schemas: tuple[SchemaSummary, ...]) -> tuple[SchemaSummary, ...]:
    unique = {item.name: item for item in schemas}
    return tuple(unique[name] for name in sorted(unique))


def _session_problem() -> ApiProblem:
    return ApiProblem(
        404,
        "CONNECTION_SESSION_NOT_FOUND",
        "The local Oracle connection session is missing or has expired.",
    )
