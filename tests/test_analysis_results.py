import json
from pathlib import Path

import pytest

from oracle_relationship_discovery.output.analysis_results import (
    PRIVACY_NOTICE,
    read_analysis_results,
    write_analysis_results,
)
from oracle_relationship_discovery.output.erd_models import ErdRelationship


def aggregate_relationship(score: float = 68) -> ErdRelationship:
    return ErdRelationship(
        source_schema="APP",
        source_table="REQUEST",
        source_column="PARTY_ID",
        target_schema="CORE",
        target_table="PARTY",
        target_column="ID",
        cardinality="Many-to-One",
        confidence_score=score,
        confidence_label="MEDIUM",
        match_ratio=0.975,
        validation_status="VALIDATED",
        source_datatype="NUMBER",
        target_datatype="NUMBER",
        target_key_type="PRIMARY_KEY",
        cardinality_confidence=0.91,
        cardinality_explanation="Target is unique.",
        name_score=31,
        datatype_score=15,
        key_score=15,
        data_overlap_score=20,
        consistency_score=4,
        structure_score=5,
        sample_size=200,
        matched_values=195,
        unmatched_values=5,
        source_uniqueness_ratio=0.4,
        target_uniqueness_ratio=1.0,
        target_sample_size=100,
        source_null_ratio=0.02,
        sampling_used=True,
        explanation="Aggregate evidence only.",
    )


def test_analysis_results_round_trip_is_versioned_and_deterministic(tmp_path: Path):
    path = tmp_path / "analysis-results.json"
    low = aggregate_relationship(68)
    high = aggregate_relationship(95)

    write_analysis_results(path, (low, high), "sampled", "2026-08-31T10:00:00+03:30")
    first = path.read_bytes()
    restored = read_analysis_results(path)
    write_analysis_results(path, (high, low), "sampled", "2026-08-31T10:00:00+03:30")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.read_bytes() == first
    assert payload["format_version"] == 1
    assert payload["privacy"] == PRIVACY_NOTICE
    assert [item.confidence_score for item in restored] == [95, 68]
    assert restored[0].sample_size == 200
    assert restored[0].source_null_ratio == pytest.approx(0.02)
    assert restored[0].cardinality_explanation == "Target is unique."
    assert restored[0].target_key_type == "PRIMARY_KEY"
    assert restored[0].data_overlap_score == 20


def test_analysis_results_never_persists_sample_values(tmp_path: Path):
    path = tmp_path / "analysis-results.json"
    relationship = aggregate_relationship()

    write_analysis_results(path, (relationship,), "sampled", "now")

    text = path.read_text(encoding="utf-8")
    assert "actual_values" not in text
    assert "sample_values" not in text
    assert "raw_rows" not in text
    assert "SECRET-SAMPLED-VALUE" not in text
    assert '"matched_values": 195' in text


def test_analysis_results_rejects_unsupported_version(tmp_path: Path):
    path = tmp_path / "analysis-results.json"
    path.write_text('{"format_version": 99, "relationships": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported analysis results format_version"):
        read_analysis_results(path)


def test_analysis_results_rejects_corrupt_json(tmp_path: Path):
    path = tmp_path / "analysis-results.json"
    path.write_text('{"format_version": 1,', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid analysis results JSON"):
        read_analysis_results(path)


def test_analysis_results_rejects_unknown_validation_status(tmp_path: Path):
    path = tmp_path / "analysis-results.json"
    write_analysis_results(path, (aggregate_relationship(),), "sampled", "now")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["relationships"][0]["validation_status"] = "BROKEN"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown validation_status"):
        read_analysis_results(path)
