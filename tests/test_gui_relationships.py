import hashlib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from gui.api.app import create_app
from gui.api.services.oracle_gateway import OracleDiscoveryResult
from gui.api.services.runs import AnalysisExecutor
from oracle_relationship_discovery.analysis.service import AnalysisResult
from oracle_relationship_discovery.models import AnalysisStats, SchemaSummary
from oracle_relationship_discovery.output.analysis_results import write_analysis_results
from oracle_relationship_discovery.output.erd_models import ErdRelationship

CONNECTION_PAYLOAD = {
    "host": "db.example.invalid",
    "port": 1521,
    "service_name": "FAKE_SERVICE",
    "username": "FAKE_USER",
    "password": "fake-phase4-password-8M!",
}


class FakeGateway:
    def verify_and_discover(self, _credentials):
        return OracleDiscoveryResult((SchemaSummary("APP", 3, 12), SchemaSummary("CORE", 5, 30)))


def relationships() -> tuple[ErdRelationship, ...]:
    return (
        ErdRelationship(
            source_schema="APP",
            source_table="REQUEST",
            source_column="PARTY_ID",
            target_schema="CORE",
            target_table="PARTY",
            target_column="ID",
            source_datatype="NUMBER",
            target_datatype="NUMBER",
            target_key_type="PRIMARY_KEY",
            cardinality="Many-to-One",
            cardinality_confidence=0.92,
            cardinality_explanation="The target is unique-like and source values repeat.",
            confidence_score=96,
            confidence_label="HIGH",
            validation_status="VALIDATED",
            match_ratio=0.9957,
            sample_size=3000,
            matched_values=2987,
            unmatched_values=13,
            source_uniqueness_ratio=0.73,
            target_uniqueness_ratio=1,
            target_sample_size=1000,
            source_null_ratio=None,
            sampling_used=True,
            name_score=34,
            datatype_score=15,
            key_score=15,
            data_overlap_score=24,
            consistency_score=4,
            structure_score=4,
            explanation="Names and datatypes align. Bounded validation strongly corroborated the link.",
        ),
        ErdRelationship(
            source_schema="APP",
            source_table="ORDER_LINE",
            source_column="ORDER_ID",
            target_schema="APP",
            target_table="ORDERS",
            target_column="ID",
            source_datatype="NUMBER",
            target_datatype="NUMBER",
            target_key_type="UNIQUE_KEY",
            cardinality="Unknown / Insufficient Evidence",
            cardinality_confidence=0,
            cardinality_explanation="Sampling was not run, so cardinality is unknown.",
            confidence_score=78,
            confidence_label="MEDIUM-HIGH",
            validation_status="NOT_RUN",
            match_ratio=None,
            sampling_used=False,
            name_score=32,
            datatype_score=15,
            key_score=13,
            structure_score=4,
            explanation="Metadata evidence supports a directional relationship.",
        ),
        ErdRelationship(
            source_schema="APP",
            source_table="AUDIT",
            source_column="TYPE_ID",
            target_schema="CORE",
            target_table="TYPE",
            target_column="ID",
            confidence_score=30,
            confidence_label="VERY LOW",
            cardinality="Unknown / Insufficient Evidence",
        ),
    )


class ArtifactExecutor(AnalysisExecutor):
    def __init__(self, root: Path, mode: str = "valid") -> None:
        self.root = root
        self.mode = mode

    def execute(self, **kwargs):
        run_directory = self.root / kwargs["run_id"]
        run_directory.mkdir(parents=True)
        artifact = run_directory / "analysis-results.json"
        if self.mode in {"valid", "empty"}:
            write_analysis_results(
                artifact,
                relationships() if self.mode == "valid" else (),
                "sampled",
                "2026-09-01T10:00:00+03:30",
            )
        elif self.mode == "corrupt":
            artifact.write_text('{"relationships": [', encoding="utf-8")
        return AnalysisResult(
            AnalysisStats(2, 8, 42, 3, 1, 0),
            relationships_in_report=2,
            mode="sampled",
            elapsed_seconds=1.5,
            run_directory=run_directory,
        )


class BlockingExecutor(AnalysisExecutor):
    def execute(self, **kwargs):
        token = kwargs["cancellation_token"]
        while True:
            token.raise_if_cancelled()
            time.sleep(0.005)


def connect_and_run(client: TestClient) -> str:
    connection_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()["connection_id"]
    response = client.post(
        "/api/runs",
        json={
            "connection_id": connection_id,
            "schemas": ["APP", "CORE"],
            "configuration": {"profile": "BALANCED"},
        },
    )
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if client.get(f"/api/runs/{run_id}").json()["state"] == "COMPLETED":
            return run_id
        time.sleep(0.01)
    raise AssertionError("run did not complete")


def test_completed_run_list_is_lightweight_ordered_and_thresholded(tmp_path: Path) -> None:
    with TestClient(
        create_app(gateway=FakeGateway(), analysis_executor=ArtifactExecutor(tmp_path))
    ) as client:
        run_id = connect_and_run(client)
        response = client.get(f"/api/runs/{run_id}/relationships")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["summary"]["relationships_in_report"] == 2
    assert [item["confidence_score"] for item in body["relationships"]] == [96, 78]
    assert "score_breakdown" not in body["relationships"][0]
    assert body["relationships"][0]["source"] == {
        "schema_name": "APP",
        "table_name": "REQUEST",
        "column_name": "PARTY_ID",
        "datatype": "NUMBER",
    }


