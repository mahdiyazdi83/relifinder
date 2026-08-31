"""Format-independent ERD filtering, scoping, and export orchestration."""

import logging
import re
from pathlib import Path

from oracle_relationship_discovery.analysis.name_similarity import (
    semantic_root,
    table_semantic_root,
)
from oracle_relationship_discovery.output.dbml_exporter import DbmlExporter
from oracle_relationship_discovery.output.erd_models import (
    ErdExportOptions,
    ErdExportResult,
    ErdModel,
)

LOGGER = logging.getLogger(__name__)


def _generic(rel, entities: set[str]) -> bool:
    values = {
        semantic_root(rel.source_column).replace("_", ""),
        semantic_root(rel.target_column).replace("_", ""),
        table_semantic_root(rel.source_table).replace("_", ""),
        table_semantic_root(rel.target_table).replace("_", ""),
    }
    return bool(values & {item.replace("_", "") for item in entities})


def _selected(
    model: ErdModel, options: ErdExportOptions, schema: str | None = None
) -> tuple[ErdModel, int]:
    relationships = [r for r in model.relationships if r.confidence_score >= options.min_confidence]
    if options.scope == "cross-schema":
        relationships = [r for r in relationships if r.cross_schema]
    if options.schemas:
        allowed = set(options.schemas)
        relationships = [
            r for r in relationships if r.source_schema in allowed or r.target_schema in allowed
        ]
    if schema:
        relationships = [
            r for r in relationships if r.source_schema == schema or r.target_schema == schema
        ]
    if options.exclude_generic:
        entities = {item.upper() for item in options.generic_entities}
        relationships = [r for r in relationships if not _generic(r, entities)]
    relationships.sort(
        key=lambda r: (
            -r.confidence_score,
            r.source_schema,
            r.source_table,
            r.target_schema,
            r.target_table,
            r.source_column,
            r.target_column,
        )
    )
    omitted = 0
    if options.max_relationships is not None and len(relationships) > options.max_relationships:
        omitted = len(relationships) - options.max_relationships
        relationships = relationships[: options.max_relationships]
    required = {(r.source_schema, r.source_table) for r in relationships} | {
        (r.target_schema, r.target_table) for r in relationships
    }
    tables = tuple(t for t in model.tables if t.key in required)
    return ErdModel(tables, tuple(relationships)), omitted


def export_erd(
    model: ErdModel, destination_root: Path, options: ErdExportOptions
) -> list[ErdExportResult]:
    if options.format != "dbml":
        raise ValueError(f"Unsupported ERD format: {options.format}")
    if options.scope not in {"full", "schema", "cross-schema"}:
        raise ValueError(f"Unsupported ERD scope: {options.scope}")
    exporter = DbmlExporter()
    jobs = []
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
        scoped, omitted = _selected(model, options, schema)
        unknown = exporter.export(scoped, path, options, external_to_schema=schema)
        if omitted:
            LOGGER.warning("ERD %s omitted %d relationships due to max limit", path, omitted)
        results.append(
            ErdExportResult(
                path,
                options.format,
                options.scope,
                options.min_confidence,
                len(scoped.relationships),
                omitted,
                unknown,
            )
        )
    return results
