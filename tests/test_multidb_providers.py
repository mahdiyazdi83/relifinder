from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from oracle_relationship_discovery.analysis.candidate_generator import generate_candidates
from oracle_relationship_discovery.config import AnalysisConfig, SamplingConfig
from oracle_relationship_discovery.database.base import DatabaseOperation
from oracle_relationship_discovery.database.factory import adapter_for
from oracle_relationship_discovery.database.types import DatatypeFamily
from oracle_relationship_discovery.models import (
    ColumnMetadata,
    RelationshipCandidate,
    ScoreBreakdown,
    TableMetadata,
    ValidationStatus,
)
from oracle_relationship_discovery.output.dbml_exporter import DbmlExporter
from oracle_relationship_discovery.output.erd_models import (
    ErdColumn,
    ErdExportOptions,
    ErdModel,
    ErdTable,
)
from oracle_relationship_discovery.providers.dbapi import DbApiRuntimePool, assert_read_only
from oracle_relationship_discovery.providers.mysql import MARIADB_ADAPTER, MYSQL_ADAPTER
from oracle_relationship_discovery.providers.mysql.connection import quote_identifier as mysql_quote
from oracle_relationship_discovery.providers.mysql.datatypes import normalize_mysql_datatype
from oracle_relationship_discovery.providers.mysql.metadata import MySQLMetadataReader
from oracle_relationship_discovery.providers.mysql.sampling import MySQLDataSampler
from oracle_relationship_discovery.providers.postgresql import POSTGRESQL_ADAPTER
from oracle_relationship_discovery.providers.postgresql.connection import (
    quote_identifier as postgres_quote,
)
from oracle_relationship_discovery.providers.postgresql.datatypes import (
    normalize_postgresql_datatype,
)
from oracle_relationship_discovery.providers.postgresql.metadata import PostgreSQLMetadataReader
from oracle_relationship_discovery.providers.postgresql.sampling import PostgreSQLDataSampler


class _Cursor:
    def __init__(self, rows_by_token: dict[str, list[tuple]] | None = None) -> None:
        self.rows_by_token = rows_by_token or {}
        self.executed: list[tuple[str, tuple]] = []
        self.sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, binds=()):
        self.sql = sql
        self.executed.append((sql, tuple(binds)))
        return self

    def fetchone(self):
        rows = self.fetchall()
        return rows[0] if rows else None

    def fetchall(self):
        for token, rows in self.rows_by_token.items():
            if token in self.sql:
                return rows
        return []


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self.cursor_instance = cursor

    def cursor(self):
        return self.cursor_instance


@pytest.mark.parametrize(
    ("database_type", "expected"),
    [
        ("postgresql", POSTGRESQL_ADAPTER),
        ("mysql", MYSQL_ADAPTER),
        ("mariadb", MARIADB_ADAPTER),
    ],
)
def test_factory_selects_new_adapters(database_type, expected) -> None:
    assert adapter_for(SimpleNamespace(type=database_type)) is expected


def test_provider_identifier_quoting_preserves_case_and_escapes_delimiters() -> None:
    assert postgres_quote('Mixed"Case') == '"Mixed""Case"'
    assert mysql_quote("Mixed`Case") == "`Mixed``Case`"
    with pytest.raises(ValueError, match="unsafe"):
        postgres_quote("bad\nname")
    with pytest.raises(ValueError, match="unsafe"):
        mysql_quote("bad\x00name")


def test_read_boundary_rejects_mutations_but_allows_quoted_keyword_identifiers() -> None:
    for statement in (
        "UPDATE app.t SET value = 1",
        "WITH changed AS (DELETE FROM app.t RETURNING *) SELECT * FROM changed",
        "SELECT 1; DROP TABLE app.t",
    ):
        with pytest.raises(ValueError, match="read-only"):
            assert_read_only(statement)
    assert_read_only('SELECT "update" FROM "MixedCase"."Table"')
    assert_read_only("SELECT `delete` FROM `app-db`.`table`")


