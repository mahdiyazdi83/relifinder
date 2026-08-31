from fastapi import HTTPException
from fastapi.testclient import TestClient

from gui.api.app import app, create_app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "relifinder"}


def test_http_errors_use_sanitized_contract() -> None:
    response = TestClient(app).get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "http_error", "message": "Not Found"}}


def test_http_exception_details_are_not_exposed() -> None:
    isolated_app = create_app()

    @isolated_app.get("/api/private-error")
    def private_error() -> None:
        raise HTTPException(status_code=400, detail="secret credential or internal path")

    response = TestClient(isolated_app).get("/api/private-error")

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "http_error", "message": "The request is invalid."}
    }
    assert "secret" not in response.text
