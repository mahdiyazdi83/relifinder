import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type EdgeMouseHandler,
  type NodeMouseHandler,
} from "@xyflow/react";
import { AlertTriangle, Network } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ErdGraphResponse } from "../../api/client";
import { RelationshipInspector } from "../results/relationship-inspector";
import { useRelationshipDetail } from "../results/results-api";
import { ErdNodeActionsProvider } from "./erd-node-actions";
import { ErdRelationshipEdgeView } from "./erd-relationship-edge";
import { ErdTableInspector } from "./erd-table-inspector";
import { ErdTableNodeView } from "./erd-table-node";
import { ErdToolbar } from "./erd-toolbar";
import { fallbackGridLayout, layoutErdGraph } from "./erd-layout";
import type { ErdFilters, ErdRelationshipEdge, ErdTableNode, ErdVisualization } from "./erd-types";

const nodeTypes = { erdTable: ErdTableNodeView };
const edgeTypes = { erdRelationship: ErdRelationshipEdgeView };

export function ErdWorkspace(props: ErdWorkspaceProps) {
  return (
    <ReactFlowProvider>
      <ErdWorkspaceInner {...props} />
    </ReactFlowProvider>
  );
}

type ErdWorkspaceProps = {
  runId: string;
  graph: ErdGraphResponse;
  visualization: ErdVisualization;
  filters: ErdFilters;
  selectedTableId: string | null;
  selectedRelationshipId: string | null;
  focusTableId: string | null;
  onFiltersChange: (filters: ErdFilters) => void;
  onSelectTable: (tableId: string | null) => void;
  onSelectRelationship: (relationshipId: string | null) => void;
  onFocusTable: (tableId: string | null) => void;
  onToggleExpanded: (tableId: string) => void;
};

