import { MarkerType } from "@xyflow/react";

import type { ErdGraphResponse, ErdGraphTable, RelationshipListItem } from "../../api/client";
import {
  DEFAULT_REMAINING_COLUMNS,
  TABLE_COLUMN_HEIGHT,
  TABLE_HEADER_HEIGHT,
  TABLE_MORE_HEIGHT,
  TABLE_NODE_WIDTH,
  type ErdFilters,
  type ErdRelationshipEdge,
  type ErdTableNode,
  type ErdVisualization,
  type VisibleColumn,
} from "./erd-types";

export function buildErdVisualization(
  graph: ErdGraphResponse,
  filters: ErdFilters,
  expandedTables: ReadonlySet<string>,
  focusTableId: string | null,
  selectedTableId: string | null,
  selectedRelationshipId: string | null,
): ErdVisualization {
  const tableByEndpoint = new Map(
    graph.tables.map((table) => [tableKey(table.schema_name, table.table_name), table]),
  );
  const tableIdByEndpoint = new Map(
    graph.tables.map((table) => [tableKey(table.schema_name, table.table_name), table.id]),
  );
  const allowedSchemas = new Set(filters.schemas);
  let relationships = graph.relationships.filter(
    (relationship) =>
      relationship.confidence_score >= filters.minConfidence &&
      (!filters.validationStatus || relationship.validation_status === filters.validationStatus) &&
      (!filters.crossSchemaOnly || relationship.cross_schema) &&
      allowedSchemas.has(relationship.source.schema_name) &&
      allowedSchemas.has(relationship.target.schema_name),
  );

  if (focusTableId) {
    relationships = relationships.filter(
      (relationship) =>
        tableIdByEndpoint.get(
          tableKey(relationship.source.schema_name, relationship.source.table_name),
        ) === focusTableId ||
        tableIdByEndpoint.get(
          tableKey(relationship.target.schema_name, relationship.target.table_name),
        ) === focusTableId,
    );
  }

  const includedTableIds = new Set<string>();
  for (const relationship of relationships) {
    includedTableIds.add(
      tableIdByEndpoint.get(
        tableKey(relationship.source.schema_name, relationship.source.table_name),
      )!,
    );
    includedTableIds.add(
      tableIdByEndpoint.get(
        tableKey(relationship.target.schema_name, relationship.target.table_name),
      )!,
    );
  }
  const focusTable = graph.tables.find((table) => table.id === focusTableId);
  if (focusTableId && focusTable && allowedSchemas.has(focusTable.schema_name)) {
    includedTableIds.add(focusTableId);
  }

  const selectedNeighborIds = connectedTableIds(
    relationships,
    selectedTableId,
    selectedRelationshipId,
    tableIdByEndpoint,
  );
  const nodes = graph.tables
    .filter((table) => includedTableIds.has(table.id))
    .map((table, index) =>
      tableNode(
        table,
        relationships,
        expandedTables.has(table.id),
        selectedNeighborIds.has(table.id),
        index,
      ),
    );
  const edges = relationships.map((relationship) =>
    relationshipEdge(relationship, selectedRelationshipId, selectedTableId, tableIdByEndpoint),
  );

  for (const relationship of relationships) {
    const sourceKey = tableKey(relationship.source.schema_name, relationship.source.table_name);
    const targetKey = tableKey(relationship.target.schema_name, relationship.target.table_name);
    if (!tableByEndpoint.has(sourceKey) || !tableByEndpoint.has(targetKey)) {
      throw new Error("ERD relationship references unavailable table metadata.");
    }
  }

  return {
    nodes,
    edges,
    relationships,
    focusHasNeighbors: !focusTableId || relationships.length > 0,
  };
}

export function tableKey(schema: string, table: string): string {
  return `${schema}\u0000${table}`;
}

export function columnHandle(kind: "source" | "target", column: string): string {
  return `${kind}:${encodeURIComponent(column)}`;
}

