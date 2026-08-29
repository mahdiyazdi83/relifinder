"""CSV relationship report."""

from __future__ import annotations

import csv
from pathlib import Path

from oracle_relationship_discovery.analysis.scorer import confidence_label
from oracle_relationship_discovery.models import RelationshipCandidate

FIELDS = [
    "analysis_mode",
    "report_generated_at",
    "source_schema",
    "source_table",
    "source_column",
    "target_schema",
    "target_table",
    "target_column",
    "source_datatype",
    "target_datatype",
    "target_key_type",
    "relationship_type",
    "cardinality",
    "cardinality_confidence",
    "confidence_score",
    "confidence_label",
    "name_score",
    "datatype_score",
    "key_score",
    "data_overlap_score",
    "consistency_score",
    "structure_score",
    "sample_size",
    "matched_samples",
    "unmatched_samples",
    "match_ratio",
    "source_uniqueness_ratio",
    "target_uniqueness_ratio",
    "target_sample_size",
    "source_nullable",
    "sampling_used",
    "validation_status",
    "explanation",
]


def candidate_row(
    candidate: RelationshipCandidate, analysis_mode: str = "", generated_at: str = ""
) -> dict[str, object]:
    score = candidate.final_score or candidate.preliminary
    evidence = candidate.evidence
    return {
        "analysis_mode": analysis_mode,
        "report_generated_at": generated_at,
        "source_schema": candidate.source.schema,
        "source_table": candidate.source.table,
        "source_column": candidate.source.name,
        "target_schema": candidate.target.schema,
        "target_table": candidate.target.table,
        "target_column": candidate.target.name,
        "source_datatype": candidate.source.data_type,
        "target_datatype": candidate.target.data_type,
        "target_key_type": candidate.target.key_type.value,
        "relationship_type": "LOGICAL_INFERRED",
        "cardinality": candidate.cardinality,
        "cardinality_confidence": round(candidate.cardinality_confidence * 100, 2),
        "confidence_score": score.total,
        "confidence_label": confidence_label(score.total),
        "name_score": score.name,
        "datatype_score": score.datatype,
        "key_score": score.target_key,
        "data_overlap_score": score.overlap,
        "consistency_score": score.consistency,
        "structure_score": score.structure,
        "sample_size": evidence.sample_size,
        "matched_samples": evidence.matched_values,
        "unmatched_samples": evidence.unmatched_values,
        "match_ratio": round(evidence.match_ratio * 100, 4)
        if evidence.match_ratio is not None
        else "",
        "source_uniqueness_ratio": (
            round(evidence.source_uniqueness_ratio * 100, 4)
            if evidence.source_uniqueness_ratio is not None
            else ""
        ),
        "target_uniqueness_ratio": (
            round(evidence.target_uniqueness_ratio * 100, 4)
            if evidence.target_uniqueness_ratio is not None
            else ""
        ),
        "target_sample_size": evidence.target_sample_size,
        "source_nullable": candidate.source.nullable,
        "sampling_used": evidence.sampling_used,
        "validation_status": evidence.status.value,
        "explanation": candidate.explanation(),
    }


def write_csv(
    path: Path,
    candidates: list[RelationshipCandidate],
    analysis_mode: str = "",
    generated_at: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(
            candidate_row(candidate, analysis_mode, generated_at) for candidate in candidates
        )
