"""Sample-aware cardinality inference."""

from oracle_relationship_discovery.analysis.scorer import sample_reliability, target_is_unique_like
from oracle_relationship_discovery.models import RelationshipCandidate, ValidationStatus


def infer_cardinality(candidate: RelationshipCandidate) -> tuple[str, float, str]:
    evidence = candidate.evidence
    target_unique = target_is_unique_like(candidate)
    if not target_unique:
        return (
            "Unknown / Insufficient Evidence",
            0.2,
            "The target is not a single-column declared key and sampled uniqueness is insufficient.",
        )
    if evidence.status != ValidationStatus.VALIDATED or evidence.source_uniqueness_ratio is None:
        return (
            "Unknown / Insufficient Evidence",
            0.35,
            "The target is unique, but source duplication was not sampled.",
        )
    if evidence.sample_size < 2:
        return (
            "Unknown / Insufficient Evidence",
            0.2,
            "Too few source values were available to infer cardinality.",
        )
    if evidence.source_uniqueness_ratio >= 0.99 and evidence.sample_size < 30:
        return (
            "Unknown / Insufficient Evidence",
            0.25 + 0.25 * sample_reliability(evidence.sample_size),
            "The source sample appears unique, but fewer than 30 values cannot support a One-to-One inference.",
        )
    if evidence.source_uniqueness_ratio >= 0.99:
        return (
            "One-to-One",
            min(0.85, 0.45 + 0.4 * sample_reliability(evidence.sample_size)),
            "Both target key metadata and the bounded source sample appear unique; this is probabilistic.",
        )
    return (
        "Many-to-One",
        min(0.9, 0.5 + 0.4 * sample_reliability(evidence.sample_size)),
        "The target is unique and repeated values were observed in the bounded source sample.",
    )