function tableNode(
  table: ErdGraphTable,
  relationships: RelationshipListItem[],
  expanded: boolean,
  neighborHighlighted: boolean,
  index: number,
): ErdTableNode {
  const sourceColumns = new Set<string>();
  const targetColumns = new Set<string>();
  let incomingCount = 0;
  let outgoingCount = 0;
  for (const relationship of relationships) {
    if (
      relationship.source.schema_name === table.schema_name &&
      relationship.source.table_name === table.table_name
    ) {
      sourceColumns.add(relationship.source.column_name);
      outgoingCount += 1;
    }
    if (
      relationship.target.schema_name === table.schema_name &&
      relationship.target.table_name === table.table_name
    ) {
      targetColumns.add(relationship.target.column_name);
      incomingCount += 1;
    }
  }
  const visibleColumns = selectColumns(table, sourceColumns, targetColumns, expanded);
  const hiddenColumnCount = table.columns.length - visibleColumns.length;
  const height =
    TABLE_HEADER_HEIGHT +
    visibleColumns.length * TABLE_COLUMN_HEIGHT +
    (hiddenColumnCount > 0 ? TABLE_MORE_HEIGHT : 0);

  return {
    id: table.id,
    type: "erdTable",
    position: { x: (index % 4) * 330, y: Math.floor(index / 4) * 260 },
    width: TABLE_NODE_WIDTH,
    height,
    data: {
      table,
      visibleColumns,
      hiddenColumnCount,
      incomingCount,
      outgoingCount,
      neighborHighlighted,
      width: TABLE_NODE_WIDTH,
      height,
    },
    selected: false,
    ariaLabel: `Table ${table.schema_name}.${table.table_name}`,
  };
}

function selectColumns(
  table: ErdGraphTable,
  sourceColumns: ReadonlySet<string>,
  targetColumns: ReadonlySet<string>,
  expanded: boolean,
): VisibleColumn[] {
  const sorted = [...table.columns].sort(
    (left, right) => left.position - right.position || left.name.localeCompare(right.name),
  );
  const decorated = sorted.map((column) => ({
    ...column,
    sourceConnected: sourceColumns.has(column.name),
    targetConnected: targetColumns.has(column.name),
  }));
  if (expanded) return decorated;
  const essential = decorated.filter(
    (column) =>
      column.relationship_connected ||
      column.primary_key ||
      column.unique_key ||
      column.composite_key,
  );
  const essentialNames = new Set(essential.map((column) => column.name));
  const remaining = decorated
    .filter((column) => !essentialNames.has(column.name))
    .slice(0, DEFAULT_REMAINING_COLUMNS);
  const visibleNames = new Set([...essential, ...remaining].map((column) => column.name));
  return decorated.filter((column) => visibleNames.has(column.name));
}

function relationshipEdge(
  relationship: RelationshipListItem,
  selectedRelationshipId: string | null,
  selectedTableId: string | null,
  tableIdByEndpoint: ReadonlyMap<string, string>,
): ErdRelationshipEdge {
  const source = tableIdByEndpoint.get(
    tableKey(relationship.source.schema_name, relationship.source.table_name),
  )!;
  const target = tableIdByEndpoint.get(
    tableKey(relationship.target.schema_name, relationship.target.table_name),
  )!;
  return {
    id: relationship.id,
    type: "erdRelationship",
    source,
    target,
    sourceHandle: columnHandle("source", relationship.source.column_name),
    targetHandle: columnHandle("target", relationship.target.column_name),
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
    data: {
      relationship,
      highlighted: Boolean(
        selectedTableId && (source === selectedTableId || target === selectedTableId),
      ),
    },
    selected: relationship.id === selectedRelationshipId,
    focusable: true,
    ariaLabel: `${relationship.source.schema_name}.${relationship.source.table_name}.${relationship.source.column_name} to ${relationship.target.schema_name}.${relationship.target.table_name}.${relationship.target.column_name}`,
  };
}
function connectedTableIds(
  relationships: RelationshipListItem[],
  selectedTableId: string | null,
  selectedRelationshipId: string | null,
  tableIdByEndpoint: ReadonlyMap<string, string>,
): Set<string> {
  const result = new Set<string>();
  for (const relationship of relationships) {
    const sourceId = tableIdByEndpoint.get(
      tableKey(relationship.source.schema_name, relationship.source.table_name),
    )!;
    const targetId = tableIdByEndpoint.get(
      tableKey(relationship.target.schema_name, relationship.target.table_name),
    )!;
    if (
      sourceId === selectedTableId ||
      targetId === selectedTableId ||
      relationship.id === selectedRelationshipId
    ) {
      result.add(sourceId);
      result.add(targetId);
    }
  }
  return result;
}
