from oracle_relationship_discovery.db.metadata_repository import MetadataRepository


class FakeCursor:
    def __init__(self, *, maintained_supported: bool = True) -> None:
        self.sql = ""
        self.maintained_supported = maintained_supported
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, _binds):
        self.sql = sql
        self.executed.append(sql)
        if "ORACLE_MAINTAINED" in sql and not self.maintained_supported:
            raise RuntimeError("ORA-00904")
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        if "ORACLE_MAINTAINED" in self.sql:
            return [("SYS",), ("XDB",)]
        if "FROM ALL_TAB_COLUMNS c" in self.sql:
            return [("APP", 24), ("SYS", 400), ("XDB", 120)]
        if "FROM ALL_TABLES" in self.sql and "GROUP BY OWNER" in self.sql:
            return [("SYS", 50), ("APP", 5), ("APP", 7), ("XDB", 20)]
        return []


class FakeConnection:
    def __init__(self, *, maintained_supported: bool = True) -> None:
        self.fake_cursor = FakeCursor(maintained_supported=maintained_supported)

    def cursor(self):
        return self.fake_cursor


def test_required_metadata_access_uses_only_selects() -> None:
    connection = FakeConnection()
    MetadataRepository(connection).verify_required_access()

    assert len(connection.fake_cursor.executed) == 4
    assert all(
        sql.strip().startswith("SELECT 1 FROM ALL_") for sql in connection.fake_cursor.executed
    )


def test_schema_discovery_is_deterministic_and_marks_oracle_maintained() -> None:
    summaries = MetadataRepository(FakeConnection()).discover_schemas()

    assert [
        (item.name, item.table_count, item.column_count, item.oracle_maintained)
        for item in summaries
    ] == [
        ("APP", 7, 24, False),
        ("SYS", 50, 400, True),
        ("XDB", 20, 120, True),
    ]


def test_old_oracle_fallback_only_marks_conservative_system_schemas() -> None:
    summaries = MetadataRepository(FakeConnection(maintained_supported=False)).discover_schemas()
    system = {item.name for item in summaries if item.oracle_maintained}

    assert system == {"SYS"}
