"""Safe metadata artifact used for offline ERD exports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from oracle_relationship_discovery.models import ColumnMetadata, TableMetadata

FORMAT_VERSION = 1
PRIVACY_NOTICE = "Metadata only; no sampled values are stored."


class SchemaMetadataError(ValueError):
    """Raised when schema metadata cannot be interpreted safely."""


def write_schema_metadata(
    path: Path,
    tables: list[TableMetadata],
    generated_at: str,
) -> None:
    payload = {
        "format_version": FORMAT_VERSION,
        "generated_at": generated_at,
        "privacy": PRIVACY_NOTICE,
        "tables": [
            {
                "schema": table.schema,
                "name": table.name,
                "estimated_rows": table.estimated_rows,
                "last_analyzed": (table.last_analyzed.isoformat() if table.last_analyzed else None),
                "columns": [
                    {
                        "name": column.name,
                        "data_type": column.data_type,
                        "data_length": column.data_length,
                        "precision": column.precision,
                        "scale": column.scale,
                        "nullable": column.nullable,
                        "position": column.position,
                        "pk_constraints": sorted(column.pk_constraints),
                        "unique_constraints": sorted(column.unique_constraints),
                        "composite_constraints": sorted(column.composite_constraints),
                        "num_distinct": column.num_distinct,
                        "num_nulls": column.num_nulls,
                    }
                    for column in sorted(
                        table.columns,
                        key=lambda item: (item.position, item.name),
                    )
                ],
            }
            for table in sorted(tables, key=lambda item: (item.schema, item.name))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_schema_metadata(path: Path) -> list[TableMetadata]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaMetadataError(
            f"Invalid schema metadata JSON at line {exc.lineno}, column {exc.colno}: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise SchemaMetadataError("Schema metadata artifact must contain a JSON object")
    version = payload.get("format_version")
    if version != FORMAT_VERSION:
        raise SchemaMetadataError(
            f"Unsupported schema metadata format_version {version!r}; expected {FORMAT_VERSION}"
        )
    raw_tables = payload.get("tables")
    if not isinstance(raw_tables, list):
        raise SchemaMetadataError("Schema metadata artifact field 'tables' must be a list")

    tables = []
    for table_index, raw in enumerate(raw_tables):
        if not isinstance(raw, dict):
            raise SchemaMetadataError(f"Schema metadata table #{table_index + 1} must be an object")
        try:
            last_analyzed = (
                datetime.fromisoformat(str(raw["last_analyzed"]))
                if raw.get("last_analyzed")
                else None
            )
            table = TableMetadata(
                schema=str(raw["schema"]),
                name=str(raw["name"]),
                estimated_rows=_optional_int(raw.get("estimated_rows")),
                last_analyzed=last_analyzed,
            )
            raw_columns = raw.get("columns", [])
            if not isinstance(raw_columns, list):
                raise SchemaMetadataError("columns must be a list")
            table.columns = [
                _read_column(table, column, table_index, column_index)
                for column_index, column in enumerate(raw_columns)
            ]
        except KeyError as exc:
            raise SchemaMetadataError(
                f"Schema metadata table #{table_index + 1} is missing {exc.args[0]}"
            ) from exc
        except (TypeError, ValueError) as exc:
            if isinstance(exc, SchemaMetadataError):
                raise
            raise SchemaMetadataError(
                f"Schema metadata table #{table_index + 1} contains an invalid value"
            ) from exc
        tables.append(table)
    return sorted(tables, key=lambda item: (item.schema, item.name))


def _read_column(
    table: TableMetadata,
    raw: object,
    table_index: int,
    column_index: int,
) -> ColumnMetadata:
    if not isinstance(raw, dict):
        raise SchemaMetadataError(
            f"Schema metadata table #{table_index + 1} column #{column_index + 1} must be an object"
        )
    try:
        return ColumnMetadata(
            schema=table.schema,
            table=table.name,
            name=str(raw["name"]),
            data_type=str(raw["data_type"]),
            data_length=_optional_int(raw.get("data_length")),
            precision=_optional_int(raw.get("precision")),
            scale=_optional_int(raw.get("scale")),
            nullable=bool(raw.get("nullable", True)),
            position=int(raw.get("position", 0)),
            pk_constraints=tuple(sorted(str(item) for item in raw.get("pk_constraints", []))),
            unique_constraints=tuple(
                sorted(str(item) for item in raw.get("unique_constraints", []))
            ),
            composite_constraints=tuple(
                sorted(str(item) for item in raw.get("composite_constraints", []))
            ),
            num_distinct=_optional_int(raw.get("num_distinct")),
            num_nulls=_optional_int(raw.get("num_nulls")),
        )
    except KeyError as exc:
        raise SchemaMetadataError(
            f"Schema metadata table #{table_index + 1} column "
            f"#{column_index + 1} is missing {exc.args[0]}"
        ) from exc


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)
