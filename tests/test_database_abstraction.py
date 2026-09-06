from contextlib import contextmanager
from pathlib import Path

import pytest

import oracle_relationship_discovery.analysis.service as analysis_service
from oracle_relationship_discovery.analysis.service import AnalysisProgress, run_analysis
from oracle_relationship_discovery.config import (
    AppConfig,
    DatabaseConfig,
    SamplingConfig,
    load_config,
)
from oracle_relationship_discovery.database.base import DatabaseError, DatabaseOperation
from oracle_relationship_discovery.database.factory import adapter_for
from oracle_relationship_discovery.database.types import DatatypeFamily
from oracle_relationship_discovery.models import ColumnMetadata, TableMetadata
from oracle_relationship_discovery.providers.oracle import ORACLE_ADAPTER


class _MetadataReader:
    def load(self, schemas: tuple[str, ...]) -> list[TableMetadata]:
        assert schemas == ("APP",)
        return [
            TableMetadata(
                "APP",
                "CHILD",
                columns=[
                    ColumnMetadata(
                        "APP",
                        "CHILD",
                        "PARENT_ID",
                        "synthetic_int",
                        data_type_family=DatatypeFamily.NUMERIC,
                    )
                ],
            ),
            TableMetadata(
                "APP",
                "PARENT",
                columns=[
                    ColumnMetadata(
                        "APP",
                        "PARENT",
                        "ID",
                        "synthetic_int",
                        nullable=False,
                        pk_constraints=("PK_PARENT",),
                        data_type_family=DatatypeFamily.NUMERIC,
                    )
                ],
            ),
        ]


class _SyntheticAdapter:
    type_name = "synthetic"
    display_name = "Synthetic"

    def connection_pool(self, *_args):
        raise AssertionError("an injected connection must be used")

    def metadata_reader(self, _connection):
        return _MetadataReader()

    def candidate_sampler(self, *_args):
        raise AssertionError("sampling is disabled")

    def normalize_error(self, _exc, _operation):
        return DatabaseError("SYNTHETIC", "Synthetic failure.")


@contextmanager
def _acquire():
    yield object()


def test_analysis_engine_runs_through_database_adapter(tmp_path: Path) -> None:
    progress: list[AnalysisProgress] = []
    config = AppConfig(
        database=DatabaseConfig("unused", 1, "unused", "unused", "UNUSED"),
        schemas=("APP",),
        sampling=SamplingConfig(enabled=False),
    )

    result = run_analysis(
        config,
        tmp_path,
        acquire_connection=_acquire,
        progress_callback=progress.append,
        database_adapter=_SyntheticAdapter(),
        generated_at="2026-09-06T12:00:00+03:30",
    )

    assert result.relationships_in_report == 1
    assert progress[0].message == "Reading Synthetic metadata"
    assert progress[1].message == "Synthetic metadata loaded"
    assert (tmp_path / "relationships.csv").is_file()
    assert (tmp_path / "relationship-report.html").is_file()


def test_config_defaults_to_oracle_and_factory_rejects_unknown_type() -> None:
    config = DatabaseConfig("host", 1521, "service", "user", "PASSWORD")
    assert config.type == "oracle"
    assert adapter_for(config) is ORACLE_ADAPTER

    unsupported = DatabaseConfig("host", 1521, "service", "user", "PASSWORD", type="postgresql")
    with pytest.raises(ValueError, match="Unsupported database type"):
        adapter_for(unsupported)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NUMBER", DatatypeFamily.NUMERIC),
        ("VARCHAR2", DatatypeFamily.TEXT),
        ("TIMESTAMP WITH LOCAL TIME ZONE", DatatypeFamily.DATETIME),
        ("RAW", DatatypeFamily.BINARY),
        ("XMLTYPE", DatatypeFamily.OTHER),
    ],
)
def test_canonical_metadata_keeps_native_type_and_normalizes_family(raw, expected) -> None:
    column = ColumnMetadata("APP", "T", "C", raw)
    assert column.data_type == raw
    assert column.data_type_family == expected


def test_oracle_error_normalization_is_sanitized() -> None:
    error = ORACLE_ADAPTER.normalize_error(
        RuntimeError("DPY-6001 descriptor=(sensitive)"),
        DatabaseOperation.CONNECT,
    )
    assert (error.code, error.status_code) == ("SERVICE_NOT_FOUND", 503)
    assert "sensitive" not in error.message


def test_legacy_yaml_defaults_to_oracle_and_unknown_type_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  host: localhost
  service_name: XE
  username: reader
  password_env: TEST_PASSWORD
schemas: [APP]
""".strip(),
        encoding="utf-8",
    )
    assert load_config(config_path).database.type == "oracle"

    config_path.write_text(
        """
database:
  type: postgresql
  host: localhost
  service_name: demo
  username: reader
  password_env: TEST_PASSWORD
schemas: [APP]
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="database.type must be 'oracle'"):
        load_config(config_path)


def test_analysis_module_has_no_direct_oracle_provider_dependency() -> None:
    source = Path(analysis_service.__file__).read_text(encoding="utf-8")
    assert "providers.oracle" not in source
    assert "oracle_relationship_discovery.db" not in source
    assert "ALL_TABLES" not in source
