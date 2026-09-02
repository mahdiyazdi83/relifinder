import "@xyflow/react/dist/style.css";

import { ArrowLeft, Code2, Network } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { toDisplayMessage } from "../../api/errors";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { useWorkspaceStore } from "../workspace/workspace-store";
import { buildErdVisualization } from "./erd-adapter";
import { useErdGraph } from "./erd-api";
import type { ErdFilters } from "./erd-types";
import { ErdWorkspace } from "./erd-workspace";

export function ErdPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get("run");
  const selectedTableId = searchParams.get("table");
  const selectedRelationshipId = searchParams.get("rel");
  const focusTableId = searchParams.get("focus");
  const graphQuery = useErdGraph(runId);
  const adoptCompletedRun = useWorkspaceStore((state) => state.adoptCompletedRun);
  const [filters, setFilters] = useState<ErdFilters | null>(null);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (runId && graphQuery.data) adoptCompletedRun(runId);
  }, [adoptCompletedRun, graphQuery.data, runId]);

  const effectiveFilters = useMemo<ErdFilters | null>(
    () =>
      filters ??
      (graphQuery.data
        ? {
            minConfidence: graphQuery.data.default_min_confidence,
            schemas: [...graphQuery.data.schemas],
            validationStatus: "",
            crossSchemaOnly: false,
          }
        : null),
    [filters, graphQuery.data],
  );

  const visualization = useMemo(
    () =>
      graphQuery.data && effectiveFilters
        ? buildErdVisualization(
            graphQuery.data,
            effectiveFilters,
            expandedTables,
            focusTableId,
            selectedTableId,
            selectedRelationshipId,
          )
        : null,
    [
      expandedTables,
      effectiveFilters,
      focusTableId,
      graphQuery.data,
      selectedRelationshipId,
      selectedTableId,
    ],
  );

  const updateUrlSelection = useCallback(
    (key: "table" | "rel" | "focus", value: string | null) => {
      const next = new URLSearchParams(searchParams);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key === "table" && value) next.delete("rel");
      if (key === "rel" && value) next.delete("table");
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const toggleExpanded = useCallback((tableId: string) => {
    setExpandedTables((current) => {
      const next = new Set(current);
      if (next.has(tableId)) next.delete(tableId);
      else next.add(tableId);
      return next;
    });
  }, []);

  if (!runId) {
    return <ErdState title="Completed run required" message="Open ERD from completed results." />;
  }
  if (graphQuery.isError) {
    return <ErdState title="ERD unavailable" message={toDisplayMessage(graphQuery.error)} />;
  }
  if (graphQuery.isLoading || !effectiveFilters || !visualization) {
    return (
      <ErdState loading title="Interactive ERD" message="Loading safe completed-run metadata..." />
    );
  }

  return (
    <section
      className="flex min-h-[calc(100vh-3rem)] flex-col px-3 py-3"
      aria-labelledby="erd-title"
    >
      <header className="mb-3 flex flex-wrap items-end gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">
            Completed run / {runId.slice(0, 8)}
          </p>
          <h1
            className="mt-1 flex items-center gap-2 text-xl font-semibold text-text"
            id="erd-title"
          >
            <Network aria-hidden="true" className="size-5 text-accent" /> Interactive ERD
          </h1>
        </div>
        <Link
          className="ml-auto inline-flex h-8 items-center gap-2 border border-accent px-3 text-xs text-accent hover:bg-accent/10"
          to={`/exports?run=${encodeURIComponent(runId)}`}
        >
          <Code2 aria-hidden="true" className="size-3.5" /> DBML & Exports
        </Link>{" "}
        <p className="max-w-xl text-right text-xs leading-5 text-text-muted">
          Artifact-backed visualization · zero additional Oracle queries · internal unknown
          cardinalities remain visible
        </p>
      </header>
      <ErdWorkspace
        filters={effectiveFilters}
        focusTableId={focusTableId}
        graph={graphQuery.data!}
        onFiltersChange={setFilters}
        onFocusTable={(id) => updateUrlSelection("focus", id)}
        onSelectRelationship={(id) => updateUrlSelection("rel", id)}
        onSelectTable={(id) => updateUrlSelection("table", id)}
        onToggleExpanded={toggleExpanded}
        runId={runId}
        selectedRelationshipId={selectedRelationshipId}
        selectedTableId={selectedTableId}
        visualization={visualization}
      />
      <Link
        className="mt-3 inline-flex w-fit items-center gap-2 text-sm text-text-muted hover:text-text"
        to={`/results?run=${encodeURIComponent(runId)}`}
      >
        <ArrowLeft aria-hidden="true" className="size-4" /> Back to relationship table
      </Link>
    </section>
  );
}

function ErdState({
  title,
  message,
  loading = false,
}: {
  title: string;
  message: string;
  loading?: boolean;
}) {
  return (
    <section className="mx-auto max-w-3xl px-5 py-10" aria-labelledby="erd-state-title">
      <div className="border-l-2 border-warning bg-surface px-5 py-4">
        <h1 className="text-lg font-semibold text-text" id="erd-state-title">
          {title}
        </h1>
        <p
          className="mt-2 flex items-center gap-2 text-sm text-text-muted"
          role={loading ? "status" : undefined}
        >
          {loading ? <ActivityIndicator /> : null}
          {message}
        </p>
        {!loading ? (
          <Link className="mt-4 inline-flex text-sm text-accent hover:underline" to="/">
            Back to connection
          </Link>
        ) : null}
      </div>
    </section>
  );
}
