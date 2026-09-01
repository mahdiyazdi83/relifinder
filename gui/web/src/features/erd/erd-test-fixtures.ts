import type { ErdGraphResponse, ErdGraphTable, RelationshipListItem } from "../../api/client";

export function erdFixture(): ErdGraphResponse {
  const tables = [
    table("1", "APP", "REQUEST", 16, "PARTY_ID"),
    table("2", "CORE", "PARTY", 4, "ID"),
    table("3", "APP", "AUDIT", 4, "TYPE_ID"),
    table("4", "APP", "TYPE", 4, "ID"),
  ];
  return {
    run_id: "erd-test-run",
    default_min_confidence: 60,
    schemas: ["APP", "CORE"],
    tables,
    relationships: [
      relationship("a", tables[0]!, "PARTY_ID", tables[1]!, "ID", 96, "VALIDATED", true),
      relationship(
        "b",
        tables[0]!,
        "PARTY_ID",
        tables[2]!,
        "TYPE_ID",
        78,
        "NOT_RUN",
        false,
        "Unknown / Insufficient Evidence",
      ),
      relationship("c", tables[2]!, "TYPE_ID", tables[3]!, "ID", 44, "FAILED", false),
    ],
  };
}

export function stressGraph(tableCount: number, edgeCount: number): ErdGraphResponse {
  const tables = Array.from({ length: tableCount }, (_, index) =>
    table((index + 1).toString(16), `S${index % 3}`, `TABLE_${index}`, 4, "REF_ID"),
  );
  const relationships = Array.from({ length: edgeCount }, (_, index) => {
    const sourceIndex = index % tableCount;
    let targetIndex = (index * 7 + 3) % tableCount;
    if (targetIndex === sourceIndex) targetIndex = (targetIndex + 1) % tableCount;
    return relationship(
      (index + 1).toString(16),
      tables[sourceIndex]!,
      "REF_ID",
      tables[targetIndex]!,
      "ID",
      70 + (index % 27),
      index % 4 === 0 ? "NOT_RUN" : "VALIDATED",
      tables[sourceIndex]!.schema_name !== tables[targetIndex]!.schema_name,
      index % 9 === 0 ? "Unknown / Insufficient Evidence" : "Many-to-One",
    );
  });
  return {
    run_id: `stress-${tableCount}-${edgeCount}`,
    default_min_confidence: 0,
    schemas: [...new Set(tables.map((item) => item.schema_name))],
    tables,
    relationships,
  };
}

function table(
  idSeed: string,
  schema: string,
  tableName: string,
  columnCount: number,
  connectedColumn: string,
): ErdGraphTable {
  const names =
    connectedColumn === "ID"
      ? ["ID", ...Array.from({ length: columnCount - 1 }, (_, i) => `FIELD_${i + 1}`)]
      : [
          "ID",
          connectedColumn,
          ...Array.from({ length: columnCount - 2 }, (_, i) => `FIELD_${i + 1}`),
        ];
  return {
    id: idSeed.padStart(64, "0"),
    schema_name: schema,
    table_name: tableName,
    estimated_rows: 1000,
    columns: names.map((name, index) => ({
      name,
      datatype: name.startsWith("FIELD") ? "VARCHAR2" : "NUMBER",
      nullable: name !== "ID",
      position: index + 1,
      primary_key: name === "ID",
      unique_key: false,
      composite_key: false,
      relationship_connected: name === connectedColumn || name === "ID",
    })),
  };
}

function relationship(
  idSeed: string,
  sourceTable: ErdGraphTable,
  sourceColumn: string,
  targetTable: ErdGraphTable,
  targetColumn: string,
  confidence: number,
  validation: RelationshipListItem["validation_status"],
  crossSchema: boolean,
  cardinality = "Many-to-One",
): RelationshipListItem {
  return {
    id: idSeed.padStart(64, "0"),
    source: {
      schema_name: sourceTable.schema_name,
      table_name: sourceTable.table_name,
      column_name: sourceColumn,
      datatype: "NUMBER",
    },
    target: {
      schema_name: targetTable.schema_name,
      table_name: targetTable.table_name,
      column_name: targetColumn,
      datatype: "NUMBER",
    },
    confidence_score: confidence,
    confidence_label: confidence >= 85 ? "HIGH" : confidence >= 65 ? "MEDIUM-HIGH" : "LOW",
    cardinality,
    validation_status: validation,
    match_ratio: validation === "VALIDATED" ? 0.94 : null,
    cross_schema: crossSchema,
    target_key_type: "PRIMARY_KEY",
  };
}
