import csv
from pathlib import Path

import pytest

from oracle_relationship_discovery.models import ColumnMetadata, TableMetadata
from oracle_relationship_discovery.output.analysis_results import write_analysis_results
from oracle_relationship_discovery.output.dbml_exporter import (
    DbmlExporter,
    dbml_identifier,
    oracle_type,
)
from oracle_relationship_discovery.output.erd_builder import (
    load_erd_model,
    resolve_offline_source,
)
from oracle_relationship_discovery.output.erd_models import (
    ErdColumn,
    ErdExportOptions,
    ErdModel,
    ErdRelationship,
    ErdTable,
)
from oracle_relationship_discovery.output.erd_service import export_erd
from oracle_relationship_discovery.output.schema_metadata import write_schema_metadata


def relationship(
    source_schema: str = "APP",
    source_table: str = "REQUEST",
    source_column: str = "PARTY_ID",
    target_schema: str = "CORE",
    target_table: str = "PARTY",
    target_column: str = "ID",
    *,
    score: float = 90,
    cardinality: str = "Many-to-One",
    status: str = "VALIDATED",
) -> ErdRelationship:
    return ErdRelationship(
        source_schema=source_schema,
        source_table=source_table,
        source_column=source_column,
        target_schema=target_schema,
        target_table=target_table,
        target_column=target_column,
        cardinality=cardinality,
        confidence_score=score,
        confidence_label="HIGH" if score >= 90 else "MEDIUM",
        match_ratio=0.95,
        validation_status=status,
        source_datatype="NUMBER",
        target_datatype="NUMBER",
    )


def synthetic_model(*relationships: ErdRelationship) -> ErdModel:
    tables = (
        ErdTable(
            "APP",
            "CONTRACT",
            (
                ErdColumn("TENANT_ID", "NUMBER", position=1),
                ErdColumn("CONTRACT_ID", "NUMBER", position=2),
            ),
        ),
        ErdTable(
            "APP",
            "LOCAL_SETTINGS",
            (ErdColumn("NAME", "VARCHAR2", data_length=100),),
        ),
        ErdTable(
            "APP",
            "REQUEST",
            (
                ErdColumn("ID", "NUMBER", nullable=False, pk_constraints=("PK_REQUEST",)),
                ErdColumn("PARTY_ID", "NUMBER"),
                ErdColumn("STATUS_ID", "NUMBER"),
            ),
        ),
        ErdTable("CORE", "ACCOUNT", (ErdColumn("ID", "NUMBER"),)),
        ErdTable(
            "CORE",
            "PARTY",
            (
                ErdColumn(
                    "ID",
                    "NUMBER",
                    nullable=False,
                    pk_constraints=("PK_PARTY",),
                ),
            ),
        ),
        ErdTable("REF", "STATUS", (ErdColumn("ID", "NUMBER"),)),
    )
    return ErdModel(tables, tuple(relationships))


def test_validation_defaults_preserve_metadata_evidence_and_exclude_failed(tmp_path: Path):
    model = synthetic_model(
        relationship(status="VALIDATED"),
        relationship(source_column="ACCOUNT_ID", target_table="ACCOUNT", status="FAILED"),
        relationship(
            source_column="LEGACY_ID",
            cardinality="Unknown / Insufficient Evidence",
            status="NOT_RUN",
        ),
        relationship(source_column="DEFERRED_ID", status="SKIPPED"),
    )

    result = export_erd(model, tmp_path, ErdExportOptions(min_confidence=0))[0]
    text = result.path.read_text(encoding="utf-8")

    assert result.input_relationships == 4
    assert result.confidence_qualified_relationships == 4
    assert result.validation_qualified_relationships == 3
    assert result.omitted_by_validation_filter == 1
    assert result.eligible_relationships == 3
    assert result.unknown_cardinality_relationships == 1
    assert result.rendered_relationships == 2
    assert "ACCOUNT_ID" not in text
    assert "Unknown cardinality omitted: 1" in text


def test_validation_filter_can_explicitly_include_failed(tmp_path: Path):
    failed = relationship(status="FAILED")

    result = export_erd(
        synthetic_model(failed),
        tmp_path,
        ErdExportOptions(min_confidence=0, validation_statuses=("FAILED",)),
    )[0]

    assert result.rendered_relationships == 1
    assert result.omitted_by_validation_filter == 0


@pytest.mark.parametrize(
    ("scope", "schemas", "expected_tables", "expected_isolated"),
    [
        ("full", (), 6, 4),
        ("schema", ("APP",), 4, 2),
        ("cross-schema", (), 2, 0),
    ],
)
def test_include_isolated_tables_respects_scope(
    tmp_path: Path,
    scope: str,
    schemas: tuple[str, ...],
    expected_tables: int,
    expected_isolated: int,
):
    result = export_erd(
        synthetic_model(relationship()),
        tmp_path,
        ErdExportOptions(
            scope=scope,
            schemas=schemas,
            min_confidence=0,
            include_isolated_tables=True,
        ),
    )[0]

    assert result.included_tables == expected_tables
    assert result.isolated_tables_included == expected_isolated