function ErdWorkspaceInner({
  runId,
  graph,
  visualization,
  filters,
  selectedTableId,
  selectedRelationshipId,
  focusTableId,
  onFiltersChange,
  onSelectTable,
  onSelectRelationship,
  onFocusTable,
  onToggleExpanded,
}: ErdWorkspaceProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<ErdTableNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ErdRelationshipEdge>([]);
  const [layoutBusy, setLayoutBusy] = useState(false);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const initialLayoutDone = useRef(false);
  const nodesRef = useRef<ErdTableNode[]>([]);
  const edgesRef = useRef<ErdRelationshipEdge[]>([]);
  const { fitView } = useReactFlow<ErdTableNode, ErdRelationshipEdge>();
  const detailQuery = useRelationshipDetail(runId, selectedRelationshipId);

  const selectedTable = graph.tables.find((table) => table.id === selectedTableId);
  const selectedTableNode = visualization.nodes.find((node) => node.id === selectedTableId);

  const fit = useCallback(() => {
    void fitView({ padding: 0.16, duration: 280, maxZoom: 1.15 });
  }, [fitView]);

  const runLayout = useCallback(
    async (sourceNodes?: ErdTableNode[], sourceEdges?: ErdRelationshipEdge[]) => {
      const activeNodes = sourceNodes ?? nodesRef.current;
      const activeEdges = sourceEdges ?? edgesRef.current;
      if (activeNodes.length === 0) return;
      setLayoutBusy(true);
      setLayoutError(null);
      try {
        const layouted = await layoutErdGraph(activeNodes, activeEdges);
        nodesRef.current = layouted;
        setNodes(layouted);
      } catch {
        const fallback = fallbackGridLayout(activeNodes);
        nodesRef.current = fallback;
        setNodes(fallback);
        setLayoutError("Automatic layout failed; a safe grid layout is active.");
      } finally {
        setLayoutBusy(false);
        window.setTimeout(fit, 0);
      }
    },
    [fit, setNodes],
  );

  useEffect(() => {
    setNodes((current) => {
      const previous = new Map(current.map((node) => [node.id, node]));
      const merged = visualization.nodes.map((node) => ({
        ...node,
        position: previous.get(node.id)?.position ?? node.position,
        selected: node.id === selectedTableId,
      }));
      if (!initialLayoutDone.current && merged.length > 0) {
        initialLayoutDone.current = true;
        window.setTimeout(() => void runLayout(merged, visualization.edges), 0);
      }
      nodesRef.current = merged;
      return merged;
    });
    setEdges(visualization.edges);
    edgesRef.current = visualization.edges;
  }, [runLayout, selectedTableId, setEdges, setNodes, visualization]);

  const onNodeClick = useCallback<NodeMouseHandler<ErdTableNode>>(
    (_event, node) => {
      onSelectRelationship(null);
      onSelectTable(node.id);
    },
    [onSelectRelationship, onSelectTable],
  );
  const onEdgeClick = useCallback<EdgeMouseHandler<ErdRelationshipEdge>>(
    (_event, edge) => {
      onSelectTable(null);
      onSelectRelationship(edge.id);
    },
    [onSelectRelationship, onSelectTable],
  );
  const actions = useMemo(() => ({ toggleExpanded: onToggleExpanded }), [onToggleExpanded]);

  const emptyMessage =
    graph.relationships.length === 0
      ? "This completed run contains no inferred relationships."
      : focusTableId && !visualization.focusHasNeighbors
        ? "The focused table has no neighbors under the current filters."
        : "No relationships match the current ERD filters.";

  return (
    <div className="flex min-h-[calc(100vh-7.25rem)] flex-col overflow-hidden border border-border bg-surface">
      <ErdToolbar
        availableSchemas={[...graph.schemas]}
        edgeCount={visualization.edges.length}
        filters={filters}
        focusActive={Boolean(focusTableId)}
        layoutBusy={layoutBusy}
        nodeCount={visualization.nodes.length}
        onAutoLayout={() => void runLayout()}
        onChange={onFiltersChange}
        onExitFocus={() => onFocusTable(null)}
        onFitView={fit}
      />
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_22rem] max-xl:grid-cols-1">
        <div className="relative min-h-[34rem] bg-background" data-testid="erd-canvas">
          <ErdNodeActionsProvider value={actions}>
            <ReactFlow<ErdTableNode, ErdRelationshipEdge>
              colorMode="system"
              deleteKeyCode={null}
              edges={edges}
              edgeTypes={edgeTypes}
              elementsSelectable
              fitView={false}
              minZoom={0.12}
              nodeTypes={nodeTypes}
              nodes={nodes}
              nodesConnectable={false}
              nodesDraggable
              onEdgesChange={onEdgesChange}
              onEdgeClick={onEdgeClick}
              onNodesChange={onNodesChange}
              onNodeClick={onNodeClick}
              onlyRenderVisibleElements
            >
              <Background
                color="var(--rf-border)"
                gap={24}
                size={1}
                variant={BackgroundVariant.Dots}
              />
              <Controls
                className="!overflow-hidden !rounded-none !border !border-border !bg-surface !shadow-none [&_button]:!border-border [&_button]:!bg-surface [&_button]:!fill-text-muted hover:[&_button]:!bg-surface-elevated"
                showFitView={false}
                showInteractive={false}
              />
              {nodes.length >= 20 ? (
                <MiniMap
                  className="!border !border-border !bg-surface"
                  maskColor="color-mix(in srgb, var(--rf-background) 72%, transparent)"
                  nodeColor="var(--rf-text-muted)"
                  pannable
                  zoomable
                />
              ) : null}
            </ReactFlow>
          </ErdNodeActionsProvider>
          {visualization.nodes.length === 0 ? (
            <div className="absolute inset-0 z-10 bg-background/92">
              <EmptyGraph message={emptyMessage} />
            </div>
          ) : null}
          {focusTableId && !visualization.focusHasNeighbors && visualization.nodes.length > 0 ? (
            <div
              className="absolute bottom-3 left-1/2 z-20 -translate-x-1/2 border border-warning/50 bg-surface px-3 py-2 text-xs text-text-muted shadow"
              role="status"
            >
              Focused table has no neighbors under the current filters.
            </div>
          ) : null}
          {layoutBusy ? (
            <div
              className="absolute left-3 top-3 z-20 border border-border bg-surface px-3 py-2 font-mono text-[10px] text-text-muted shadow"
              role="status"
            >
              Calculating deterministic ELK layout…
            </div>
          ) : null}
          {layoutError ? (
            <div
              className="absolute bottom-3 left-3 z-20 flex items-center gap-2 border-l-2 border-warning bg-surface px-3 py-2 text-xs text-warning shadow"
              role="alert"
            >
              <AlertTriangle aria-hidden="true" className="size-4" /> {layoutError}
            </div>
          ) : null}
        </div>
        {selectedTable && selectedTableNode ? (
          <ErdTableInspector
            focused={focusTableId === selectedTable.id}
            incomingCount={selectedTableNode.data.incomingCount}
            onClose={() => onSelectTable(null)}
            onFocus={() => onFocusTable(selectedTable.id)}
            outgoingCount={selectedTableNode.data.outgoingCount}
            table={selectedTable}
          />
        ) : selectedRelationshipId ? (
          <RelationshipInspector
            detail={detailQuery.data}
            error={detailQuery.error}
            loading={detailQuery.isLoading}
            onClose={() => onSelectRelationship(null)}
          />
        ) : (
          <aside
            aria-label="ERD inspector"
            className="grid min-h-64 place-items-center border-l border-border bg-surface p-5 text-center max-xl:border-l-0 max-xl:border-t"
          >
            <div>
              <p className="text-sm font-medium text-text">Inspect the graph</p>
              <p className="mt-1 max-w-60 text-xs leading-5 text-text-muted">
                Select a table or relationship. All relationship facts remain available in the Phase
                4 table.
              </p>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

function EmptyGraph({ message }: { message: string }) {
  return (
    <div className="grid h-full min-h-[34rem] place-items-center p-6 text-center">
      <div>
        <Network aria-hidden="true" className="mx-auto size-7 text-text-muted" />
        <h2 className="mt-3 text-sm font-medium text-text">ERD has no visible relationships</h2>
        <p className="mt-1 text-xs text-text-muted">{message}</p>
      </div>
    </div>
  );
}
