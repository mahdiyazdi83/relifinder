"""Orchestrate bounded validation and scoring while isolating candidate failures."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from oracle_relationship_discovery.analysis.cardinality import infer_cardinality
from oracle_relationship_discovery.analysis.scorer import (
    final_breakdown,
    sample_reliability,
    target_is_unique_like,
)
from oracle_relationship_discovery.config import AppConfig
from oracle_relationship_discovery.models import RelationshipCandidate, ValidationStatus

LOGGER = logging.getLogger(__name__)


class CandidateSampler(Protocol):
    def validate(self, candidate: RelationshipCandidate) -> None: ...


def _finish(
    candidate: RelationshipCandidate, sampler: CandidateSampler, weights: dict[str, float]
) -> RelationshipCandidate:
    try:
        sampler.validate(candidate)
    except Exception as exc:  # noqa: BLE001 - one bad candidate must not abort the analysis run.
        LOGGER.warning(
            "Validation failed for %s -> %s: %s",
            candidate.source.qualified_name,
            candidate.target.qualified_name,
            type(exc).__name__,
        )
        candidate.evidence.status = ValidationStatus.FAILED
        candidate.evidence.message = f"Sampling failed: {type(exc).__name__}."
    candidate.final_score = final_breakdown(candidate, weights)
    if candidate.evidence.status == ValidationStatus.VALIDATED:
        if sample_reliability(candidate.evidence.sample_size) < 1:
            candidate.reasons.append(
                "Sampling evidence was discounted because fewer than 100 source rows were available."
            )
        if not target_is_unique_like(candidate):
            candidate.reasons.append(
                "Overlap was strongly discounted because the target is neither a declared key nor reliably unique-like."
            )
    (candidate.cardinality, candidate.cardinality_confidence, candidate.cardinality_explanation) = (
        infer_cardinality(candidate)
    )
    return candidate


def validate_candidates(
    candidates: list[RelationshipCandidate], sampler_factory, config: AppConfig
) -> tuple[list[RelationshipCandidate], int]:
    if not config.sampling.enabled:
        for candidate in candidates:
            candidate.evidence.status = ValidationStatus.SKIPPED
            candidate.evidence.message = "Sampling was disabled; score uses metadata evidence only."
            candidate.final_score = candidate.preliminary
        return candidates, 0

    limit = config.performance.candidate_validation_limit
    selected = candidates[:limit]
    skipped = candidates[limit:]
    for candidate in skipped:
        candidate.evidence.status = ValidationStatus.SKIPPED
        candidate.evidence.message = "Skipped because candidate_validation_limit was reached."
        candidate.final_score = candidate.preliminary

    with ThreadPoolExecutor(max_workers=config.performance.max_workers) as executor:
        futures = {
            executor.submit(
                _finish, candidate, sampler_factory(), config.analysis.weights
            ): candidate
            for candidate in selected
        }
        for future in as_completed(futures):
            future.result()
    return sorted(candidates, key=lambda item: -item.score), len(skipped)