def test_relationship_id_is_directional_stable_and_detail_is_complete(tmp_path: Path) -> None:
    with TestClient(
        create_app(gateway=FakeGateway(), analysis_executor=ArtifactExecutor(tmp_path))
    ) as client:
        run_id = connect_and_run(client)
        first = client.get(f"/api/runs/{run_id}/relationships").json()
        second = client.get(f"/api/runs/{run_id}/relationships").json()
        relationship_id = first["relationships"][0]["id"]
        detail = client.get(f"/api/runs/{run_id}/relationships/{relationship_id}").json()

    expected = hashlib.sha256(b"APP\0REQUEST\0PARTY_ID\0CORE\0PARTY\0ID").hexdigest()
    assert relationship_id == expected
    assert relationship_id == second["relationships"][0]["id"]
    assert detail["score_breakdown"] == {
        "name": 34,
        "datatype": 15,
        "target_key": 15,
        "overlap": 24,
        "consistency": 4,
        "structure": 4,
    }
    assert detail["validation"]["matched_values"] == 2987
    assert detail["validation"]["sampling_used"] is True
    assert detail["cardinality_confidence"] == 0.92
    assert detail["target_key_type"] == "PRIMARY_KEY"


def test_results_payload_contains_no_sampled_values_or_sensitive_paths(tmp_path: Path) -> None:
    marker = "raw-database-value-must-not-appear"
    with TestClient(
        create_app(gateway=FakeGateway(), analysis_executor=ArtifactExecutor(tmp_path))
    ) as client:
        run_id = connect_and_run(client)
        listing = client.get(f"/api/runs/{run_id}/relationships")
        relationship_id = listing.json()["relationships"][0]["id"]
        detail = client.get(f"/api/runs/{run_id}/relationships/{relationship_id}")

    combined = listing.text + detail.text
    assert marker not in combined
    assert str(tmp_path) not in combined
    assert CONNECTION_PAYLOAD["password"] not in combined
    assert "sampled_values" not in combined


def test_results_guard_missing_relationship(tmp_path: Path) -> None:
    with TestClient(
        create_app(gateway=FakeGateway(), analysis_executor=ArtifactExecutor(tmp_path))
    ) as client:
        run_id = connect_and_run(client)
        missing = client.get(f"/api/runs/{run_id}/relationships/{'0' * 64}")
        listing = client.get(f"/api/runs/{run_id}/relationships")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RELATIONSHIP_NOT_FOUND"
    assert listing.status_code == 200


def test_empty_completed_run_returns_an_empty_list(tmp_path: Path) -> None:
    with TestClient(
        create_app(
            gateway=FakeGateway(),
            analysis_executor=ArtifactExecutor(tmp_path, "empty"),
        )
    ) as client:
        run_id = connect_and_run(client)
        response = client.get(f"/api/runs/{run_id}/relationships")

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["relationships"] == []


def test_non_completed_run_is_rejected(tmp_path: Path) -> None:
    with TestClient(
        create_app(gateway=FakeGateway(), analysis_executor=BlockingExecutor())
    ) as client:
        connection_id = client.post("/api/connections", json=CONNECTION_PAYLOAD).json()[
            "connection_id"
        ]
        run_id = client.post(
            "/api/runs",
            json={
                "connection_id": connection_id,
                "schemas": ["APP"],
                "configuration": {"profile": "BALANCED"},
            },
        ).json()["run_id"]
        response = client.get(f"/api/runs/{run_id}/relationships")
        client.post(f"/api/runs/{run_id}/cancel")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_NOT_COMPLETED"


def test_corrupt_and_missing_artifacts_are_sanitized(tmp_path: Path) -> None:
    for mode, code in (
        ("corrupt", "RESULTS_ARTIFACT_CORRUPT"),
        ("missing", "RESULTS_ARTIFACT_UNAVAILABLE"),
    ):
        with TestClient(
            create_app(
                gateway=FakeGateway(),
                analysis_executor=ArtifactExecutor(tmp_path / mode, mode),
            )
        ) as client:
            run_id = connect_and_run(client)
            response = client.get(f"/api/runs/{run_id}/relationships")
        assert response.status_code in {409, 422}
        assert response.json()["error"]["code"] == code
        assert str(tmp_path) not in response.text


def test_parsed_results_cache_avoids_reparsing_for_detail(tmp_path: Path) -> None:
    with TestClient(
        create_app(gateway=FakeGateway(), analysis_executor=ArtifactExecutor(tmp_path))
    ) as client:
        run_id = connect_and_run(client)
        listing = client.get(f"/api/runs/{run_id}/relationships").json()
        (tmp_path / run_id / "analysis-results.json").write_text("corrupt", encoding="utf-8")
        detail = client.get(f"/api/runs/{run_id}/relationships/{listing['relationships'][0]['id']}")

    assert detail.status_code == 200
