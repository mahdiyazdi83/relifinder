from pathlib import Path

from oracle_relationship_discovery.analysis.candidate_generator import generate_candidates
from oracle_relationship_discovery.config import DEFAULT_WEIGHTS
from oracle_relationship_discovery.database.types import DatatypeFamily
from oracle_relationship_discovery.providers.oracle.metadata import OracleMetadataReader


class _Cursor:
    def __init__(self) -> None:
        self.sql = ""
        self.binds = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, binds):
        self.sql = sql
        self.binds = binds
        return self

    def fetchall(self):
        if "SELECT OWNER, TABLE_NAME, NUM_ROWS" in self.sql:
            return [("APP", "CHILD", 20, None), ("APP", "PARENT", 10, None)]
        if "SELECT OWNER, TABLE_NAME, COLUMN_NAME" in self.sql:
            return [
                ("APP", "CHILD", "PARENT_ID", "NUMBER", 22, 12, 0, "Y", 1, 8, 0),
                ("APP", "PARENT", "ID", "NUMBER", 22, 12, 0, "N", 1, 10, 0),
                ("APP", "PARENT", "CODE", "VARCHAR2", 30, None, None, "N", 2, 10, 0),
                ("APP", "PARENT", "TENANT_ID", "NUMBER", 22, 12, 0, "N", 3, 3, 0),
                ("APP", "PARENT", "LOCAL_ID", "NUMBER", 22, 12, 0, "N", 4, 10, 0),
            ]
        if "SELECT c.OWNER, c.TABLE_NAME" in self.sql:
            return [
                ("APP", "PARENT", "ID", "PK_PARENT", "P", 1, 1),
                ("APP", "PARENT", "CODE", "UQ_PARENT_CODE", "U", 1, 1),
                ("APP", "PARENT", "TENANT_ID", "PK_PARENT_TENANT", "P", 1, 2),
                ("APP", "PARENT", "LOCAL_ID", "PK_PARENT_TENANT", "P", 2, 2),
            ]
        raise AssertionError(self.sql)


class _Connection:
    def __init__(self) -> None:
        self.cursor_instance = _Cursor()

    def cursor(self):
        return self.cursor_instance


def test_oracle_metadata_golden_fixture_preserves_key_semantics_and_order() -> None:
    tables = OracleMetadataReader(_Connection()).load(("APP",))

    golden = [
        (
            table.qualified_name,
            [
                (
                    column.name,
                    column.data_type,
                    column.data_type_family,
                    column.pk_constraints,
                    column.unique_constraints,
                    column.composite_constraints,
                )
                for column in table.columns
            ],
        )
        for table in tables
    ]
    assert golden == [
        (
            "APP.CHILD",
            [("PARENT_ID", "NUMBER", DatatypeFamily.NUMERIC, (), (), ())],
        ),
        (
            "APP.PARENT",
            [
                ("ID", "NUMBER", DatatypeFamily.NUMERIC, ("PK_PARENT",), (), ()),
                ("CODE", "VARCHAR2", DatatypeFamily.TEXT, (), ("UQ_PARENT_CODE",), ()),
                (
                    "TENANT_ID",
                    "NUMBER",
                    DatatypeFamily.NUMERIC,
                    ("PK_PARENT_TENANT",),
                    (),
                    ("PK_PARENT_TENANT",),
                ),
                (
                    "LOCAL_ID",
                    "NUMBER",
                    DatatypeFamily.NUMERIC,
                    ("PK_PARENT_TENANT",),
                    (),
                    ("PK_PARENT_TENANT",),
                ),
            ],
        ),
    ]

    candidates = generate_candidates(tables, 0, DEFAULT_WEIGHTS, ())
    assert [
        (
            candidate.source.qualified_name,
            candidate.target.qualified_name,
            candidate.preliminary.total,
        )
        for candidate in candidates
    ] == [("APP.CHILD.PARENT_ID", "APP.PARENT.ID", 70.0)]


def test_oracle_driver_imports_are_confined_to_provider() -> None:
    package = Path(__file__).parents[1] / "src" / "oracle_relationship_discovery"
    importers = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if "import oracledb" in path.read_text(encoding="utf-8")
    ]
    assert importers == ["providers/oracle/connection.py"]
