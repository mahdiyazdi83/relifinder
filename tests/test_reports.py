import csv
from pathlib import Path

from oracle_relationship_discovery.models import (
    AnalysisStats,
    ColumnMetadata,
    RelationshipCandidate,
    ScoreBreakdown,
    ValidationEvidence,
    ValidationStatus,
)
from oracle_relationship_discovery.output.csv_report import write_csv
from oracle_relationship_discovery.output.html_report import write_html


def example_candidate() -> RelationshipCandidate:
    candidate = RelationshipCandidate(
        ColumnMetadata("APP", "REQUEST", "PARTY_ID", "NUMBER"),
        ColumnMetadata("APP", "PARTY", "ID", "NUMBER", pk_constraints=("PK_PARTY",)),
        ScoreBreakdown(name=35, datatype=15, target_key=15, overlap=25, consistency=5),
        reasons=["semantic match"],
    )
    candidate.evidence = ValidationEvidence(
        status=ValidationStatus.VALIDATED,
        sample_size=10,
        matched_values=9,
        unmatched_values=1,
        match_ratio=0.9,
        sampling_used=True,
    )
    return candidate


def test_reports_are_self_contained_and_aggregate_only(tmp_path: Path):
    candidate = example_candidate()
    csv_path = tmp_path / "relationships.csv"
    html_path = tmp_path / "relationship-report.html"
    stats = AnalysisStats(1, 2, 2, 1, 1)

    generated_at = "2026-08-29T10:20:30.123456+03:30"
    write_csv(csv_path, [candidate], "sampled", generated_at)
    write_html(html_path, [candidate], stats, "sampled", generated_at)

    with csv_path.open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    assert row["sample_size"] == "10"
    assert row["matched_samples"] == "9"
    assert row["analysis_mode"] == "sampled"
    assert row["report_generated_at"] == generated_at
    html = html_path.read_text(encoding="utf-8")
    assert "https://" not in html
    assert "Relationship Discovery" in html
    assert 'id="theme"' in html
    assert 'data-theme="light"' in html
