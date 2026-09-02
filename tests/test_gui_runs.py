import json
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from oracle_relationship_discovery.analysis.service import (
    AnalysisPhase,
    AnalysisProgress,
    AnalysisResult,
)
from oracle_relationship_discovery.gui.app import create_app
from oracle_relationship_discovery.gui.schemas.runs import AnalysisConfiguration
from oracle_relationship_discovery.gui.services.oracle_gateway import OracleDiscoveryResult
from oracle_relationship_discovery.gui.services.runs import (
    AnalysisExecutionError,
    AnalysisExecutor,
    _core_config,
)
from oracle_relationship_discovery.models import AnalysisStats, SchemaSummary

CONNECTION_PAYLOAD = {
    "host": "db.example.invalid",
    "port": 1521,
    "service_name": "FAKE_SERVICE",
    "username": "FAKE_USER",
    "password": "fake-phase3-password-4K!",
}


class FakeResource:
    def __init__(self) -> None:
        self.closed = False

    @contextmanager
    def acquire(self, _timeout_seconds: int):
        yield object()

    def close(self) -> None:
        self.closed = True


class RunGateway:
    def __init__(self) -> None:
        self.resources: list[FakeResource] = []

    def verify_and_discover(self, _credentials):
        resource = FakeResource()
        self.resources.append(resource)
        return OracleDiscoveryResult(
            (SchemaSummary("APP", 3, 12), SchemaSummary("CORE", 5, 30)),
            resource,
        )


class FakeExecutor(AnalysisExecutor):
    def __init__(self, behavior: str = "complete") -> None:
        self.behavior = behavior

    def execute(self, **kwargs):
        callback = kwargs["progress_callback"]
        token = kwargs["cancellation_token"]
        callback(
            AnalysisProgress(
                AnalysisPhase.READING_METADATA,
                "Oracle metadata loaded",
                stats={"schemas": 2, "tables": 8, "columns": 42, "sample_value": 999},
            )
        )
        if self.behavior == "block":
            while True:
                token.raise_if_cancelled()
                time.sleep(0.005)
        if self.behavior == "fail":
            raise AnalysisExecutionError("ORACLE_CONNECTION_LOST", "Oracle connection was lost.")
        callback(
            AnalysisProgress(
                AnalysisPhase.BUILDING_CANDIDATES,
                "Candidate discovery completed",
                stats={"schemas": 2, "tables": 8, "columns": 42, "candidates_generated": 21},
            )
        )
        callback(
            AnalysisProgress(
                AnalysisPhase.VALIDATING_CANDIDATES,
                "Validating relationship candidates",
                current=7,
                total=21,
                stats={"candidates_generated": 21},
            )
        )
        callback(AnalysisProgress(AnalysisPhase.SCORING, "Finalizing scores"))
        callback(AnalysisProgress(AnalysisPhase.WRITING_ARTIFACTS, "Writing artifacts"))
        return AnalysisResult(
            AnalysisStats(2, 8, 42, 21, 18, 3),
            relationships_in_report=11,
            mode="sampled",
            elapsed_seconds=1.25,
            run_directory=Path("ignored"),
        )


def _connect(client: TestClient) -> str:
    response = client.post("/api/connections", json=CONNECTION_PAYLOAD)
    assert response.status_code == 201
    return response.json()["connection_id"]


def _payload(connection_id: str, **configuration):
    return {
        "connection_id": connection_id,
        "schemas": ["CORE", "APP", "CORE"],
        "configuration": {"profile": "BALANCED", **configuration},
    }


def _wait_for(client: TestClient, run_id: str, state: str, timeout: float = 2) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["state"] == state:
            return body
        time.sleep(0.01)
    raise AssertionError(f"run did not reach {state}")


def test_gui_core_configuration_generates_authoritative_dbml(tmp_path: Path) -> None:
    config = _core_config(("APP",), AnalysisConfiguration(), tmp_path)

    assert config.erd.enabled is True
    assert config.erd.scope == "full"
    assert config.erd.min_confidence == 80