def test_postgresql_metadata_normalizes_catalog_rows_and_mixed_case() -> None:
    cursor = _Cursor(
        {
            "GROUP BY n.nspname": [("MixedCase", 2, 3), ("pg_catalog", 1, 2)],
            "CASE WHEN c.reltuples": [
                ("MixedCase", "Child", 20, None),
                ("MixedCase", "Parent", 10, None),
            ],
            "pg_catalog.format_type": [
                ("MixedCase", "Child", "parent_id", "uuid", None, None, None, True, 1, -0.5, 0.1),
                ("MixedCase", "Parent", "id", "uuid", None, None, None, False, 1, -1.0, 0.0),
                (
                    "MixedCase",
                    "Parent",
                    "created_at",
                    "timestamp with time zone",
                    None,
                    None,
                    6,
                    False,
                    2,
                    10,
                    0.0,
                ),
            ],
            "FROM pg_catalog.pg_index": [
                ("MixedCase", "Parent", "id", "Parent_pkey", True, 1, 1),
            ],
        }
    )
    reader = PostgreSQLMetadataReader(_Connection(cursor))

    schemas = reader.discover_schemas()
    tables = reader.load(("MixedCase",))

    assert [(item.name, item.system_managed) for item in schemas] == [
        ("MixedCase", False),
        ("pg_catalog", True),
    ]
    assert [table.qualified_name for table in tables] == ["MixedCase.Child", "MixedCase.Parent"]
    parent_id = tables[1].columns[0]
    assert parent_id.data_type == "uuid"
    assert parent_id.data_type_family == DatatypeFamily.OTHER
    assert parent_id.pk_constraints == ("Parent_pkey",)
    assert parent_id.num_distinct == 10
    assert all(binds == ("MixedCase",) for sql, binds in cursor.executed if "n.nspname IN (" in sql)
    assert all("MixedCase" not in sql for sql, _binds in cursor.executed if "n.nspname IN (" in sql)


def test_mysql_and_mariadb_metadata_share_queries_but_mark_system_schemas() -> None:
    cursor = _Cursor(
        {
            "GROUP BY t.table_schema": [("AppDb", 2, 3), ("mysql", 1, 4)],
            "table_rows, NULL": [("AppDb", "child", 20, None), ("AppDb", "parent", 10, None)],
            "character_maximum_length": [
                ("AppDb", "child", "parent_id", "bigint unsigned", None, 20, 0, "YES", 1),
                ("AppDb", "parent", "id", "bigint unsigned", None, 20, 0, "NO", 1),
                ("AppDb", "parent", "payload", "json", None, None, None, "YES", 2),
            ],
            "non_unique = 0": [
                ("AppDb", "parent", "id", "PRIMARY", 0, 1, None),
                ("AppDb", "parent", "payload", "uq_prefix", 0, 1, 16),
            ],
        }
    )
    mysql = MySQLMetadataReader(_Connection(cursor))
    mariadb = MySQLMetadataReader(_Connection(cursor), mariadb=True)

    assert [(item.name, item.system_managed) for item in mysql.discover_schemas()] == [
        ("AppDb", False),
        ("mysql", True),
    ]
    assert mariadb.system_schemas != mysql.system_schemas
    tables = mysql.load(("AppDb",))
    parent = tables[1]
    assert parent.columns[0].data_type == "bigint unsigned"
    assert parent.columns[0].data_type_family == DatatypeFamily.NUMERIC
    assert parent.columns[0].pk_constraints == ("PRIMARY",)
    assert (
        parent.columns[1].unique_constraints == ()
    )  # Prefix uniqueness is not whole-value uniqueness.
    assert parent.columns[1].data_type_family == DatatypeFamily.OTHER


def _candidate() -> RelationshipCandidate:
    return RelationshipCandidate(
        ColumnMetadata("App", "Child", "parent_id", "BIGINT"),
        ColumnMetadata("App", "Parent", "id", "BIGINT", pk_constraints=("pk_parent",)),
        ScoreBreakdown(name=35, datatype=15, target_key=15),
    )


@pytest.mark.parametrize(
    ("sampler_type", "expected_fragment", "forbidden_fragment"),
    [
        (PostgreSQLDataSampler, "TABLESAMPLE SYSTEM (1)", "ORDER BY RANDOM"),
        (MySQLDataSampler, "LIMIT %s", "ORDER BY RAND"),
    ],
)
def test_sampling_is_bounded_and_target_lookup_is_batched(
    sampler_type, expected_fragment, forbidden_fragment
) -> None:
    cursor = _Cursor()

    def fetchall():
        if "SELECT DISTINCT" in cursor.sql:
            return [(cursor.executed[-1][1][0],)]
        return [(1,), (2,), (2,)]

    cursor.fetchall = fetchall
    connection = _Connection(cursor)

    @contextmanager
    def acquire():
        yield connection

    candidate = _candidate()
    sampler_type(
        acquire,
        SamplingConfig(max_source_rows=3, bind_batch_size=1, mode="sample"),
    ).validate(candidate)

    sql_text = "\n".join(sql for sql, _binds in cursor.executed)
    assert expected_fragment in sql_text
    assert forbidden_fragment not in sql_text.upper()
    assert cursor.executed[0][1] == (3,)
    assert len([sql for sql, _binds in cursor.executed if "SELECT DISTINCT" in sql]) == 2
    assert candidate.evidence.status == ValidationStatus.VALIDATED
    assert candidate.evidence.sample_size == 3
    assert not hasattr(candidate.evidence, "sampled_values")


