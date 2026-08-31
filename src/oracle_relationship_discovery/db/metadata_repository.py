"""Read metadata from broadly available ALL_* Oracle views."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from oracle_relationship_discovery.db.connection import execute_select
from oracle_relationship_discovery.models import ColumnMetadata, SchemaSummary, TableMetadata

REQUIRED_METADATA_VIEWS = (
    "ALL_TABLES",
    "ALL_TAB_COLUMNS",
    "ALL_CONSTRAINTS",
    "ALL_CONS_COLUMNS",
)
CONSERVATIVE_SYSTEM_SCHEMAS = {"SYS", "SYSTEM"}


def _in_clause(prefix: str, values: tuple[str, ...]) -> tuple[str, dict[str, str]]:
    binds = {f"{prefix}{index}": value for index, value in enumerate(values)}
    placeholders = ", ".join(f":{name}" for name in binds)
    return placeholders, binds


class MetadataRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def verify_required_access(self) -> None:
        """Verify that every metadata view used by ReliFinder can be selected."""
        with self.connection.cursor() as cursor:
            for view in REQUIRED_METADATA_VIEWS:
                execute_select(cursor, f"SELECT 1 FROM {view} WHERE 1 = 0").fetchone()

    def discover_schemas(self) -> list[SchemaSummary]:
        """Return deterministic metadata-only summaries for owners with visible tables."""
        tables_sql = """
            SELECT OWNER, COUNT(*)
            FROM ALL_TABLES
            GROUP BY OWNER
            ORDER BY OWNER
        """
        columns_sql = """
            SELECT c.OWNER, COUNT(*)
            FROM ALL_TAB_COLUMNS c
            JOIN ALL_TABLES t
              ON t.OWNER = c.OWNER AND t.TABLE_NAME = c.TABLE_NAME
            GROUP BY c.OWNER
            ORDER BY c.OWNER
        """
        maintained_sql = """
            SELECT USERNAME
            FROM ALL_USERS
            WHERE ORACLE_MAINTAINED = 'Y'
            ORDER BY USERNAME
        """
        with self.connection.cursor() as cursor:
            table_rows = execute_select(cursor, tables_sql).fetchall()
            column_rows = execute_select(cursor, columns_sql).fetchall()
            try:
                maintained_rows = execute_select(cursor, maintained_sql).fetchall()
            except Exception:  # noqa: BLE001 - optional column is absent before Oracle 12c.
                maintained_rows = tuple((name,) for name in CONSERVATIVE_SYSTEM_SCHEMAS)

        columns_by_owner = {str(owner): int(count) for owner, count in column_rows}
        maintained = {str(row[0]) for row in maintained_rows}
        summaries = {
            str(owner): SchemaSummary(
                name=str(owner),
                table_count=int(table_count),
                column_count=columns_by_owner.get(str(owner), 0),
                oracle_maintained=str(owner) in maintained,
            )
            for owner, table_count in table_rows
        }
        return [summaries[name] for name in sorted(summaries)]

    def load(self, schemas: tuple[str, ...]) -> list[TableMetadata]:
        placeholders, binds = _in_clause("schema", schemas)
        tables_sql = f"""
            SELECT OWNER, TABLE_NAME, NUM_ROWS, LAST_ANALYZED
            FROM ALL_TABLES
            WHERE OWNER IN ({placeholders})
            ORDER BY OWNER, TABLE_NAME
        """
        columns_sql = f"""
            SELECT OWNER, TABLE_NAME, COLUMN_NAME, DATA_TYPE, DATA_LENGTH,
                   DATA_PRECISION, DATA_SCALE, NULLABLE, COLUMN_ID,
                   NUM_DISTINCT, NUM_NULLS
            FROM ALL_TAB_COLUMNS
            WHERE OWNER IN ({placeholders})
            ORDER BY OWNER, TABLE_NAME, COLUMN_ID
        """
        constraints_sql = f"""
            SELECT c.OWNER, c.TABLE_NAME, cc.COLUMN_NAME, c.CONSTRAINT_NAME,
                   c.CONSTRAINT_TYPE, cc.POSITION, counts.COLUMN_COUNT
            FROM ALL_CONSTRAINTS c
            JOIN ALL_CONS_COLUMNS cc
              ON cc.OWNER = c.OWNER AND cc.CONSTRAINT_NAME = c.CONSTRAINT_NAME
             AND cc.TABLE_NAME = c.TABLE_NAME
            JOIN (
                SELECT OWNER, TABLE_NAME, CONSTRAINT_NAME, COUNT(*) AS COLUMN_COUNT
                FROM ALL_CONS_COLUMNS
                WHERE OWNER IN ({placeholders})
                GROUP BY OWNER, TABLE_NAME, CONSTRAINT_NAME
            ) counts
              ON counts.OWNER = c.OWNER AND counts.TABLE_NAME = c.TABLE_NAME
             AND counts.CONSTRAINT_NAME = c.CONSTRAINT_NAME
            WHERE c.OWNER IN ({placeholders})
              AND c.CONSTRAINT_TYPE IN ('P', 'U')
              AND c.STATUS = 'ENABLED'
            ORDER BY c.OWNER, c.TABLE_NAME, c.CONSTRAINT_NAME, cc.POSITION
        """

        with self.connection.cursor() as cursor:
            table_rows = execute_select(cursor, tables_sql, binds).fetchall()
            column_rows = execute_select(cursor, columns_sql, binds).fetchall()
            constraint_rows = execute_select(cursor, constraints_sql, binds).fetchall()

        constraint_map: dict[tuple[str, str, str], list[tuple[str, str, int]]] = defaultdict(list)
        for owner, table, column, name, kind, _position, count in constraint_rows:
            constraint_map[(owner, table, column)].append((name, kind, count))

        table_map = {
            (owner, name): TableMetadata(owner, name, estimated_rows, last_analyzed)
            for owner, name, estimated_rows, last_analyzed in table_rows
        }
        # ALL_TAB_COLUMNS can expose objects absent from ALL_TABLES; only requested tables are retained.
        for row in column_rows:
            (
                owner,
                table,
                name,
                data_type,
                length,
                precision,
                scale,
                nullable,
                position,
                num_distinct,
                num_nulls,
            ) = row
            if (owner, table) not in table_map:
                continue
            constraints = constraint_map.get((owner, table, name), [])
            pk = tuple(item[0] for item in constraints if item[1] == "P")
            unique = tuple(item[0] for item in constraints if item[1] == "U")
            composite = tuple(item[0] for item in constraints if item[2] > 1)
            table_map[(owner, table)].columns.append(
                ColumnMetadata(
                    schema=owner,
                    table=table,
                    name=name,
                    data_type=data_type,
                    data_length=length,
                    precision=precision,
                    scale=scale,
                    nullable=nullable == "Y",
                    position=position,
                    pk_constraints=pk,
                    unique_constraints=unique,
                    composite_constraints=composite,
                    num_distinct=num_distinct,
                    num_nulls=num_nulls,
                )
            )
        return list(table_map.values())