def test_schema_export_marks_external_table_and_includes_local_isolated(tmp_path: Path):
    result = export_erd(
        synthetic_model(relationship()),
        tmp_path,
        ErdExportOptions(
            scope="schema",
            schemas=("APP",),
            min_confidence=0,
            include_isolated_tables=True,
        ),
    )[0]
    text = result.path.read_text(encoding="utf-8")

    assert "Table APP.LOCAL_SETTINGS" in text
    assert "Table CORE.PARTY" in text
    assert "External table referenced by APP" in text


def test_exact_directional_duplicates_are_removed_but_reverse_is_preserved(tmp_path: Path):
    forward = relationship()
    duplicate = relationship(score=85)
    reverse = relationship(
        source_schema="CORE",
        source_table="PARTY",
        source_column="ID",
        target_schema="APP",
        target_table="REQUEST",
        target_column="PARTY_ID",
        score=88,
    )

    result = export_erd(
        synthetic_model(forward, duplicate, reverse),
        tmp_path,
        ErdExportOptions(min_confidence=0),
    )[0]
    text = result.path.read_text(encoding="utf-8")

    assert result.duplicate_relationships_omitted == 1
    assert result.rendered_relationships == 2
    assert text.count("\nRef:") == 2


def test_filter_order_and_max_limit_are_deterministic(tmp_path: Path):
    relationships = (
        relationship(source_column="Z_ID", score=85),
        relationship(source_column="A_ID", score=85),
        relationship(source_column="FAILED_ID", score=99, status="FAILED"),
        relationship(
            source_column="STATUS_ID",
            target_schema="REF",
            target_table="STATUS",
            score=98,
        ),
        relationship(source_column="LOW_ID", score=60),
    )
    options = ErdExportOptions(
        min_confidence=80,
        max_relationships=1,
        exclude_generic=True,
        generic_entities=("STATUS",),
    )

    result = export_erd(synthetic_model(*reversed(relationships)), tmp_path, options)[0]
    text = result.path.read_text(encoding="utf-8")

    assert result.confidence_qualified_relationships == 4
    assert result.validation_qualified_relationships == 3
    assert result.eligible_relationships == 2
    assert result.omitted_by_limit == 1
    assert "A_ID" in text
    assert "Z_ID" not in text


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        (ErdColumn("C", "NUMBER"), "NUMBER"),
        (ErdColumn("C", "NUMBER", precision=19), "NUMBER(19)"),
        (ErdColumn("C", "NUMBER", precision=10, scale=2), "NUMBER(10,2)"),
        (ErdColumn("C", "VARCHAR2", data_length=255), "VARCHAR2(255)"),
        (ErdColumn("C", "NVARCHAR2", data_length=80), "NVARCHAR2(80)"),
        (ErdColumn("C", "CHAR", data_length=1), "CHAR(1)"),
        (ErdColumn("C", "NCHAR", data_length=2), "NCHAR(2)"),
        (ErdColumn("C", "DATE"), "DATE"),
        (ErdColumn("C", "TIMESTAMP"), "TIMESTAMP"),
        (ErdColumn("C", "TIMESTAMP", scale=6), "TIMESTAMP(6)"),
        (ErdColumn("C", "TIMESTAMP(6)"), "TIMESTAMP(6)"),
        (
            ErdColumn("C", "TIMESTAMP WITH TIME ZONE"),
            '"TIMESTAMP WITH TIME ZONE"',
        ),
        (
            ErdColumn("C", "TIMESTAMP WITH TIME ZONE", scale=6),
            '"TIMESTAMP(6) WITH TIME ZONE"',
        ),
        (ErdColumn("C", "CLOB"), "CLOB"),
        (ErdColumn("C", "NCLOB"), "NCLOB"),
        (ErdColumn("C", "BLOB"), "BLOB"),
        (ErdColumn("C", "RAW", data_length=16), "RAW(16)"),
        (ErdColumn("C", "FLOAT", precision=126), "FLOAT(126)"),
        (ErdColumn("C", "BINARY_FLOAT"), "BINARY_FLOAT"),
        (ErdColumn("C", "BINARY_DOUBLE"), "BINARY_DOUBLE"),
        (
            ErdColumn("C", "INTERVAL YEAR TO MONTH"),
            '"INTERVAL YEAR TO MONTH"',
        ),
        (
            ErdColumn("C", "INTERVAL DAY TO SECOND"),
            '"INTERVAL DAY TO SECOND"',
        ),
    ],
)
def test_oracle_datatypes_are_preserved(column: ErdColumn, expected: str):
    assert oracle_type(column) == expected


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("ORDER", "ORDER"),
        ("TABLE", '"TABLE"'),
        ("WITH SPACE", '"WITH SPACE"'),
        ("A$B", "A$B"),
        ("A#B", "A#B"),
        ("A_B", "A_B"),
        ("MixedCase", "MixedCase"),
        ('A"B', '"A\\"B"'),
    ],
)
def test_identifiers_are_safely_emitted(identifier: str, expected: str):
    assert dbml_identifier(identifier) == expected