@pytest.mark.parametrize(
    ("native_type", "normalizer", "family"),
    [
        ("uuid", normalize_postgresql_datatype, DatatypeFamily.OTHER),
        ("boolean", normalize_postgresql_datatype, DatatypeFamily.BOOLEAN),
        ("timestamp with time zone", normalize_postgresql_datatype, DatatypeFamily.DATETIME),
        ("bigint unsigned", normalize_mysql_datatype, DatatypeFamily.NUMERIC),
        ("tinyint(1)", normalize_mysql_datatype, DatatypeFamily.NUMERIC),
        ("longtext", normalize_mysql_datatype, DatatypeFamily.TEXT),
        ("json", normalize_mysql_datatype, DatatypeFamily.OTHER),
    ],
)
def test_provider_datatype_normalization(native_type, normalizer, family) -> None:
    assert normalizer(native_type) == family


def test_equivalent_normalized_metadata_produces_identical_candidates() -> None:
    analysis = AnalysisConfig()
    provider_types = {
        "postgresql": ("bigint", normalize_postgresql_datatype),
        "mysql": ("bigint", normalize_mysql_datatype),
        "mariadb": ("bigint", normalize_mysql_datatype),
    }
    outcomes = []
    for native, normalize in provider_types.values():
        tables = [
            TableMetadata(
                "app",
                "child",
                columns=[
                    ColumnMetadata(
                        "app", "child", "parent_id", native, data_type_family=normalize(native)
                    )
                ],
            ),
            TableMetadata(
                "app",
                "parent",
                columns=[
                    ColumnMetadata(
                        "app",
                        "parent",
                        "id",
                        native,
                        nullable=False,
                        pk_constraints=("pk_parent",),
                        data_type_family=normalize(native),
                    )
                ],
            ),
        ]
        candidates = generate_candidates(
            tables,
            analysis.metadata_candidate_threshold,
            analysis.weights,
            analysis.generic_entities,
        )
        outcomes.append(
            [
                (item.source.qualified_name, item.target.qualified_name, item.preliminary.total)
                for item in candidates
            ]
        )
    assert outcomes[0]
    assert outcomes[0] == outcomes[1] == outcomes[2]


def test_dbml_records_source_database_and_preserves_native_type(tmp_path: Path) -> None:
    destination = tmp_path / "postgresql.dbml"
    model = ErdModel(
        (ErdTable("public", "MixedCase", (ErdColumn("id", "uuid", nullable=False),)),),
        (),
        "postgresql",
    )

    DbmlExporter().export(model, destination, ErdExportOptions())

    text = destination.read_text(encoding="utf-8")
    assert "database_type: 'PostgreSQL'" in text
    assert "id UUID [not null]" in text
    assert "not declared constraints" in text
    assert "Oracle constraints" not in text


class _PooledConnection:
    def __init__(self) -> None:
        self.closed = False
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def test_runtime_pool_discards_failed_connections_and_closes_cleanly() -> None:
    created: list[_PooledConnection] = []

    def factory() -> _PooledConnection:
        connection = _PooledConnection()
        created.append(connection)
        return connection

    pool = DbApiRuntimePool(factory, 1, "TestDB")
    with pytest.raises(RuntimeError, match="analysis failed"), pool.acquire(1) as first:
        raise RuntimeError("analysis failed")
    assert first.closed

    with pool.acquire(1) as second:
        assert second is not first
    assert second.rollbacks == 1
    pool.close()
    assert second.closed
    with pytest.raises(RuntimeError, match="closed"), pool.acquire(1):
        pass


def test_provider_errors_are_sanitized_and_database_specific() -> None:
    secret = "password=do-not-expose host=private.example"
    postgresql = POSTGRESQL_ADAPTER.normalize_error(RuntimeError(secret), DatabaseOperation.CONNECT)
    mysql = MYSQL_ADAPTER.normalize_error(RuntimeError(secret), DatabaseOperation.CONNECT)
    mariadb = MARIADB_ADAPTER.normalize_error(RuntimeError(secret), DatabaseOperation.CONNECT)

    assert postgresql.message == "The PostgreSQL connection could not be established."
    assert mysql.message == "The MySQL connection could not be established."
    assert mariadb.message == "The MariaDB connection could not be established."
    assert all(secret not in error.message for error in (postgresql, mysql, mariadb))
