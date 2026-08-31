import csv
from pathlib import Path

from oracle_relationship_discovery.cli import build_parser, main
from oracle_relationship_discovery.config import load_config

FIELDS = [
    "source_schema",
    "source_table",
    "source_column",
    "target_schema",
    "target_table",
    "target_column",
    "source_datatype",
    "target_datatype",
    "cardinality",
    "confidence_score",
    "confidence_label",
    "match_ratio",
    "validation_status",
]


def _write_relationships(path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "source_schema": "APP",
                "source_table": "REQUEST",
                "source_column": "PARTY_ID",
                "target_schema": "CORE",
                "target_table": "PARTY",
                "target_column": "ID",
                "source_datatype": "NUMBER",
                "target_datatype": "NUMBER",
                "cardinality": "Many-to-One",
                "confidence_score": 94,
                "confidence_label": "HIGH",
                "match_ratio": 99.5,
                "validation_status": "VALIDATED",
            }
        )


def test_analyze_parser_accepts_erd_overrides():
    args = build_parser().parse_args(
        [
            "--config",
            "config.yaml",
            "analyze",
            "--erd",
            "--erd-format",
            "dbml",
            "--erd-min-confidence",
            "85",
            "--erd-scope",
            "schema",
            "--erd-schema",
            "APP",
            "--erd-max-relationships",
            "100",
            "--erd-validation-status",
            "VALIDATED",
            "--erd-validation-status",
            "SKIPPED",
            "--erd-include-isolated-tables",
            "--erd-exclude-generic",
        ]
    )

    assert args.erd is True
    assert args.erd_min_confidence == 85
    assert args.erd_scope == "schema"
    assert args.erd_schema == ["APP"]
    assert args.erd_validation_status == ["VALIDATED", "SKIPPED"]
    assert args.erd_include_isolated_tables is True


def test_config_loads_erd_defaults_and_options(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  host: localhost
  service_name: TEST
  username: reader
  password_env: TEST_PASSWORD
schemas: [APP]
erd:
  enabled: true
  format: dbml
  min_confidence: 87
  scope: cross-schema
  schemas: [app]
  max_relationships: 25
  exclude_generic: true
  include_isolated_tables: true
  validation_statuses: [VALIDATED, NOT_RUN]
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.erd.enabled is True
    assert config.erd.min_confidence == 87
    assert config.erd.scope == "cross-schema"
    assert config.erd.schemas == ("APP",)
    assert config.erd.max_relationships == 25
    assert config.erd.exclude_generic is True
    assert config.erd.include_isolated_tables is True
    assert config.erd.validation_statuses == ("VALIDATED", "NOT_RUN")


def test_offline_export_command_needs_no_config_or_oracle(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "relationships.csv"
    destination = tmp_path / "diagram"
    _write_relationships(csv_path)
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "export-erd",
            "--input",
            str(csv_path),
            "--output-dir",
            str(destination),
            "--min-confidence",
            "90",
        ]
    )

    assert result == 0
    text = (destination / "full.dbml").read_text(encoding="utf-8")
    assert "Ref: APP.REQUEST.PARTY_ID > CORE.PARTY.ID" in text
    assert "Minimum confidence: 90" in text
    assert (tmp_path / "logs" / "oracle-relationship-discovery.log").is_file()


def test_offline_cli_rejects_invalid_numeric_options(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "relationships.csv"
    _write_relationships(csv_path)
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "export-erd",
                "--input",
                str(csv_path),
                "--min-confidence",
                "-1",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "export-erd",
                "--input",
                str(csv_path),
                "--max-relationships",
                "0",
            ]
        )
        == 2
    )


def test_offline_cli_rejects_missing_and_corrupt_inputs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["export-erd", "--input", str(tmp_path / "missing")]) == 2

    artifact = tmp_path / "analysis-results.json"
    artifact.write_text("{broken", encoding="utf-8")
    assert main(["export-erd", "--input", str(artifact)]) == 2


def test_parser_rejects_unknown_validation_status():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "export-erd",
                "--input",
                "relationships.csv",
                "--validation-status",
                "BROKEN",
            ]
        )


def test_config_rejects_non_list_validation_statuses(tmp_path: Path):
    import pytest

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  host: localhost
  service_name: TEST
  username: reader
  password_env: TEST_PASSWORD
schemas: [APP]
erd:
  validation_statuses: VALIDATED
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="validation_statuses must be a list"):
        load_config(config_path)
