"""Transparent relationship confidence scoring."""

from __future__ import annotations

import math

from oracle_relationship_discovery.models import (
    KeyType,
    RelationshipCandidate,
    ScoreBreakdown,
    ValidationStatus,
)


def confidence_label(score: float) -> str:
    if score >= 90:
        return "HIGH"
    if score >= 75:
        return "MEDIUM-HIGH"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "LOW"
    return "VERY LOW"


def preliminary_breakdown(
    name_ratio: float,
    datatype_ratio: float,
    target_key: KeyType,
    weights: dict[str, float],
    structure_ratio: float = 0,
) -> ScoreBreakdown:
    if target_key == KeyType.PRIMARY:
        key_ratio = 1.0
    elif target_key == KeyType.UNIQUE:
        key_ratio = 0.87
    elif target_key == KeyType.COMPOSITE_COMPONENT:
        key_ratio = 0.0
    else:
        key_ratio = 0.15
    return ScoreBreakdown(
        name=round(weights["name"] * name_ratio, 2),
        datatype=round(weights["datatype"] * datatype_ratio, 2),
        target_key=round(weights["target_key"] * key_ratio, 2),
        structure=round(weights["structure"] * structure_ratio, 2),
    )


def sample_reliability(sample_size: int) -> float:
    """Return 0..1 evidence reliability; 100 sampled rows earns full sampling weight."""
    if sample_size <= 0:
        return 0.0
    return min(1.0, math.sqrt(sample_size / 100))


def target_is_unique_like(candidate: RelationshipCandidate) -> bool:
    evidence = candidate.evidence
    return bool(
        candidate.target.is_single_column_key
        or (
            evidence.target_uniqueness_ratio is not None
            and evidence.target_uniqueness_ratio >= 0.99
            and evidence.target_sample_size >= 100
        )
    )


def final_breakdown(candidate: RelationshipCandidate, weights: dict[str, float]) -> ScoreBreakdown:
    preliminary = candidate.preliminary
    evidence = candidate.evidence
    overlap = 0.0
    consistency = 0.0
    target_key = preliminary.target_key
    corroboration = 1.0
    if evidence.status == ValidationStatus.VALIDATED and evidence.match_ratio is not None:
        reliability = sample_reliability(evidence.sample_size)
        unique_like = target_is_unique_like(candidate)
        # Overlap against a repeating, non-key domain is weak relationship evidence.
        non_key_factor = 1.0 if unique_like else 0.15
        # Low-overlap samples should actively prevent a metadata-only false positive.
        overlap = (
            weights["overlap"]
            * max(0.0, min(1.0, evidence.match_ratio))
            * reliability
            * non_key_factor
        )
        corroboration = 0.25 + (0.75 * max(0.0, min(1.0, evidence.match_ratio)))
        consistency = weights["consistency"] * reliability * (1.0 if unique_like else 0.25)
        if not candidate.target.is_single_column_key and unique_like:
            target_key = weights["target_key"] * 0.7
    return ScoreBreakdown(
        name=round(preliminary.name * corroboration, 2),
        datatype=preliminary.datatype,
        target_key=round(target_key * corroboration, 2),
        overlap=round(overlap, 2),
        consistency=round(consistency, 2),
        structure=round(preliminary.structure * corroboration, 2),
    )