@pytest.mark.parametrize("identifier", ["", "BAD\nNAME", "BAD\x7fNAME"])
def test_invalid_control_identifiers_are_rejected(identifier: str):
    with pytest.raises(ValueError, match="Invalid DBML identifier"):
        dbml_identifier(identifier)


def test_multiple_composite_constraints_and_names_are_escaped(tmp_path: Path):
    constraint_name = "UK_O'Reilly\\Code"
    table = ErdTable(
        "APP",
        "MIXED_KEYS",
        (
            ErdColumn(
                "TENANT_ID",
                "NUMBER",
                position=1,
                pk_constraints=("PK_MIXED",),
                composite_constraints=("PK_MIXED",),
            ),
            ErdColumn(
                "ITEM_ID",
                "NUMBER",
                position=2,
                pk_constraints=("PK_MIXED",),
                composite_constraints=("PK_MIXED",),
            ),
            ErdColumn(
                "REGION",
                "VARCHAR2",
                position=3,
                unique_constraints=(constraint_name,),
                composite_constraints=(constraint_name,),
            ),
            ErdColumn(
                "CODE",
                "VARCHAR2",
                position=4,
                unique_constraints=(constraint_name,),
                composite_constraints=(constraint_name,),
            ),
        ),
    )
    destination = tmp_path / "composite.dbml"

    DbmlExporter().export(
        ErdModel((table,), ()),
        destination,
        ErdExportOptions(include_isolated_tables=True),
    )
    text = destination.read_text(encoding="utf-8")

    assert "TENANT_ID NUMBER [pk" not in text
    assert "(TENANT_ID, ITEM_ID) [pk, name: 'PK_MIXED']" in text
    assert "(REGION, CODE) [unique, name: 'UK_O\\'Reilly\\\\Code']" in text


def test_empty_erd_is_valid_and_reports_zero(tmp_path: Path):
    result = export_erd(
        synthetic_model(),
        tmp_path,
        ErdExportOptions(min_confidence=100),
    )[0]
    text = result.path.read_text(encoding="utf-8")

    assert result.eligible_relationships == 0
    assert result.rendered_relationships == 0
    assert result.included_tables == 0
    assert "Rendered DBML references: 0" in text


def test_unknown_schema_is_actionable(tmp_path: Path):
    with pytest.raises(ValueError, match="ERD schema not present in metadata: MISSING"):
        export_erd(
            synthetic_model(),
            tmp_path,
            ErdExportOptions(scope="schema", schemas=("MISSING",)),
        )


def test_new_artifact_beats_filtered_legacy_csv_and_allows_lower_threshold(
    tmp_path: Path,
):
    run = tmp_path / "run"
    run.mkdir()
    high = relationship(score=95)
    lower = relationship(source_column="LOWER_ID", score=68)
    write_analysis_results(
        run / "analysis-results.json",
        (high, lower),
        "sampled",
        "2026-08-31T10:00:00+03:30",
    )
    with (run / "relationships.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_schema",
                "source_table",
                "source_column",
                "target_schema",
                "target_table",
                "target_column",
                "confidence_score",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_schema": "APP",
                "source_table": "REQUEST",
                "source_column": "PARTY_ID",
                "target_schema": "CORE",
                "target_table": "PARTY",
                "target_column": "ID",
                "confidence_score": 95,
            }
        )
    source = resolve_offline_source(run / "relationships.csv")
    loaded = load_erd_model(source.path)
    result = export_erd(
        loaded,
        run / "erd",
        ErdExportOptions(min_confidence=60),
    )[0]

    assert source.path.name == "analysis-results.json"
    assert source.legacy_csv is False
    assert result.eligible_relationships == 2
    assert "LOWER_ID" in result.path.read_text(encoding="utf-8")


def test_legacy_csv_fallback_still_works_without_metadata(tmp_path: Path):
    csv_path = tmp_path / "relationships.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_schema",
                "source_table",
                "source_column",
                "target_schema",
                "target_table",
                "target_column",
                "confidence_score",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_schema": "APP",
                "source_table": "REQUEST",
                "source_column": "PARTY_ID",
                "target_schema": "CORE",
                "target_table": "PARTY",
                "target_column": "ID",
                "confidence_score": 90,
            }
        )

    source = resolve_offline_source(csv_path)
    model = load_erd_model(source.path)

    assert source.legacy_csv is True
    assert len(model.tables) == 2
    assert model.relationships[0].validation_status == "NOT_RUN"


