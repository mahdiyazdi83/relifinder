"""Adapters from ReliFinder results and artifacts to visualization models."""

import csv
from pathlib import Path

from oracle_relationship_discovery.analysis.scorer import confidence_label
from oracle_relationship_discovery.models import RelationshipCandidate, TableMetadata
from oracle_relationship_discovery.output.erd_models import (
    ErdColumn,
    ErdModel,
    ErdRelationship,
    ErdTable,
)
from oracle_relationship_discovery.output.schema_metadata import read_schema_metadata


def _tables(tables: list[TableMetadata]) -> tuple[ErdTable, ...]:
    return tuple(
        ErdTable(
            t.schema,
            t.name,
            tuple(
                ErdColumn(
                    c.name,
                    c.data_type,
                    c.data_length,
                    c.precision,
                    c.scale,
                    c.nullable,
                    c.position,
                    c.pk_constraints,
                    c.unique_constraints,
                    c.composite_constraints,
                )
                for c in sorted(t.columns, key=lambda item: item.position)
            ),
        )
        for t in sorted(tables, key=lambda item: (item.schema, item.name))
    )


def build_erd_model(
    tables: list[TableMetadata], candidates: list[RelationshipCandidate]
) -> ErdModel:
    relationships = tuple(
        ErdRelationship(
            item.source.schema,
            item.source.table,
            item.source.name,
            item.target.schema,
            item.target.table,
            item.target.name,
            item.cardinality,
            item.score,
            confidence_label(item.score),
            item.evidence.match_ratio,
            item.evidence.status.value,
        )
        for item in candidates
    )
    return ErdModel(_tables(tables), relationships)


def load_erd_model(csv_path: Path, metadata_path: Path | None = None) -> ErdModel:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    relationships = tuple(
        ErdRelationship(
            r["source_schema"],
            r["source_table"],
            r["source_column"],
            r["target_schema"],
            r["target_table"],
            r["target_column"],
            r.get("cardinality", "Unknown / Insufficient Evidence"),
            float(r["confidence_score"]),
            r.get("confidence_label", ""),
            float(r["match_ratio"]) / 100 if r.get("match_ratio") else None,
            r.get("validation_status", ""),
        )
        for r in rows
    )
    if metadata_path and metadata_path.exists():
        tables = _tables(read_schema_metadata(metadata_path))
    else:
        found: dict[tuple[str, str], dict[str, ErdColumn]] = {}
        for r in rows:
            for side in ("source", "target"):
                key = (r[f"{side}_schema"], r[f"{side}_table"])
                found.setdefault(key, {})[r[f"{side}_column"]] = ErdColumn(
                    r[f"{side}_column"], r.get(f"{side}_datatype", "UNKNOWN")
                )
        tables = tuple(
            ErdTable(s, t, tuple(sorted(cols.values(), key=lambda c: c.name)))
            for (s, t), cols in sorted(found.items())
        )
    return ErdModel(tables, relationships)
