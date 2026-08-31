"""Format-independent ERD filtering, scoping, and export orchestration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from oracle_relationship_discovery.analysis.name_similarity import (
    semantic_root,
    table_semantic_root,
)
from oracle_relationship_discovery.models import ValidationStatus
from oracle_relationship_discovery.output.dbml_exporter import (
    DbmlExporter,
)
from oracle_relationship_discovery.output.erd_models import (
    ErdExportOptions,
    ErdExportResult,
    ErdModel,
    ErdRelationship,
)

LOGGER = logging.getLogger(__name__)
_VALID_SCOPES = {"full", "schema", "cross-schema"}
_VALID_STATUSES = {status.value for status in ValidationStatus}


@dataclass(frozen=True, slots=True)
class _Selection:
    model: ErdModel
    input_relationships: int
    duplicate_relationships_omitted: int
    confidence_qualified: int
    validation_qualified: int
    eligible: int
    omitted_by_validation: int
    omitted_by_limit: int
    isolated_tables_included: int


def _generic(relationship: ErdRelationship, entities: set[str]) -> bool:
    values = {
        semantic_root(relationship.source_column).replace("_", ""),
        semantic_root(relationship.target_column).replace("_", ""),
        table_semantic_root(relationship.source_table).replace("_", ""),
        table_semantic_root(relationship.target_table).replace("_", ""),
    }
    normalized_entities = {item.replace("_", "") for item in entities}
    return bool(values & normalized_entities)


def _relationship_sort_key(relationship: ErdRelationship) -> tuple[object, ...]:
    return (
        -relationship.confidence_score,
        relationship.source_schema,
        relationship.source_table,
        relationship.target_schema,
        relationship.target_table,
        relationship.source_column,
        relationship.target_column,
        relationship.validation_status,
        relationship.cardinality,
    )


def _deduplicate(
    relationships: tuple[ErdRelationship, ...],
) -> tuple[tuple[ErdRelationship, ...], int]:
    status_rank = {
        "VALIDATED": 0,
        "NOT_RUN": 1,
        "SKIPPED": 2,
        "FAILED": 3,
    }

    def preference(item: ErdRelationship) -> tuple[object, ...]:
        return (
            item.key,
            status_rank.get(item.validation_status, 4),
            -item.confidence_score,
            item.cardinality,
            item.explanation,
        )

    selected: dict[tuple[str, str, str, str, str, str], ErdRelationship] = {}
    for relationship in sorted(relationships, key=preference):
        selected.setdefault(relationship.key, relationship)
    result = tuple(sorted(selected.values(), key=_relationship_sort_key))
    return result, len(relationships) - len(result)


def _select(
    model: ErdModel,
    options: ErdExportOptions,
    schema: str | None = None,
) -> _Selection:
    relationships, duplicate_count = _deduplicate(model.relationships)
    confidence = tuple(
        item for item in relationships if item.confidence_score >= options.min_confidence
    )
    allowed_statuses = set(options.validation_statuses)
    validation = tuple(item for item in confidence if item.validation_status in allowed_statuses)

    scoped = validation
    if options.scope == "cross-schema":
        scoped = tuple(item for item in scoped if item.cross_schema)
    if options.schemas:
        allowed_schemas = set(options.schemas)
        scoped = tuple(
            item
            for item in scoped
            if item.source_schema in allowed_schemas or item.target_schema in allowed_schemas
        )
    if schema:
        scoped = tuple(
            item for item in scoped if item.source_schema == schema or item.target_schema == schema
        )
    if options.exclude_generic:
        entities = {item.upper() for item in options.generic_entities}
        scoped = tuple(item for item in scoped if not _generic(item, entities))

    ordered = tuple(sorted(scoped, key=_relationship_sort_key))
    eligible_count = len(ordered)
    omitted_by_limit = 0
    if options.max_relationships is not None:
        omitted_by_limit = max(0, len(ordered) - options.max_relationships)
        ordered = ordered[: options.max_relationships]

    endpoint_tables = {(item.source_schema, item.source_table) for item in ordered} | {
        (item.target_schema, item.target_table) for item in ordered
    }
    included_keys = set(endpoint_tables)
    if options.include_isolated_tables and options.scope != "cross-schema":
        if schema:
            included_keys.update(table.key for table in model.tables if table.schema == schema)
        elif options.schemas:
            allowed_schemas = set(options.schemas)
            included_keys.update(
                table.key for table in model.tables if table.schema in allowed_schemas
            )
        else:
            included_keys.update(table.key for table in model.tables)

    tables = tuple(
        table
        for table in sorted(model.tables, key=lambda item: item.key)
        if table.key in included_keys
    )
    isolated_count = len({table.key for table in tables} - endpoint_tables)
    return _Selection(
        model=ErdModel(tables, ordered),
        input_relationships=len(model.relationships),
        duplicate_relationships_omitted=duplicate_count,
        confidence_qualified=len(confidence),
        validation_qualified=len(validation),
        eligible=eligible_count,
        omitted_by_validation=len(confidence) - len(validation),
        omitted_by_limit=omitted_by_limit,
        isolated_tables_included=isolated_count,
    )


def _validate_options(model: ErdModel, options: ErdExportOptions) -> None:
    if options.format != "dbml":
        raise ValueError(f"Unsupported ERD format: {options.format}")
    if options.scope not in _VALID_SCOPES:
        raise ValueError(f"Unsupported ERD scope: {options.scope}")
    if not 0 <= options.min_confidence <= 100:
        raise ValueError("ERD minimum confidence must be between 0 and 100")
    if options.max_relationships is not None and options.max_relationships <= 0:
        raise ValueError("ERD maximum relationships must be greater than zero")
    unknown_statuses = sorted(set(options.validation_statuses) - _VALID_STATUSES)
    if unknown_statuses:
        raise ValueError(f"Unknown ERD validation status: {', '.join(unknown_statuses)}")
    available_schemas = {table.schema for table in model.tables}
    missing_schemas = sorted(set(options.schemas) - available_schemas)
    if missing_schemas:
        raise ValueError("ERD schema not present in metadata: " + ", ".join(missing_schemas))


def export_erd(
    model: ErdModel,
    destination_root: Path,
    options: ErdExportOptions,
) -> list[ErdExportResult]:
    _validate_options(model, options)
    exporter = DbmlExporter()
    jobs: list[tuple[str | None, Path]] = []
    if options.scope == "schema":
        schemas = options.schemas or tuple(sorted({table.schema for table in model.tables}))
        for schema in schemas:
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", schema)
            jobs.append((schema, destination_root / "schemas" / f"{safe}.dbml"))
    else:
        name = "cross-schema.dbml" if options.scope == "cross-schema" else "full.dbml"
        jobs.append((None, destination_root / name))

    results = []
    for schema, path in jobs:
        selection = _select(model, options, schema)
        unknown_count = exporter.export(
            selection.model,
            path,
            options,
            external_to_schema=schema,
        )
        rendered_count = len(selection.model.relationships) - unknown_count
        result = ErdExportResult(
            path=path,
            format=options.format,
            scope=options.scope,
            min_confidence=options.min_confidence,
            validation_statuses=options.validation_statuses,
            input_relationships=selection.input_relationships,
            duplicate_relationships_omitted=selection.duplicate_relationships_omitted,
            confidence_qualified_relationships=selection.confidence_qualified,
            validation_qualified_relationships=selection.validation_qualified,
            eligible_relationships=selection.eligible,
            omitted_by_validation_filter=selection.omitted_by_validation,
            omitted_by_limit=selection.omitted_by_limit,
            unknown_cardinality_relationships=unknown_count,
            rendered_relationships=rendered_count,
            included_tables=len(selection.model.tables),
            isolated_tables_included=selection.isolated_tables_included,
        )
        LOGGER.info(
            "ERD export %s: source=%d, duplicates=%d, confidence=%d, validation=%d, "
            "eligible=%d, limit_omitted=%d, unknown_omitted=%d, "
            "rendered_refs=%d, tables=%d, isolated=%d",
            path,
            result.input_relationships,
            result.duplicate_relationships_omitted,
            result.confidence_qualified_relationships,
            result.validation_qualified_relationships,
            result.eligible_relationships,
            result.omitted_by_limit,
            result.unknown_cardinality_relationships,
            result.rendered_relationships,
            result.included_tables,
            result.isolated_tables_included,
        )
        results.append(result)
    return results
