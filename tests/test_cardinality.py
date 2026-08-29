from oracle_relationship_discovery.analysis.cardinality import infer_cardinality
from oracle_relationship_discovery.models import (
    ColumnMetadata,
    RelationshipCandidate,
    ScoreBreakdown,
    ValidationEvidence,
    ValidationStatus,
)


def candidate(source_unique: float, sample_size: int = 100):
    source = ColumnMetadata("S", "CHILD", "PARENT_ID", "NUMBER")
    target = ColumnMetadata("S", "PARENT", "ID", "NUMBER", pk_constraints=("PK",))
    item = RelationshipCandidate(source, target, ScoreBreakdown())
    item.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED,
        sample_size=sample_size,
        source_uniqueness_ratio=source_unique,
    )
    return item


def test_duplicates_imply_many_to_one_probabilistically():
    assert infer_cardinality(candidate(0.4))[0] == "Many-to-One"


def test_unique_source_and_target_imply_one_to_one():
    assert infer_cardinality(candidate(1.0))[0] == "One-to-One"


def test_tiny_sample_is_unknown():
    assert infer_cardinality(candidate(1.0, 1))[0].startswith("Unknown")


def test_unique_source_under_thirty_rows_remains_unknown():
    assert infer_cardinality(candidate(1.0, 29))[0].startswith("Unknown")


def test_observed_duplicates_can_support_many_to_one_in_small_sample():
    assert infer_cardinality(candidate(0.5, 4))[0] == "Many-to-One"