def test_run_creation_progress_and_completed_summary() -> None:
    with TestClient(create_app(gateway=RunGateway(), analysis_executor=FakeExecutor())) as client:
        connection_id = _connect(client)
        response = client.post("/api/runs", json=_payload(connection_id))
        assert response.status_code == 202
        assert response.json()["status"] == "QUEUED"
        completed = _wait_for(client, response.json()["run_id"], "COMPLETED")

    assert completed["selected_schemas"] == ["CORE", "APP"]
    assert completed["summary"] == {
        "schemas_analyzed": 2,
        "tables": 8,
        "columns": 42,
        "candidates_generated": 21,
        "candidates_validated": 18,
        "candidates_skipped": 3,
        "relationships_in_report": 11,
        "run_mode": "sampled",
        "elapsed_seconds": 1.25,
    }


def test_invalid_configuration_and_preset_mismatch_are_rejected() -> None:
    with TestClient(create_app(gateway=RunGateway(), analysis_executor=FakeExecutor())) as client:
        connection_id = _connect(client)
        invalid = client.post(
            "/api/runs",
            json=_payload(connection_id, max_workers=0),
        )
        mismatch = client.post(
            "/api/runs",
            json=_payload(connection_id, metadata_candidate_threshold=55),
        )

    assert invalid.status_code == 422
    assert mismatch.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_invalid_session_and_unavailable_schema_fail_cleanly() -> None:
    with TestClient(create_app(gateway=RunGateway(), analysis_executor=FakeExecutor())) as client:
        missing = client.post(
            "/api/runs",
            json=_payload("missing-session-1234567890"),
        )
        connection_id = _connect(client)
        unavailable = client.post(
            "/api/runs",
            json={**_payload(connection_id), "schemas": ["PRIVATE"]},
        )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONNECTION_SESSION_NOT_FOUND"
    assert unavailable.status_code == 400
    assert unavailable.json()["error"]["code"] == "SCHEMA_NOT_AVAILABLE"


def test_sse_serialization_is_typed_and_drops_unknown_or_sample_fields() -> None:
    with TestClient(create_app(gateway=RunGateway(), analysis_executor=FakeExecutor())) as client:
        connection_id = _connect(client)
        run_id = client.post("/api/runs", json=_payload(connection_id)).json()["run_id"]
        _wait_for(client, run_id, "COMPLETED")
        text = client.get(f"/api/runs/{run_id}/events").text

    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]
    assert [item["sequence"] for item in payloads] == sorted(item["sequence"] for item in payloads)
    assert payloads[-1]["state"] == "COMPLETED"
    assert all("sample_value" not in item["stats"] for item in payloads)
    assert "fake-phase3-password" not in text


def test_cancellation_is_cooperative_and_allows_resource_cleanup() -> None:
    gateway = RunGateway()
    with TestClient(create_app(gateway=gateway, analysis_executor=FakeExecutor("block"))) as client:
        connection_id = _connect(client)
        run_id = client.post("/api/runs", json=_payload(connection_id)).json()["run_id"]
        cancel = client.post(f"/api/runs/{run_id}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "CANCEL_REQUESTED"
        _wait_for(client, run_id, "CANCELLED")
        assert client.delete(f"/api/connections/{connection_id}").status_code == 204

    assert gateway.resources[0].closed


def test_single_active_run_per_connection_returns_conflict() -> None:
    with TestClient(
        create_app(gateway=RunGateway(), analysis_executor=FakeExecutor("block"))
    ) as client:
        connection_id = _connect(client)
        first = client.post("/api/runs", json=_payload(connection_id))
        second = client.post("/api/runs", json=_payload(connection_id))
        client.post(f"/api/runs/{first.json()['run_id']}/cancel")
        _wait_for(client, first.json()["run_id"], "CANCELLED")

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ACTIVE_RUN_EXISTS"


def test_failed_run_is_sanitized_and_retry_is_possible() -> None:
    executor = FakeExecutor("fail")
    with TestClient(create_app(gateway=RunGateway(), analysis_executor=executor)) as client:
        connection_id = _connect(client)
        first_id = client.post("/api/runs", json=_payload(connection_id)).json()["run_id"]
        failed = _wait_for(client, first_id, "FAILED")
        executor.behavior = "complete"
        retry = client.post("/api/runs", json=_payload(connection_id))
        completed = _wait_for(client, retry.json()["run_id"], "COMPLETED")

    assert failed["message"] == "Oracle connection was lost."
    assert failed["error_code"] == "ORACLE_CONNECTION_LOST"
    assert retry.status_code == 202
    assert completed["state"] == "COMPLETED"
