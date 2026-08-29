from oracle_relationship_discovery.analysis.scorer import (
    confidence_label,
    final_breakdown,
    preliminary_breakdown,
    sample_reliability,
)
from oracle_relationship_discovery.config import DEFAULT_WEIGHTS
from oracle_relationship_discovery.models import (
    ColumnMetadata,
    KeyType,
    RelationshipCandidate,
    ValidationEvidence,
    ValidationStatus,
)


def test_confidence_labels_boundaries():
    assert confidence_label(90) == "HIGH"
    assert confidence_label(75) == "MEDIUM-HIGH"
    assert confidence_label(60) == "MEDIUM"
    assert confidence_label(40) == "LOW"
    assert confidence_label(39.99) == "VERY LOW"


def test_score_is_transparent_and_bounded():
    score = preliminary_breakdown(1, 1, KeyType.PRIMARY, DEFAULT_WEIGHTS, 1)
    assert score.total == 70  # overlap and validation consistency are intentionally absent
    assert sum(score.as_dict().values()) == score.total


def test_zero_overlap_downweights_metadata_claims():
    source = ColumnMetadata("S", "REQUEST", "PARTY_ID", "NUMBER")
    target = ColumnMetadata("S", "PARTY", "ID", "NUMBER", pk_constraints=("PK",))
    candidate = RelationshipCandidate(
        source, target, preliminary_breakdown(1, 1, KeyType.PRIMARY, DEFAULT_WEIGHTS, 1)
    )
    candidate.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED, sample_size=100, match_ratio=0
    )
    assert final_breakdown(candidate, DEFAULT_WEIGHTS).total < 40


def test_small_sample_does_not_receive_full_overlap_weight():
    source = ColumnMetadata("S", "REQUEST", "PARTY_ID", "NUMBER")
    target = ColumnMetadata("S", "PARTY", "ID", "NUMBER", pk_constraints=("PK",))
    preliminary = preliminary_breakdown(1, 1, KeyType.PRIMARY, DEFAULT_WEIGHTS, 1)
    small = RelationshipCandidate(source, target, preliminary)
    small.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED, sample_size=4, match_ratio=1
    )
    large = RelationshipCandidate(source, target, preliminary)
    large.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED, sample_size=100, match_ratio=1
    )
    assert final_breakdown(small, DEFAULT_WEIGHTS).total < 90
    assert final_breakdown(large, DEFAULT_WEIGHTS).total == 100
    assert sample_reliability(4) == 0.2


def test_repeating_non_key_target_cannot_become_medium_high_from_overlap():
    source = ColumnMetadata("S", "EVENT", "USER_ID", "NUMBER")
    target = ColumnMetadata("S", "AUDIT", "USER_ID", "NUMBER")
    candidate = RelationshipCandidate(
        source, target, preliminary_breakdown(0.86, 1, KeyType.NONE, DEFAULT_WEIGHTS, 1)
    )
    candidate.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED,
        sample_size=100,
        match_ratio=1,
        target_uniqueness_ratio=0.2,
        target_sample_size=100,
    )
    assert final_breakdown(candidate, DEFAULT_WEIGHTS).total < 60


def test_large_unique_like_target_can_receive_key_and_overlap_evidence():
    source = ColumnMetadata("S", "CUSTOMER_ARCHIVE", "NATIONAL_CODE", "VARCHAR2")
    target = ColumnMetadata("S", "CUSTOMER", "NATIONAL_CODE", "VARCHAR2")
    candidate = RelationshipCandidate(
        source, target, preliminary_breakdown(0.86, 1, KeyType.NONE, DEFAULT_WEIGHTS, 1)
    )
    candidate.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED,
        sample_size=100,
        match_ratio=1,
        target_uniqueness_ratio=1,
        target_sample_size=100,
    )
    assert final_breakdown(candidate, DEFAULT_WEIGHTS).total >= 90
