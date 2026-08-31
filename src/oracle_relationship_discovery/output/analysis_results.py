"""Versioned aggregate analysis artifact for safe offline tooling."""

from __future__ import annotations

import json
from pathlib import Path

from oracle_relationship_discovery.models import ValidationStatus
from oracle_relationship_discovery.output.erd_models import ErdRelationship

FORMAT_VERSION = 1
PRIVACY_NOTICE = "Aggregate analysis evidence only; no sampled values are stored."


class AnalysisResultsError(ValueError):
    """Raised when an offline analysis artifact cannot be interpreted safely."""


_REQUIRED_FIELDS = {
    "source_schema",
    "source_table",
    "source_column",
    "target_schema",
    "target_table",
    "target_column",
    "source_datatype",
    "target_datatype",
    "cardinality",
    "cardinality_confidence",
    "cardinality_explanation",
    "confidence_score",
    "confidence_label",
    "score_breakdown",
    "validation_status",
    "sample_size",
    "matched_values",
    "unmatched_values",
    "match_ratio",
    "source_uniqueness_ratio",
    "target_uniqueness_ratio",
    "source_null_ratio",
    "sampling_used",
    "explanation",
}


def _sort_key(item: ErdRelationship) -> tuple[object, ...]:
    return (
        item.source_schema,
        item.source_table,
        item.source_column,
        item.target_schema,
        item.target_table,
        item.target_column,
        -item.confidence_score,
    )


def _relationship_dict(item: ErdRelationship) -> dict[str, object]:
    return {
        "source_schema": item.source_schema,
        "source_table": item.source_table,
        "source_column": item.source_column,
        "target_schema": item.target_schema,
        "target_table": item.target_table,
        "target_column": item.target_column,
        "source_datatype": item.source_datatype,
        "target_datatype": item.target_datatype,
        "cardinality": item.cardinality,
        "cardinality_confidence": item.cardinality_confidence,
        "cardinality_explanation": item.cardinality_explanation,
        "confidence_score": item.confidence_score,
        "confidence_label": item.confidence_label,
        "score_breakdown": {
            "name": item.name_score,
            "datatype": item.datatype_score,
            "target_key": item.key_score,
            "overlap": item.data_overlap_score,
            "consistency": item.consistency_score,
            "structure": item.structure_score,
        },
        "validation_status": item.validation_status,
        "sample_size": item.sample_size,
        "matched_values": item.matched_values,
        "unmatched_values": item.unmatched_values,
        "match_ratio": item.match_ratio,
        "source_uniqueness_ratio": item.source_uniqueness_ratio,
        "target_uniqueness_ratio": item.target_uniqueness_ratio,
        "target_sample_size": item.target_sample_size,
        "source_null_ratio": item.source_null_ratio,
        "sampling_used": item.sampling_used,
        "explanation": item.explanation,
    }


def write_analysis_results(
    path: Path,
    relationships: tuple[ErdRelationship, ...],
    analysis_mode: str,
    generated_at: str,
) -> None:
    payload = {
        "format_version": FORMAT_VERSION,
        "generated_at": generated_at,
        "analysis_mode": analysis_mode,
        "privacy": PRIVACY_NOTICE,
        "relationships": [
            _relationship_dict(item) for item in sorted(relationships, key=_sort_key)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_analysis_results(path: Path) -> tuple[ErdRelationship, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisResultsError(
            f"Invalid analysis results JSON at line {exc.lineno}, column {exc.colno}: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise AnalysisResultsError("Analysis results artifact must contain a JSON object")
    version = payload.get("format_version")
    if version != FORMAT_VERSION:
        raise AnalysisResultsError(
            f"Unsupported analysis results format_version {version!r}; expected {FORMAT_VERSION}"
        )
    raw_relationships = payload.get("relationships")
    if not isinstance(raw_relationships, list):
        raise AnalysisResultsError("Analysis results artifact field 'relationships' must be a list")

    relationships = []
    for index, raw in enumerate(raw_relationships):
        if not isinstance(raw, dict):
            raise AnalysisResultsError(
                f"Analysis result relationship #{index + 1} must be an object"
            )
        missing = sorted(_REQUIRED_FIELDS - raw.keys())
        if missing:
            raise AnalysisResultsError(
                f"Analysis result relationship #{index + 1} is missing: {', '.join(missing)}"
            )
        scores = raw.get("score_breakdown") or {}
        if not isinstance(scores, dict):
            raise AnalysisResultsError(
                f"Analysis result relationship #{index + 1} has invalid score_breakdown"
            )
        try:
            relationships.append(
                ErdRelationship(
                    source_schema=str(raw["source_schema"]),
                    source_table=str(raw["source_table"]),
                    source_column=str(raw["source_column"]),
                    target_schema=str(raw["target_schema"]),
                    target_table=str(raw["target_table"]),
                    target_column=str(raw["target_column"]),
                    cardinality=str(raw.get("cardinality", "Unknown / Insufficient Evidence")),
                    confidence_score=float(raw["confidence_score"]),
                    confidence_label=str(raw.get("confidence_label", "")),
                    match_ratio=_optional_float(raw.get("match_ratio")),
                    validation_status=_validation_status(raw["validation_status"], index),
                    source_datatype=str(raw.get("source_datatype", "")),
                    target_datatype=str(raw.get("target_datatype", "")),
                    cardinality_confidence=float(raw.get("cardinality_confidence", 0)),
                    cardinality_explanation=str(raw.get("cardinality_explanation", "")),
                    name_score=float(scores.get("name", 0)),
                    datatype_score=float(scores.get("datatype", 0)),
                    key_score=float(scores.get("target_key", 0)),
                    data_overlap_score=float(scores.get("overlap", 0)),
                    consistency_score=float(scores.get("consistency", 0)),
                    structure_score=float(scores.get("structure", 0)),
                    sample_size=int(raw.get("sample_size", 0)),
                    matched_values=int(raw.get("matched_values", 0)),
                    unmatched_values=int(raw.get("unmatched_values", 0)),
                    source_uniqueness_ratio=_optional_float(raw.get("source_uniqueness_ratio")),
                    target_uniqueness_ratio=_optional_float(raw.get("target_uniqueness_ratio")),
                    target_sample_size=int(raw.get("target_sample_size", 0)),
                    source_null_ratio=_optional_float(raw.get("source_null_ratio")),
                    sampling_used=_strict_bool(raw["sampling_used"], "sampling_used", index),
                    explanation=str(raw.get("explanation", "")),
                )
            )
        except AnalysisResultsError:
            raise
        except (TypeError, ValueError) as exc:
            raise AnalysisResultsError(
                f"Analysis result relationship #{index + 1} contains an invalid value"
            ) from exc
    return tuple(sorted(relationships, key=_sort_key))


def _optional_float(value: object) -> float | None:
    return None if value is None or value == "" else float(value)


def _validation_status(value: object, index: int) -> str:
    status = str(value).upper()
    valid = {item.value for item in ValidationStatus}
    if status not in valid:
        raise AnalysisResultsError(
            f"Analysis result relationship #{index + 1} has unknown validation_status {status!r}"
        )
    return status


def _strict_bool(value: object, field: str, index: int) -> bool:
    if not isinstance(value, bool):
        raise AnalysisResultsError(
            f"Analysis result relationship #{index + 1} field {field!r} must be boolean"
        )
    return value
