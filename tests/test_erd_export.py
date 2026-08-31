import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from oracle_relationship_discovery.models import ColumnMetadata, TableMetadata
from oracle_relationship_discovery.output.dbml_exporter import (
    DbmlExporter,
    dbml_identifier,
    oracle_type,
)
from oracle_relationship_discovery.output.erd_builder import load_erd_model
from oracle_relationship_discovery.output.erd_models import (
    ErdColumn,
    ErdExportOptions,
    ErdModel,
    ErdRelationship,
    ErdTable,
)
from oracle_relationship_discovery.output.erd_service import export_erd
from oracle_relationship_discovery.output.schema_metadata import (
    read_schema_metadata,
    write_schema_metadata,
)


def relationship(
    score: float = 92,
    *,
    source_schema: str = "SALES",
    target_schema: str = "CORE",
    cardinality: str = "Many-to-One",
    source_table: str = "ORDERS",
) -> ErdRelationship:
    return ErdRelationship(
        source_schema,
        source_table,
        "CUSTOMER_ID",
        target_schema,
        "CUSTOMERS",
        "ID",
        cardinality,
        score,
        "HIGH",
        0.975,
        "VALIDATED",
    )


def model(*relationships: ErdRelationship) -> ErdModel:
    tables = (
        ErdTable(
            "SALES",
            "ORDERS",
            (
                ErdColumn("ID", "NUMBER", precision=12, scale=0, nullable=False, position=1),
                ErdColumn("CUSTOMER_ID", "NUMBER", precision=12, scale=0, position=2),
            ),
        ),
        ErdTable(
            "CORE",
            "CUSTOMERS",
            (
                ErdColumn(
                    "ID",
                    "NUMBER",
                    precision=12,
                    scale=0,
                    nullable=False,
                    position=1,
                    pk_constraints=("PK_CUSTOMERS",),
                ),
                ErdColumn(
                    "REGION",
                    "VARCHAR2",
                    data_length=20,
                    position=2,
                    unique_constraints=("UK_CUSTOMER_REGION_CODE",),
                    composite_constraints=("UK_CUSTOMER_REGION_CODE",),
                ),
                ErdColumn(
                    "CODE",
                    "VARCHAR2",
                    data_length=30,
                    position=3,
                    unique_constraints=("UK_CUSTOMER_REGION_CODE",),
                    composite_constraints=("UK_CUSTOMER_REGION_CODE",),
                ),
            ),
        ),
    )
    return ErdModel(tables, tuple(relationships))


def test_dbml_preserves_oracle_types_keys_and_evidence(tmp_path: Path):
    destination = tmp_path / "full.dbml"
    unknown = relationship(cardinality="Unknown / Insufficient Evidence")
    exporter = DbmlExporter()

    count = exporter.export(
        model(relationship(), unknown),
        destination,
        ErdExportOptions(min_confidence=80),
    )

    text = destination.read_text(encoding="utf-8")
    assert "ID NUMBER(12,0) [pk, not null]" in text
    assert "CUSTOMER_ID NUMBER(12,0)" in text
    assert "REGION VARCHAR2(20)" in text
    assert "(REGION, CODE) [unique, name: 'UK_CUSTOMER_REGION_CODE']" in text
    assert "Ref: SALES.ORDERS.CUSTOMER_ID > CORE.CUSTOMERS.ID" in text
    assert "// Confidence: 92 (HIGH)" in text
    assert "// Sample match: 97.50%" in text
    assert "Ref omitted: DBML has no neutral operator" in text
    assert count == 1


def test_identifier_and_type_escaping_are_safe():
    assert dbml_identifier("ORDER") == "ORDER"
    assert dbml_identifier("Order Detail") == '"Order Detail"'
    assert oracle_type(ErdColumn("CREATED_AT", "TIMESTAMP(6) WITH TIME ZONE")) == (
        '"TIMESTAMP(6) WITH TIME ZONE"'
    )
    with pytest.raises(ValueError):
        dbml_identifier("BAD\nNAME")


def test_scope_threshold_limit_and_external_table_note(tmp_path: Path):
    candidates = (
        relationship(95),
        relationship(85, source_table="ORDER_ARCHIVE"),
        relationship(70, source_schema="CORE", target_schema="CORE"),
    )
    expanded = model(*candidates)
    expanded = ErdModel(
        expanded.tables
        + (
            ErdTable(
                "SALES",
                "ORDER_ARCHIVE",
                (ErdColumn("CUSTOMER_ID", "NUMBER"),),
            ),
        ),
        expanded.relationships,
    )

    results = export_erd(
        expanded,
        tmp_path,
        ErdExportOptions(
            scope="schema",
            schemas=("SALES",),
            min_confidence=80,
            max_relationships=1,
        ),
    )

    assert len(results) == 1
    assert results[0].relationship_count == 1
    assert results[0].omitted_by_limit == 1
    text = results[0].path.read_text(encoding="utf-8")
    assert "External table referenced by SALES" in text
    assert "ORDER_ARCHIVE" not in text


def test_cross_schema_scope_excludes_same_schema_relationships(tmp_path: Path):
    same_schema = relationship(99, source_schema="CORE", target_schema="CORE")
    result = export_erd(
        model(relationship(), same_schema),
        tmp_path,
        ErdExportOptions(scope="cross-schema", min_confidence=0),
    )[0]

    text = result.path.read_text(encoding="utf-8")
    assert result.relationship_count == 1
    assert "cross-schema.dbml" in str(result.path)
    assert text.count("\nRef:") == 1


