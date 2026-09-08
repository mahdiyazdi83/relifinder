"""MySQL/MariaDB information_schema metadata normalized for ReliFinder."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from oracle_relationship_discovery.models import ColumnMetadata, SchemaSummary, TableMetadata
from oracle_relationship_discovery.providers.dbapi import execute_read
from oracle_relationship_discovery.providers.mysql.datatypes import normalize_mysql_datatype

MYSQL_SYSTEM_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}
MARIADB_SYSTEM_SCHEMAS = MYSQL_SYSTEM_SCHEMAS | {"mariadb_schema"}


def _placeholders(values: tuple[str, ...]) -> str:
    return ", ".join("%s" for _value in values)


class MySQLMetadataReader:
    def __init__(self, connection: Any, *, mariadb: bool = False) -> None:
        self.connection = connection
        self.system_schemas = MARIADB_SYSTEM_SCHEMAS if mariadb else MYSQL_SYSTEM_SCHEMAS

    def verify_required_access(self) -> None:
        with self.connection.cursor() as cursor:
            execute_read(cursor, "SELECT 1 FROM information_schema.tables WHERE 1 = 0").fetchone()
            execute_read(cursor, "SELECT 1 FROM information_schema.columns WHERE 1 = 0").fetchone()
            execute_read(
                cursor, "SELECT 1 FROM information_schema.statistics WHERE 1 = 0"
            ).fetchone()

    def discover_schemas(self) -> list[SchemaSummary]:
        sql = """
            SELECT t.table_schema, COUNT(DISTINCT t.table_name), COUNT(c.column_name)
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c
              ON c.table_schema = t.table_schema AND c.table_name = t.table_name
            WHERE t.table_type = 'BASE TABLE'
            GROUP BY t.table_schema
            ORDER BY t.table_schema
        """
        with self.connection.cursor() as cursor:
            rows = execute_read(cursor, sql).fetchall()
        return [
            SchemaSummary(
                str(name),
                int(tables),
                int(columns),
                str(name).lower() in self.system_schemas,
            )
            for name, tables, columns in rows
        ]

    def load(self, schemas: tuple[str, ...]) -> list[TableMetadata]:
        if not schemas:
            return []
        placeholders = _placeholders(schemas)
        tables_sql = f"""
            SELECT table_schema, table_name, table_rows, NULL
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND table_schema IN ({placeholders})
            ORDER BY table_schema, table_name
        """
        columns_sql = f"""
            SELECT table_schema, table_name, column_name, column_type,
                   character_maximum_length, numeric_precision, numeric_scale,
                   is_nullable, ordinal_position
            FROM information_schema.columns
            WHERE table_schema IN ({placeholders})
            ORDER BY table_schema, table_name, ordinal_position
        """
        indexes_sql = f"""
            SELECT table_schema, table_name, column_name, index_name, non_unique, seq_in_index, sub_part
            FROM information_schema.statistics
            WHERE table_schema IN ({placeholders})
              AND non_unique = 0 AND column_name IS NOT NULL
            ORDER BY table_schema, table_name, index_name, seq_in_index
        """
        binds = tuple(schemas)
        with self.connection.cursor() as cursor:
            table_rows = execute_read(cursor, tables_sql, binds).fetchall()
            column_rows = execute_read(cursor, columns_sql, binds).fetchall()
            index_rows = execute_read(cursor, indexes_sql, binds).fetchall()

        grouped_indexes: dict[tuple[str, str, str], list[tuple[str, bool, int]]] = defaultdict(list)
        index_sizes: dict[tuple[str, str, str], int] = defaultdict(int)
        prefix_indexes = {
            (str(schema), str(table), str(name))
            for schema, table, _column, name, _non_unique, _position, sub_part in index_rows
            if sub_part is not None
        }
        for schema, table, _column, name, _non_unique, _position, _sub_part in index_rows:
            index_sizes[(str(schema), str(table), str(name))] += 1
        for schema, table, column, name, _non_unique, _position, _sub_part in index_rows:
            index_identity = (str(schema), str(table), str(name))
            if index_identity in prefix_indexes:
                continue
            key = (str(schema), str(table), str(column))
            index_name = str(name)
            grouped_indexes[key].append(
                (
                    index_name,
                    index_name.upper() == "PRIMARY",
                    index_sizes[(key[0], key[1], index_name)],
                )
            )

        table_map = {
            (str(schema), str(name)): TableMetadata(
                str(schema), str(name), _optional_int(rows), updated
            )
            for schema, name, rows, updated in table_rows
        }
        for row in column_rows:
            schema, table, name, native_type, length, precision, scale, nullable, position = row
            key = (str(schema), str(table))
            target = table_map.get(key)
            if target is None:
                continue
            indexes = grouped_indexes.get((key[0], key[1], str(name)), [])
            target.columns.append(
                ColumnMetadata(
                    schema=key[0],
                    table=key[1],
                    name=str(name),
                    data_type=str(native_type),
                    data_length=_optional_int(length),
                    precision=_optional_int(precision),
                    scale=_optional_int(scale),
                    nullable=str(nullable).upper() == "YES",
                    position=int(position),
                    pk_constraints=tuple(item[0] for item in indexes if item[1]),
                    unique_constraints=tuple(item[0] for item in indexes if not item[1]),
                    composite_constraints=tuple(item[0] for item in indexes if item[2] > 1),
                    data_type_family=normalize_mysql_datatype(str(native_type)),
                )
            )
        return [table_map[key] for key in sorted(table_map)]


def _optional_int(value: Any) -> int | None:
    return None if value is None else max(0, int(value))