def test_synthetic_artifacts_generate_full_cross_and_schema_outputs(tmp_path: Path):
    run = tmp_path / "synthetic"
    relationships = (
        relationship(score=95),
        relationship(
            source_table="CONTRACT",
            source_column="ACCOUNT_ID",
            target_table="ACCOUNT",
            score=91,
            cardinality="One-to-One",
        ),
        relationship(
            source_column="UNKNOWN_ID",
            score=89,
            cardinality="Unknown / Insufficient Evidence",
            status="NOT_RUN",
        ),
        relationship(
            source_column="STATUS_ID",
            target_schema="REF",
            target_table="STATUS",
            score=88,
            status="SKIPPED",
        ),
        relationship(source_column="FAILED_ID", score=99, status="FAILED"),
        relationship(
            source_table="CONTRACT",
            source_column="LOCAL_ID",
            target_schema="APP",
            target_table="REQUEST",
            score=84,
        ),
    )
    model = synthetic_model(*relationships)
    write_analysis_results(
        run / "analysis-results.json",
        model.relationships,
        "sampled",
        "now",
    )
    metadata_tables = [
        TableMetadata(
            table.schema,
            table.name,
            columns=[
                ColumnMetadata(
                    table.schema,
                    table.name,
                    column.name,
                    column.data_type,
                    data_length=column.data_length,
                    precision=column.precision,
                    scale=column.scale,
                    nullable=column.nullable,
                    position=column.position,
                    pk_constraints=column.pk_constraints,
                    unique_constraints=column.unique_constraints,
                    composite_constraints=column.composite_constraints,
                )
                for column in table.columns
            ],
        )
        for table in model.tables
    ]
    write_schema_metadata(run / "schema-metadata.json", metadata_tables, "now")
    (run / "relationships.csv").write_text(
        "source_schema,source_table,source_column,target_schema,target_table,"
        "target_column,confidence_score\n"
        "APP,REQUEST,PARTY_ID,CORE,PARTY,ID,95\n",
        encoding="utf-8",
    )

    loaded = load_erd_model(
        run / "analysis-results.json",
        run / "schema-metadata.json",
    )
    full = export_erd(
        loaded,
        run / "erd-full",
        ErdExportOptions(
            min_confidence=80,
            include_isolated_tables=True,
        ),
    )[0]
    cross = export_erd(
        loaded,
        run / "erd-cross",
        ErdExportOptions(scope="cross-schema", min_confidence=80),
    )[0]
    schema = export_erd(
        loaded,
        run / "erd-schema",
        ErdExportOptions(
            scope="schema",
            schemas=("APP",),
            min_confidence=80,
            include_isolated_tables=True,
        ),
    )[0]

    assert (run / "analysis-results.json").is_file()
    assert (run / "schema-metadata.json").is_file()
    assert (run / "relationships.csv").is_file()
    assert full.path.name == "full.dbml"
    assert cross.path.name == "cross-schema.dbml"
    assert schema.path.name == "APP.dbml"
    assert full.omitted_by_validation_filter == 1
    assert full.unknown_cardinality_relationships == 1
    assert full.isolated_tables_included >= 1
    assert cross.rendered_relationships == 3
    assert "LOCAL_ID" not in cross.path.read_text(encoding="utf-8")
    assert "External table referenced by APP" in schema.path.read_text(encoding="utf-8")


def test_malformed_legacy_csv_is_actionable(tmp_path: Path):
    path = tmp_path / "relationships.csv"
    path.write_text("source_schema,confidence_score\nAPP,not-a-number\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_erd_model(path)


def test_schema_metadata_rejects_unsupported_version(tmp_path: Path):
    from oracle_relationship_discovery.output.schema_metadata import read_schema_metadata

    path = tmp_path / "schema-metadata.json"
    path.write_text('{"format_version": 2, "tables": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported schema metadata format_version"):
        read_schema_metadata(path)


def test_service_rejects_unknown_validation_status(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown ERD validation status"):
        export_erd(
            synthetic_model(relationship()),
            tmp_path,
            ErdExportOptions(validation_statuses=("BROKEN",)),
        )


def test_dedup_prefers_validated_evidence_over_higher_failed_score(tmp_path: Path):
    validated = relationship(score=85, status="VALIDATED")
    failed = relationship(score=99, status="FAILED")

    result = export_erd(
        synthetic_model(failed, validated),
        tmp_path,
        ErdExportOptions(min_confidence=0),
    )[0]
    text = result.path.read_text(encoding="utf-8")

    assert result.duplicate_relationships_omitted == 1
    assert result.rendered_relationships == 1
    assert "// Confidence: 85" in text
    assert "// Validation status: VALIDATED" in text