def test_schema_metadata_round_trip_contains_no_sample_values(tmp_path: Path):
    table = TableMetadata(
        "CORE",
        "CUSTOMERS",
        estimated_rows=10,
        last_analyzed=datetime(2026, 8, 29, tzinfo=UTC),
        columns=[
            ColumnMetadata(
                "CORE",
                "CUSTOMERS",
                "ID",
                "NUMBER",
                precision=12,
                scale=0,
                nullable=False,
                position=1,
                pk_constraints=("PK_CUSTOMERS",),
            )
        ],
    )
    destination = tmp_path / "schema-metadata.json"
    write_schema_metadata(destination, [table], "2026-08-29T00:00:00+00:00")

    raw = destination.read_text(encoding="utf-8")
    payload = json.loads(raw)
    restored = read_schema_metadata(destination)
    assert payload["privacy"].startswith("Metadata only")
    assert "sample" not in raw.lower().replace("sampled values", "")
    assert restored[0].columns[0].pk_constraints == ("PK_CUSTOMERS",)
    assert restored[0].columns[0].precision == 12


def test_offline_csv_adapter_uses_metadata_when_available(tmp_path: Path):
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
                "source_datatype",
                "target_datatype",
                "cardinality",
                "confidence_score",
                "confidence_label",
                "match_ratio",
                "validation_status",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_schema": "SALES",
                "source_table": "ORDERS",
                "source_column": "CUSTOMER_ID",
                "target_schema": "CORE",
                "target_table": "CUSTOMERS",
                "target_column": "ID",
                "source_datatype": "NUMBER",
                "target_datatype": "NUMBER",
                "cardinality": "Many-to-One",
                "confidence_score": "91",
                "confidence_label": "HIGH",
                "match_ratio": "98.5",
                "validation_status": "VALIDATED",
            }
        )
    metadata = tmp_path / "schema-metadata.json"
    write_schema_metadata(
        metadata,
        [
            TableMetadata(
                "SALES",
                "ORDERS",
                columns=[ColumnMetadata("SALES", "ORDERS", "CUSTOMER_ID", "NUMBER")],
            ),
            TableMetadata(
                "CORE",
                "CUSTOMERS",
                columns=[
                    ColumnMetadata(
                        "CORE",
                        "CUSTOMERS",
                        "ID",
                        "NUMBER",
                        pk_constraints=("PK_CUSTOMERS",),
                    )
                ],
            ),
        ],
        "",
    )

    loaded = load_erd_model(csv_path, metadata)

    assert loaded.relationships[0].match_ratio == pytest.approx(0.985)
    assert loaded.tables[0].columns[0].pk_constraints == ("PK_CUSTOMERS",)


def test_same_table_names_across_schemas_and_one_to_one_are_distinct(tmp_path: Path):
    duplicate_tables = ErdModel(
        (
            ErdTable("CORE", "USER", (ErdColumn("ID", "NUMBER"),)),
            ErdTable("AUTH", "USER", (ErdColumn("ID", "NUMBER"),)),
        ),
        (
            ErdRelationship(
                "AUTH",
                "USER",
                "ID",
                "CORE",
                "USER",
                "ID",
                "One-to-One",
                99,
                "HIGH",
            ),
        ),
    )

    result = export_erd(
        duplicate_tables,
        tmp_path,
        ErdExportOptions(min_confidence=0),
    )[0]
    text = result.path.read_text(encoding="utf-8")

    assert "Table AUTH.USER" in text
    assert "Table CORE.USER" in text
    assert "Ref: CORE.USER.ID - AUTH.USER.ID" in text


def test_generic_filter_is_optional_and_order_is_deterministic(tmp_path: Path):
    generic = ErdRelationship(
        "APP",
        "ITEM",
        "STATUS_ID",
        "REF",
        "STATUS",
        "ID",
        "Many-to-One",
        99,
        "HIGH",
    )
    ordinary_low = relationship(81, source_table="Z_ORDERS")
    ordinary_high = relationship(93, source_table="A_ORDERS")
    expanded = model(generic, ordinary_low, ordinary_high)
    expanded = ErdModel(
        expanded.tables
        + (
            ErdTable("APP", "ITEM", (ErdColumn("STATUS_ID", "NUMBER"),)),
            ErdTable("REF", "STATUS", (ErdColumn("ID", "NUMBER"),)),
            ErdTable("SALES", "Z_ORDERS", (ErdColumn("CUSTOMER_ID", "NUMBER"),)),
            ErdTable("SALES", "A_ORDERS", (ErdColumn("CUSTOMER_ID", "NUMBER"),)),
        ),
        expanded.relationships,
    )

    included = export_erd(
        expanded,
        tmp_path / "included",
        ErdExportOptions(min_confidence=80),
    )[0].path.read_text(encoding="utf-8")
    excluded = export_erd(
        expanded,
        tmp_path / "excluded",
        ErdExportOptions(
            min_confidence=80,
            exclude_generic=True,
            generic_entities=("STATUS", "TYPE", "CATEGORY", "USER", "CODE"),
        ),
    )[0].path.read_text(encoding="utf-8")

    assert "APP.ITEM.STATUS_ID" in included
    assert "APP.ITEM.STATUS_ID" not in excluded
    assert excluded.index("A_ORDERS.CUSTOMER_ID") < excluded.index("Z_ORDERS.CUSTOMER_ID")


def test_exporter_layer_contains_no_database_dependency():
    import inspect

    from oracle_relationship_discovery.output import dbml_exporter, erd_service

    source = inspect.getsource(dbml_exporter) + inspect.getsource(erd_service)
    assert "oracle_relationship_discovery.db" not in source
    assert "connect(" not in source
