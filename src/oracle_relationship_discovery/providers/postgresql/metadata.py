"""PostgreSQL catalog metadata normalized into ReliFinder models."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from oracle_relationship_discovery.models import ColumnMetadata, SchemaSummary, TableMetadata
from oracle_relationship_discovery.providers.dbapi import execute_read
from oracle_relationship_discovery.providers.postgresql.datatypes import (
    normalize_postgresql_datatype,
)

_POSTGRES_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}


def _placeholders(values: tuple[str, ...]) -> str:
    return ", ".join("%s" for _value in values)


def is_system_schema(name: str) -> bool:
    lowered = name.lower()
    return lowered in _POSTGRES_SYSTEM_SCHEMAS or lowered.startswith(
        ("pg_toast", "pg_temp_", "pg_toast_temp_")
    )


class PostgreSQLMetadataReader:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def verify_required_access(self) -> None:
        sql = """
            SELECT 1
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE FALSE
        """
        with self.connection.cursor() as cursor:
            execute_read(cursor, sql).fetchone()

    def discover_schemas(self) -> list[SchemaSummary]:
        sql = """
            SELECT n.nspname,
                   COUNT(DISTINCT c.oid) AS table_count,
                   COUNT(a.attnum) AS column_count
            FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid
            LEFT JOIN pg_catalog.pg_attribute a
              ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE c.relkind IN ('r', 'p')
            GROUP BY n.nspname
            ORDER BY n.nspname
        """
        with self.connection.cursor() as cursor:
            rows = execute_read(cursor, sql).fetchall()
        return [
            SchemaSummary(str(name), int(tables), int(columns), is_system_schema(str(name)))
            for name, tables, columns in rows
        ]

    def load(self, schemas: tuple[str, ...]) -> list[TableMetadata]:
        if not schemas:
            return []
        placeholders = _placeholders(schemas)
        tables_sql = f"""
            SELECT n.nspname, c.relname,
                   CASE WHEN c.reltuples < 0 THEN NULL ELSE c.reltuples::bigint END,
                   stats.last_analyze
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_stat_all_tables stats ON stats.relid = c.oid
            WHERE c.relkind IN ('r', 'p') AND n.nspname IN ({placeholders})
            ORDER BY n.nspname, c.relname
        """
        columns_sql = f"""
            SELECT n.nspname, c.relname, a.attname,
                   pg_catalog.format_type(a.atttypid, a.atttypmod),
                   information_schema._pg_char_max_length(a.atttypid, a.atttypmod),
                   information_schema._pg_numeric_precision(a.atttypid, a.atttypmod),
                   information_schema._pg_numeric_scale(a.atttypid, a.atttypmod),
                   NOT a.attnotnull, a.attnum,
                   stats.n_distinct, stats.null_frac
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_stats stats
              ON stats.schemaname = n.nspname
             AND stats.tablename = c.relname
             AND stats.attname = a.attname
            WHERE c.relkind IN ('r', 'p')
              AND a.attnum > 0 AND NOT a.attisdropped
              AND n.nspname IN ({placeholders})
            ORDER BY n.nspname, c.relname, a.attnum
        """
        indexes_sql = f"""
            SELECT n.nspname, c.relname, a.attname, idx.relname,
                   i.indisprimary, keys.ordinality, i.indnkeyatts
            FROM pg_catalog.pg_index i
            JOIN pg_catalog.pg_class c ON c.oid = i.indrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_class idx ON idx.oid = i.indexrelid
            JOIN LATERAL unnest(i.indkey) WITH ORDINALITY keys(attnum, ordinality) ON TRUE
            JOIN pg_catalog.pg_attribute a
              ON a.attrelid = c.oid AND a.attnum = keys.attnum
             AND keys.ordinality <= i.indnkeyatts
            WHERE i.indisunique AND i.indisvalid
              AND i.indpred IS NULL AND i.indexprs IS NULL
              AND n.nspname IN ({placeholders})
            ORDER BY n.nspname, c.relname, idx.relname, keys.ordinality
        """
        binds = tuple(schemas)
        with self.connection.cursor() as cursor:
            table_rows = execute_read(cursor, tables_sql, binds).fetchall()
            column_rows = execute_read(cursor, columns_sql, binds).fetchall()
            index_rows = execute_read(cursor, indexes_sql, binds).fetchall()

        index_map: dict[tuple[str, str, str], list[tuple[str, bool, int]]] = defaultdict(list)
        for schema, table, column, name, primary, _position, count in index_rows:
            index_map[(str(schema), str(table), str(column))].append(
                (str(name), bool(primary), int(count))
            )
        table_map = {
            (str(schema), str(name)): TableMetadata(
                str(schema), str(name), _optional_int(rows), analyzed
            )
            for schema, name, rows, analyzed in table_rows
        }
        for row in column_rows:
            (
                schema,
                table,
                name,
                native_type,
                length,
                precision,
                scale,
                nullable,
                position,
                nd,
                nf,
            ) = row
            key = (str(schema), str(table))
            target = table_map.get(key)
            if target is None:
                continue
            indexes = index_map.get((key[0], key[1], str(name)), [])
            estimated_rows = target.estimated_rows
            target.columns.append(
                ColumnMetadata(
                    schema=key[0],
                    table=key[1],
                    name=str(name),
                    data_type=str(native_type),
                    data_length=_optional_int(length),
                    precision=_optional_int(precision),
                    scale=_optional_int(scale),
                    nullable=bool(nullable),
                    position=int(position),
                    pk_constraints=tuple(item[0] for item in indexes if item[1]),
                    unique_constraints=tuple(item[0] for item in indexes if not item[1]),
                    composite_constraints=tuple(item[0] for item in indexes if item[2] > 1),
                    num_distinct=_postgres_distinct(nd, estimated_rows),
                    num_nulls=_postgres_nulls(nf, estimated_rows),
                    data_type_family=normalize_postgresql_datatype(str(native_type)),
                )
            )
        return [table_map[key] for key in sorted(table_map)]


def _optional_int(value: Any) -> int | None:
    return None if value is None else max(0, int(value))


def _postgres_distinct(value: Any, rows: int | None) -> int | None:
    if value is None:
        return None
    distinct = float(value)
    if distinct >= 0:
        return int(distinct)
    return round(abs(distinct) * rows) if rows is not None else None


def _postgres_nulls(value: Any, rows: int | None) -> int | None:
    if value is None or rows is None:
        return None
    return round(float(value) * rows)
