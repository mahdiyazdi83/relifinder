"""DBML exporter with source-native types and explainable references."""

from __future__ import annotations

import re
from pathlib import Path

from oracle_relationship_discovery.output.erd_models import (
    ErdExportDiagnostics,
    ErdExportOptions,
    ErdModel,
    ErdTable,
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
_SAFE_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\([0-9]+(?:,[0-9]+)?\))?$")
_RESERVED_IDENTIFIERS = {
    "ENUM",
    "INDEXES",
    "NOTE",
    "PROJECT",
    "REF",
    "TABLE",
    "TABLEGROUP",
    "TABLEPARTIAL",
}


def dbml_identifier(value: str) -> str:
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"Invalid DBML identifier: {value!r}")
    if _SAFE_IDENTIFIER.fullmatch(value) and value.upper() not in _RESERVED_IDENTIFIERS:
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def native_type(column) -> str:
    kind = re.sub(r"\s+", " ", column.data_type.upper().strip())
    if not kind:
        return "UNKNOWN"
    if kind == "NUMBER" and column.precision is not None:
        kind += (
            f"({column.precision},{column.scale})"
            if column.scale is not None
            else f"({column.precision})"
        )
    elif kind == "FLOAT" and column.precision is not None:
        kind += f"({column.precision})"
    elif (
        kind in {"VARCHAR2", "VARCHAR", "NVARCHAR2", "CHAR", "NCHAR", "RAW"} and column.data_length
    ):
        kind += f"({column.data_length})"
    elif kind in {"TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP WITH LOCAL TIME ZONE"}:
        fractional_precision = column.scale if column.scale is not None else column.precision
        if fractional_precision is not None:
            kind = kind.replace("TIMESTAMP", f"TIMESTAMP({fractional_precision})", 1)
    return kind if _SAFE_TYPE.fullmatch(kind) else '"' + kind.replace('"', '\\"') + '"'


# Backward-compatible public alias.
oracle_type = native_type


def _database_label(database_type: str) -> str:
    return {
        "oracle": "Oracle",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mariadb": "MariaDB",
    }.get(database_type.lower(), database_type)


def cardinality_operator(cardinality: str) -> str | None:
    normalized = re.sub(r"[^A-Z0-9]+", "_", cardinality.upper()).strip("_")
    return {
        "MANY_TO_ONE": ">",
        "ONE_TO_MANY": "<",
        "ONE_TO_ONE": "-",
    }.get(normalized)


def _qualified(schema: str, table: str, column: str | None = None) -> str:
    value = f"{dbml_identifier(schema)}.{dbml_identifier(table)}"
    return f"{value}.{dbml_identifier(column)}" if column else value


def _dbml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _constraint_lines(table: ErdTable) -> list[str]:
    groups: dict[str, dict[str, object]] = {}
    for column in sorted(table.columns, key=lambda item: (item.position, item.name)):
        for name in sorted(column.composite_constraints):
            group = groups.setdefault(name, {"pk": False, "columns": []})
            group["pk"] = bool(group["pk"]) or name in column.pk_constraints
            columns = group["columns"]
            assert isinstance(columns, list)
            columns.append(column.name)
    if not groups:
        return []

    lines = ["  indexes {"]
    for name in sorted(groups):
        group = groups[name]
        columns = group["columns"]
        assert isinstance(columns, list)
        joined = ", ".join(dbml_identifier(column) for column in columns)
        kind = "pk" if group["pk"] else "unique"
        lines.append(f"    ({joined}) [{kind}, name: '{_dbml_string(name)}']")
    lines.append("  }")
    return lines


