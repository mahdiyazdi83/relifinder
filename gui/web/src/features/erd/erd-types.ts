import type { Edge, Node } from "@xyflow/react";

import type { ErdGraphColumn, ErdGraphTable, RelationshipListItem } from "../../api/client";

export const DEFAULT_REMAINING_COLUMNS = 8;
export const TABLE_NODE_WIDTH = 268;
export const TABLE_HEADER_HEIGHT = 48;
export const TABLE_COLUMN_HEIGHT = 24;
export const TABLE_MORE_HEIGHT = 28;

export type ErdFilters = {
  minConfidence: number;
  schemas: string[];
  validationStatus: string;
  crossSchemaOnly: boolean;
};

export type VisibleColumn = ErdGraphColumn & {
  sourceConnected: boolean;
  targetConnected: boolean;
};

export type TableNodeData = {
  [key: string]: unknown;
  table: ErdGraphTable;
  visibleColumns: VisibleColumn[];
  hiddenColumnCount: number;
  incomingCount: number;
  outgoingCount: number;
  neighborHighlighted: boolean;
  width: number;
  height: number;
};

export type RelationshipEdgeData = {
  [key: string]: unknown;
  relationship: RelationshipListItem;
  highlighted: boolean;
};

export type ErdTableNode = Node<TableNodeData, "erdTable">;
export type ErdRelationshipEdge = Edge<RelationshipEdgeData, "erdRelationship">;

export type ErdVisualization = {
  nodes: ErdTableNode[];
  edges: ErdRelationshipEdge[];
  relationships: RelationshipListItem[];
  focusHasNeighbors: boolean;
};
