from oracle_relationship_discovery.analysis.relationship_validator import validate_candidates
from oracle_relationship_discovery.config import (
    AppConfig,
    DatabaseConfig,
    PerformanceConfig,
    SamplingConfig,
)
from oracle_relationship_discovery.models import (
    ColumnMetadata,
    RelationshipCandidate,
    ScoreBreakdown,
    ValidationStatus,
)


def test_metadata_only_does_not_claim_candidates_were_skipped_by_limit():
    source = ColumnMetadata("S", "CHILD", "PARENT_ID", "NUMBER")
    target = ColumnMetadata("S", "PARENT", "ID", "NUMBER", pk_constraints=("PK",))
    candidates = [RelationshipCandidate(source, target, ScoreBreakdown(name=40)) for _ in range(3)]
    config = AppConfig(
        database=DatabaseConfig("localhost", 1521, "svc", "user", "PASSWORD_ENV"),
        schemas=("S",),
        sampling=SamplingConfig(enabled=False),
        performance=PerformanceConfig(candidate_validation_limit=1),
    )

    result, skipped_by_limit = validate_candidates(candidates, lambda: None, config)

    assert skipped_by_limit == 0
    assert all(item.evidence.status == ValidationStatus.SKIPPED for item in result)
    assert all("disabled" in item.evidence.message for item in result)