class DbmlExporter:
    def export(
        self,
        model: ErdModel,
        destination: Path,
        options: ErdExportOptions,
        *,
        external_to_schema: str | None = None,
        diagnostics: ErdExportDiagnostics | None = None,
    ) -> int:
        unknown = sum(
            cardinality_operator(item.cardinality) is None for item in model.relationships
        )
        rendered = len(model.relationships) - unknown
        details = diagnostics or ErdExportDiagnostics(
            input_relationships=len(model.relationships),
            duplicate_relationships_omitted=0,
            highest_detected_confidence=max(
                (item.confidence_score for item in model.relationships),
                default=None,
            ),
            below_confidence_threshold=0,
            omitted_by_validation_filter=0,
            omitted_by_scope_filter=0,
            omitted_by_generic_filter=0,
            omitted_by_limit=0,
        )
        highest = (
            "none"
            if details.highest_detected_confidence is None
            else f"{details.highest_detected_confidence:g}"
        )
        statuses = ", ".join(options.validation_statuses) or "none"
        lines = [
            "// Generated by ReliFinder. Inferred logical relationships; not declared constraints.",
            f"// Minimum confidence: {options.min_confidence:g}",
            f"// Validation statuses: {statuses}",
            f"// Scope: {options.scope}",
            f"// Input relationships: {details.input_relationships}",
            f"// Duplicate relationships omitted: {details.duplicate_relationships_omitted}",
            f"// Highest detected confidence: {highest}",
            f"// Below confidence threshold: {details.below_confidence_threshold}",
            f"// Validation-status filter omitted: {details.omitted_by_validation_filter}",
            f"// Scope filter omitted: {details.omitted_by_scope_filter}",
            f"// Generic filter omitted: {details.omitted_by_generic_filter}",
            f"// Max-relations limit omitted: {details.omitted_by_limit}",
            f"// Eligible after filters/limit: {len(model.relationships)}",
            f"// Rendered DBML references: {rendered}",
            f"// Unknown cardinality omitted: {unknown}",
            "",
            "Project ReliFinder_ERD {",
            f"  database_type: '{_dbml_string(_database_label(model.database_type))}'",
            "  Note: 'Read-only inference output. Review before operational use.'",
            "}",
            "",
        ]
        for table in sorted(model.tables, key=lambda item: item.key):
            lines.append(f"Table {_qualified(table.schema, table.name)} {{")
            if external_to_schema and table.schema != external_to_schema:
                note = _dbml_string(f"External table referenced by {external_to_schema}")
                lines.append(f"  Note: '{note}'")
            for column in sorted(table.columns, key=lambda item: (item.position, item.name)):
                attrs = []
                if column.pk_constraints and not column.composite_constraints:
                    attrs.append("pk")
                elif column.unique_constraints and not column.composite_constraints:
                    attrs.append("unique")
                if not column.nullable:
                    attrs.append("not null")
                suffix = f" [{', '.join(attrs)}]" if attrs else ""
                lines.append(f"  {dbml_identifier(column.name)} {native_type(column)}{suffix}")
            lines.extend(_constraint_lines(table))
            lines.extend(["}", ""])

        for relationship in model.relationships:
            match = "n/a" if relationship.match_ratio is None else f"{relationship.match_ratio:.2%}"
            lines.extend(
                [
                    "// ReliFinder evidence:",
                    "// Relationship type: inferred logical",
                    (
                        f"// Confidence: {relationship.confidence_score:g} "
                        f"({relationship.confidence_label})"
                    ),
                    f"// Sample match: {match}",
                    f"// Cardinality: {relationship.cardinality}",
                    (f"// Validation status: {relationship.validation_status or 'unknown'}"),
                ]
            )
            operator = cardinality_operator(relationship.cardinality)
            if operator:
                source = _qualified(
                    relationship.source_schema,
                    relationship.source_table,
                    relationship.source_column,
                )
                target = _qualified(
                    relationship.target_schema,
                    relationship.target_table,
                    relationship.target_column,
                )
                normalized = re.sub(r"[^A-Z0-9]+", "_", relationship.cardinality.upper()).strip("_")
                # DBML treats the second endpoint of one-to-one as the FK column.
                left, right = (target, source) if normalized == "ONE_TO_ONE" else (source, target)
                lines.append(f"Ref: {left} {operator} {right}")
            else:
                lines.append(
                    "// Ref omitted: DBML has no neutral operator for unknown cardinality."
                )
            lines.append("")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "\n".join(lines).rstrip() + "\n",
            encoding="utf-8",
        )
        return unknown
