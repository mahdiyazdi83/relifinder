import { ArrowLeft, DatabaseZap, Download, Network } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { RelationshipListItem } from "../../api/client";
import { toDisplayMessage } from "../../api/errors";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { useWorkspaceStore } from "../workspace/workspace-store";
import { RelationshipInspector } from "./relationship-inspector";
import {
  defaultRelationshipFilters,
  filterAndSortRelationships,
  type RelationshipFilters,
} from "./relationship-filters";
import { RelationshipTable } from "./relationship-table";
import { RelationshipToolbar } from "./relationship-toolbar";
import { useRelationshipDetail, useRelationships } from "./results-api";

const EMPTY_RELATIONSHIPS: RelationshipListItem[] = [];

export function ResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get("run");
  const selectedId = searchParams.get("rel");
  const [filters, setFilters] = useState<RelationshipFilters>(defaultRelationshipFilters);
  const [page, setPage] = useState(0);
  const relationshipsQuery = useRelationships(runId);
  const adoptCompletedRun = useWorkspaceStore((state) => state.adoptCompletedRun);
  const detailQuery = useRelationshipDetail(runId, selectedId);
  const all = relationshipsQuery.data?.relationships ?? EMPTY_RELATIONSHIPS;
  const filtered = useMemo(() => filterAndSortRelationships(all, filters), [all, filters]);

  useEffect(() => {
    if (runId && relationshipsQuery.data) adoptCompletedRun(runId);
  }, [adoptCompletedRun, relationshipsQuery.data, runId]);

  function changeFilters(next: RelationshipFilters) {
    setFilters(next);
    setPage(0);
  }

  function selectRelationship(relationshipId: string) {
    const next = new URLSearchParams(searchParams);
    next.set("rel", relationshipId);
    setSearchParams(next, { replace: true });
  }

  function closeInspector() {
    const next = new URLSearchParams(searchParams);
    next.delete("rel");
    setSearchParams(next, { replace: true });
  }

  if (!runId) {
    return (
      <ResultsState
        title="Completed run required"
        message="Open Results from a completed analysis run."
      />
    );
  }

  if (relationshipsQuery.isLoading) {
    return (
      <section className="mx-auto max-w-5xl px-5 py-8" aria-labelledby="results-loading-title">
        <h1 className="text-lg font-semibold text-text" id="results-loading-title">
          Relationship Explorer
        </h1>
        <p className="mt-3 flex items-center gap-2 text-sm text-text-muted" role="status">
          <ActivityIndicator /> Loading completed relationship results...
        </p>
      </section>
    );
  }

  if (relationshipsQuery.isError) {
    return (
      <ResultsState
        title="Results unavailable"
        message={toDisplayMessage(relationshipsQuery.error)}
      />
    );
  }

  const data = relationshipsQuery.data!;
  return (
    <section className="min-w-0 px-4 py-6 lg:px-7" aria-labelledby="results-title">
      <header className="flex flex-wrap items-end gap-4 border-b border-border pb-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
            Completed run / {runId.slice(0, 8)}
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-text" id="results-title">
            Relationship Explorer
          </h1>
        </div>
        <Link
          className="ml-auto inline-flex h-8 items-center gap-2 border border-accent px-3 text-xs font-medium text-accent hover:bg-accent/10"
          to={`/erd?run=${encodeURIComponent(runId)}`}
        >
          <Network aria-hidden="true" className="size-3.5" /> Open ERD
        </Link>
        <Link
          className="inline-flex h-8 items-center gap-2 border border-border px-3 text-xs font-medium text-text-muted hover:border-accent hover:text-text"
          to={`/exports?run=${encodeURIComponent(runId)}`}
        >
          <Download aria-hidden="true" className="size-3.5" /> Exports
        </Link>{" "}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-text-muted">
          <span>{data.summary.schemas_analyzed} schemas</span>
          <span>{data.summary.tables.toLocaleString()} tables</span>
          <span>{data.summary.columns.toLocaleString()} columns</span>
          <span>{data.total.toLocaleString()} relationships</span>
          <span>{data.summary.candidates_validated.toLocaleString()} validated</span>
          <span>mode: {data.summary.run_mode}</span>
        </div>
      </header>

      <div className="mt-4 overflow-hidden border border-border bg-surface">
        <RelationshipToolbar
          filters={filters}
          onChange={changeFilters}
          relationships={all}
          shown={filtered.length}
        />
        {all.length === 0 ? (
          <EmptyState
            message="No relationships met the report threshold."
            title="No relationships in this run"
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            message="Adjust or clear the active filters to see relationships."
            title="No relationships match the current filters."
          />
        ) : (
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_22rem] max-lg:grid-cols-1">
            <RelationshipTable
              filters={filters}
              onFiltersChange={changeFilters}
              onPageChange={setPage}
              onSelect={selectRelationship}
              page={page}
              relationships={filtered}
              selectedId={selectedId}
            />
            <RelationshipInspector
              detail={detailQuery.data}
              error={detailQuery.error}
              loading={detailQuery.isLoading}
              onClose={closeInspector}
            />
          </div>
        )}
      </div>
      <Link
        className="mt-4 inline-flex items-center gap-2 text-sm text-text-muted hover:text-text"
        to="/"
      >
        <ArrowLeft aria-hidden="true" className="size-4" /> Back to connection
      </Link>
    </section>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="grid min-h-64 place-items-center px-5 text-center">
      <div>
        <DatabaseZap aria-hidden="true" className="mx-auto size-6 text-text-muted" />
        <h2 className="mt-3 text-sm font-medium text-text">{title}</h2>
        <p className="mt-1 text-xs text-text-muted">{message}</p>
      </div>
    </div>
  );
}

function ResultsState({ title, message }: { title: string; message: string }) {
  return (
    <section className="mx-auto max-w-3xl px-5 py-10" aria-labelledby="results-state-title">
      <div className="border-l-2 border-warning bg-surface px-5 py-4">
        <h1 className="text-lg font-semibold text-text" id="results-state-title">
          {title}
        </h1>
        <p className="mt-2 text-sm leading-6 text-text-muted">{message}</p>
        <Link
          className="mt-4 inline-flex items-center gap-2 text-sm text-accent hover:underline"
          to="/"
        >
          <ArrowLeft aria-hidden="true" className="size-4" /> Back to connection
        </Link>
      </div>
    </section>
  );
}
