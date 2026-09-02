import logging

from fastapi.testclient import TestClient

from oracle_relationship_discovery.gui.app import create_app
from oracle_relationship_discovery.gui.services.connection_sessions import ConnectionSessionStore
from oracle_relationship_discovery.gui.services.oracle_gateway import (
    OracleDiscoveryResult,
    OracleGatewayError,
    _sanitized_connection_error,
)
from oracle_relationship_discovery.models import SchemaSummary

FAKE_PASSWORD = "fake-phase2-password-7C!"
CONNECTION_PAYLOAD = {
    "host": "db.example.invalid",
    "port": 1521,
    "service_name": "FAKE_SERVICE",
    "username": "FAKE_USER",
    "password": FAKE_PASSWORD,
}


class FakeGateway:
    def __init__(
        self,
        schemas: tuple[SchemaSummary, ...] = (),
        error: OracleGatewayError | None = None,
    ) -> None:
        self.schemas = schemas
        self.error = error
        self.credentials = []

    def verify_and_discover(self, credentials):
        self.credentials.append(credentials)
        if self.error:
            raise self.error
        assert credentials.password_text() == FAKE_PASSWORD
        return OracleDiscoveryResult(self.schemas)


def test_connection_response_and_logs_never_expose_password(caplog) -> None:
    gateway = FakeGateway((SchemaSummary("APP", 4, 22),))
    caplog.set_level(logging.DEBUG)
    with TestClient(create_app(gateway=gateway)) as client:
        response = client.post("/api/connections", json=CONNECTION_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "connected"
    assert body["connection_id"]
    assert FAKE_PASSWORD not in response.text
    assert FAKE_PASSWORD not in body["connection_id"]
    assert FAKE_PASSWORD not in caplog.text
    assert gateway.credentials[0].is_cleared


def test_failed_connection_is_sanitized_and_password_is_not_logged(caplog) -> None:
    gateway = FakeGateway(
        error=OracleGatewayError(
            "AUTHENTICATION_FAILED",
            "Oracle rejected the supplied username or password.",
            401,
        )
    )
    caplog.set_level(logging.DEBUG)
    with TestClient(create_app(gateway=gateway)) as client:
        response = client.post("/api/connections", json=CONNECTION_PAYLOAD)

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "AUTHENTICATION_FAILED",
            "message": "Oracle rejected the supplied username or password.",
        }
    }
    assert FAKE_PASSWORD not in response.text
    assert FAKE_PASSWORD not in caplog.text
    assert gateway.credentials[0].is_cleared


def test_schema_summaries_are_sorted_deduplicated_and_metadata_only() -> None:
    gateway = FakeGateway(
        (
            SchemaSummary("REF", 2, 8),
            SchemaSummary("APP", 7, 40),
            SchemaSummary("SYS", 100, 900, True),
            SchemaSummary("APP", 9, 44),
        )
    )
    with TestClient(create_app(gateway=gateway)) as client:
        connection_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()[
            "connection_id"
        ]
        response = client.get(f"/api/connections/{connection_id}/schemas")

    assert response.status_code == 200
    assert response.json()["schemas"] == [
        {"name": "APP", "table_count": 9, "column_count": 44, "oracle_maintained": False},
        {"name": "REF", "table_count": 2, "column_count": 8, "oracle_maintained": False},
        {"name": "SYS", "table_count": 100, "column_count": 900, "oracle_maintained": True},
    ]


def test_zero_and_many_accessible_schemas() -> None:
    for summaries, expected in (
        ((), 0),
        (tuple(SchemaSummary(f"APP_{index:03}", index, index * 5) for index in range(200)), 200),
    ):
        with TestClient(create_app(gateway=FakeGateway(summaries))) as client:
            connection_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()[
                "connection_id"
            ]
            response = client.get(f"/api/connections/{connection_id}/schemas")
        assert len(response.json()["schemas"]) == expected


def test_disconnect_invalidates_session_and_clears_credentials() -> None:
    gateway = FakeGateway((SchemaSummary("APP", 1, 3),))
    with TestClient(create_app(gateway=gateway)) as client:
        connection_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()[
            "connection_id"
        ]
        assert client.delete(f"/api/connections/{connection_id}").status_code == 204
        response = client.get(f"/api/connections/{connection_id}/schemas")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONNECTION_SESSION_NOT_FOUND"
    assert gateway.credentials[0].is_cleared


def test_unknown_session_is_safe() -> None:
    with TestClient(create_app(gateway=FakeGateway())) as client:
        response = client.get("/api/connections/not-a-session/schemas")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "CONNECTION_SESSION_NOT_FOUND",
            "message": "The local Oracle connection session is missing or has expired.",
        }
    }


def test_expired_session_is_cleaned_and_cannot_be_reused() -> None:
    now = [10.0]
    sessions = ConnectionSessionStore(idle_timeout_seconds=5, clock=lambda: now[0])
    gateway = FakeGateway((SchemaSummary("APP", 1, 3),))
    with TestClient(create_app(gateway=gateway, sessions=sessions)) as client:
        connection_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()[
            "connection_id"
        ]
        now[0] = 16.0
        response = client.get(f"/api/connections/{connection_id}/schemas")

    assert response.status_code == 404
    assert gateway.credentials[0].is_cleared


def test_successful_replacement_invalidates_previous_session_and_resets_secret() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(gateway=gateway)) as client:
        previous_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()[
            "connection_id"
        ]
        replacement = {**CONNECTION_PAYLOAD, "replace_connection_id": previous_id}
        current_id = client.post("/api/connections", json=replacement).json()["connection_id"]
        previous_response = client.get(f"/api/connections/{previous_id}/schemas")
        current_response = client.get(f"/api/connections/{current_id}/schemas")

    assert current_id != previous_id
    assert previous_response.status_code == 404
    assert current_response.status_code == 200
    assert gateway.credentials[0].is_cleared


def test_no_permissive_cors_middleware_is_installed() -> None:
    app = create_app(gateway=FakeGateway())
    assert all(middleware.cls.__name__ != "CORSMiddleware" for middleware in app.user_middleware)


def test_oracle_error_mapping_drops_raw_descriptor() -> None:
    raw = Exception(
        "DPY-6001 service FAKE_SERVICE is not registered at db.example.invalid; "
        f"password={FAKE_PASSWORD}"
    )
    error = _sanitized_connection_error(raw)

    assert error.code == "SERVICE_NOT_FOUND"
    assert "FAKE_SERVICE" not in error.message
    assert "db.example.invalid" not in error.message
    assert FAKE_PASSWORD not in error.message


def test_session_capacity_is_bounded_and_evicts_oldest() -> None:
    sessions = ConnectionSessionStore(max_sessions=1)
    gateway = FakeGateway()
    with TestClient(create_app(gateway=gateway, sessions=sessions)) as client:
        first_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()["connection_id"]
        second_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()["connection_id"]

        assert client.get(f"/api/connections/{first_id}/schemas").status_code == 404
        assert client.get(f"/api/connections/{second_id}/schemas").status_code == 200
