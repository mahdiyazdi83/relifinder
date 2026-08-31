"""Safe metadata artifact used for offline ERD exports."""

import json
from pathlib import Path

from oracle_relationship_discovery.models import ColumnMetadata, TableMetadata

FORMAT_VERSION = 1


def write_schema_metadata(path: Path, tables: list[TableMetadata], generated_at: str) -> None:
    payload = {
        "format_version": FORMAT_VERSION,
        "generated_at": generated_at,
        "privacy": "Metadata only; no sampled values are stored.",
        "tables": [
            {
                "schema": table.schema,
                "name": table.name,
                "estimated_rows": table.estimated_rows,
                "last_analyzed": table.last_analyzed.isoformat() if table.last_analyzed else None,
                "columns": [
                    {
                        "name": c.name,
                        "data_type": c.data_type,
                        "data_length": c.data_length,
                        "precision": c.precision,
                        "scale": c.scale,
                        "nullable": c.nullable,
                        "position": c.position,
                        "pk_constraints": list(c.pk_constraints),
                        "unique_constraints": list(c.unique_constraints),
                        "composite_constraints": list(c.composite_constraints),
                    }
                    for c in table.columns
                ],
            }
            for table in sorted(tables, key=lambda item: (item.schema, item.name))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_schema_metadata(path: Path) -> list[TableMetadata]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported schema metadata format version")
    tables = []
    for raw in payload.get("tables", []):
        table = TableMetadata(str(raw["schema"]), str(raw["name"]), raw.get("estimated_rows"))
        table.columns = [
            ColumnMetadata(
                table.schema,
                table.name,
                str(c["name"]),
                str(c["data_type"]),
                c.get("data_length"),
                c.get("precision"),
                c.get("scale"),
                bool(c.get("nullable", True)),
                int(c.get("position", 0)),
                tuple(c.get("pk_constraints", [])),
                tuple(c.get("unique_constraints", [])),
                tuple(c.get("composite_constraints", [])),
            )
            for c in raw.get("columns", [])
        ]
        tables.append(table)
    return tables
