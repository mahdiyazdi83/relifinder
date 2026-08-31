"""Adapters from ReliFinder results and artifacts to visualization models."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from oracle_relationship_discovery.analysis.scorer import confidence_label
from oracle_relationship_discovery.models import RelationshipCandidate, TableMetadata
from oracle_relationship_discovery.output.analysis_results import read_analysis_results
from oracle_relationship_discovery.output.erd_models import (
    ErdColumn,
    ErdModel,
    ErdRelationship,
    ErdTable,
)
from oracle_relationship_discovery.output.schema_metadata import read_schema_metadata

_LEGACY_REQUIRED_FIELDS = {
    "source_schema",
    "source_table",
    "source_column",
    "target_schema",
    "target_table",
    "target_column",
    "confidence_score",
}


@dataclass(frozen=True, slots=True)
class OfflineAnalysisSource:
    path: Path
    legacy_csv: bool


def _tables(tables: list[TableMetadata]) -> tuple[ErdTable, ...]:
    return tuple(
        ErdTable(
            table.schema,
            table.name,
            tuple(
                ErdColumn(
                    column.name,
                    column.data_type,
                    column.data_length,
                    column.precision,
                    column.scale,
                    column.nullable,
                    column.position,
                    tuple(sorted(column.pk_constraints)),
                    tuple(sorted(column.unique_constraints)),
                    tuple(sorted(column.composite_constraints)),
                )
                for column in sorted(table.columns, key=lambda item: (item.position, item.name))
            ),
        )
        for table in sorted(tables, key=lambda item: (item.schema, item.name))
    )


def build_erd_model(
    tables: list[TableMetadata], candidates: list[RelationshipCandidate]
) -> ErdModel:
    relationships = []
    for item in candidates:
        score = item.final_score or item.preliminary
        evidence = item.evidence
        relationships.append(
            ErdRelationship(
                source_schema=item.source.schema,
                source_table=item.source.table,
                source_column=item.source.name,
                target_schema=item.target.schema,
                target_table=item.target.table,
                target_column=item.target.name,
                cardinality=item.cardinality,
                confidence_score=item.score,
                confidence_label=confidence_label(item.score),
                match_ratio=evidence.match_ratio,
                validation_status=evidence.status.value,
                source_datatype=item.source.data_type,
                target_datatype=item.target.data_type,
                cardinality_confidence=item.cardinality_confidence,
                cardinality_explanation=item.cardinality_explanation,
                name_score=score.name,
                datatype_score=score.datatype,
                key_score=score.target_key,
                data_overlap_score=score.overlap,
                consistency_score=score.consistency,
                structure_score=score.structure,
                sample_size=evidence.sample_size,
                matched_values=evidence.matched_values,
                unmatched_values=evidence.unmatched_values,
                source_uniqueness_ratio=evidence.source_uniqueness_ratio,
                target_uniqueness_ratio=evidence.target_uniqueness_ratio,
                target_sample_size=evidence.target_sample_size,
                source_null_ratio=evidence.source_null_ratio,
                sampling_used=evidence.sampling_used,
                explanation=item.explanation(),
            )
        )
    relationships.sort(key=_relationship_sort_key)
    return ErdModel(_tables(tables), tuple(relationships))


def resolve_offline_source(input_path: Path) -> OfflineAnalysisSource:
    input_path = input_path.resolve()
    if input_path.is_dir():
        richer = input_path / "analysis-results.json"
        legacy = input_path / "relationships.csv"
    else:
        richer = (
            input_path
            if input_path.name == "analysis-results.json"
            else (input_path.with_name("analysis-results.json"))
        )
        legacy = (
            input_path
            if input_path.suffix.lower() == ".csv"
            else (input_path.with_name("relationships.csv"))
        )
    if richer.is_file():
        return OfflineAnalysisSource(richer, False)
    if legacy.is_file():
        return OfflineAnalysisSource(legacy, True)
    raise ValueError(
        "No offline analysis input found. Expected analysis-results.json or relationships.csv "
        f"at: {input_path}"
    )


def load_erd_model(source_path: Path, metadata_path: Path | None = None) -> ErdModel:
    if source_path.name == "analysis-results.json":
        relationships = read_analysis_results(source_path)
    elif source_path.suffix.lower() == ".csv":
        relationships = _read_legacy_csv(source_path)
    else:
        raise ValueError(
            "Unsupported offline input. Use analysis-results.json, relationships.csv, "
            "or a ReliFinder run directory"
        )

    tables = _tables(read_schema_metadata(metadata_path)) if metadata_path else ()
    if not tables:
        tables = _minimal_tables(relationships)
    else:
        tables = _merge_missing_endpoints(tables, relationships)
    return ErdModel(tables, relationships)


def _read_legacy_csv(path: Path) -> tuple[ErdRelationship, ...]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = sorted(_LEGACY_REQUIRED_FIELDS - fields)
            if missing:
                raise ValueError(
                    f"Legacy relationships CSV is missing columns: {', '.join(missing)}"
                )
            rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"Malformed legacy relationships CSV: {path}") from exc

    relationships = []
    for index, row in enumerate(rows):
        try:
            score = float(row["confidence_score"])
            relationships.append(
                ErdRelationship(
                    source_schema=row["source_schema"],
                    source_table=row["source_table"],
                    source_column=row["source_column"],
                    target_schema=row["target_schema"],
                    target_table=row["target_table"],
                    target_column=row["target_column"],
                    cardinality=row.get("cardinality") or "Unknown / Insufficient Evidence",
                    confidence_score=score,
                    confidence_label=row.get("confidence_label") or confidence_label(score),
                    match_ratio=_csv_ratio(row.get("match_ratio")),
                    validation_status=row.get("validation_status") or "NOT_RUN",
                    source_datatype=row.get("source_datatype") or "UNKNOWN",
                    target_datatype=row.get("target_datatype") or "UNKNOWN",
                    cardinality_confidence=_csv_ratio(row.get("cardinality_confidence")) or 0,
                    name_score=_csv_float(row.get("name_score")),
                    datatype_score=_csv_float(row.get("datatype_score")),
                    key_score=_csv_float(row.get("key_score")),
                    data_overlap_score=_csv_float(row.get("data_overlap_score")),
                    consistency_score=_csv_float(row.get("consistency_score")),
                    structure_score=_csv_float(row.get("structure_score")),
                    sample_size=int(row.get("sample_size") or 0),
                    matched_values=int(row.get("matched_samples") or 0),
                    unmatched_values=int(row.get("unmatched_samples") or 0),
                    source_uniqueness_ratio=_csv_ratio(row.get("source_uniqueness_ratio")),
                    target_uniqueness_ratio=_csv_ratio(row.get("target_uniqueness_ratio")),
                    target_sample_size=int(row.get("target_sample_size") or 0),
                    sampling_used=str(row.get("sampling_used", "")).lower() in {"1", "true", "yes"},
                    explanation=row.get("explanation") or "",
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Legacy relationships CSV row {index + 2} contains an invalid value"
            ) from exc
    return tuple(sorted(relationships, key=_relationship_sort_key))


def _minimal_tables(
    relationships: tuple[ErdRelationship, ...],
) -> tuple[ErdTable, ...]:
    found: dict[tuple[str, str], dict[str, ErdColumn]] = {}
    for relationship in relationships:
        for schema, table, column, datatype in (
            (
                relationship.source_schema,
                relationship.source_table,
                relationship.source_column,
                relationship.source_datatype,
            ),
            (
                relationship.target_schema,
                relationship.target_table,
                relationship.target_column,
                relationship.target_datatype,
            ),
        ):
            found.setdefault((schema, table), {})[column] = ErdColumn(column, datatype or "UNKNOWN")
    return tuple(
        ErdTable(schema, table, tuple(sorted(columns.values(), key=lambda item: item.name)))
        for (schema, table), columns in sorted(found.items())
    )


def _merge_missing_endpoints(
    tables: tuple[ErdTable, ...],
    relationships: tuple[ErdRelationship, ...],
) -> tuple[ErdTable, ...]:
    existing = {table.key: table for table in tables}
    minimal = {table.key: table for table in _minimal_tables(relationships)}
    for key, table in minimal.items():
        if key not in existing:
            existing[key] = table
    return tuple(existing[key] for key in sorted(existing))


def _relationship_sort_key(item: ErdRelationship) -> tuple[object, ...]:
    return (
        item.source_schema,
        item.source_table,
        item.source_column,
        item.target_schema,
        item.target_table,
        item.target_column,
        -item.confidence_score,
    )


def _csv_float(value: str | None) -> float:
    return float(value) if value else 0


def _csv_ratio(value: str | None) -> float | None:
    return float(value) / 100 if value else None
