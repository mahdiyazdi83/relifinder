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
            "--erd-exclude-generic",
        ]
    )

    assert args.erd is True
    assert args.erd_min_confidence == 85
    assert args.erd_scope == "schema"
    assert args.erd_schema == ["APP"]


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
