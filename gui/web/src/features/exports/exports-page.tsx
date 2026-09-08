import {
  ArrowLeft,
  Code2,
  Download,
  ExternalLink,
  FileCode2,
  FileSpreadsheet,
  Network,
  RefreshCw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { artifactUrl, type ArtifactMetadata } from "../../api/client";
import { toDisplayMessage } from "../../api/errors";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { useWorkspaceStore } from "../workspace/workspace-store";
import { DbmlCodeViewer } from "./dbml-code-viewer";
import { useArtifacts, useRegenerateDbml } from "./export-api";

export function ExportsPage() {
  const [searchParams] = useSearchParams();
  const runId = searchParams.get("run");
  const artifactsQuery = useArtifacts(runId);
  const adoptCompletedRun = useWorkspaceStore((state) => state.adoptCompletedRun);
  const dbmlArtifacts = useMemo(
    () => artifactsQuery.data?.artifacts.filter((artifact) => artifact.type === "dbml") ?? [],
    [artifactsQuery.data],
  );
  const [selectedDbmlId, setSelectedDbmlId] = useState<string | null>(null);
  const selectedDbml = dbmlArtifacts.find((item) => item.id === selectedDbmlId) ?? dbmlArtifacts[0];
  const [regenerationThreshold, setRegenerationThreshold] = useState<number | null>(null);
  const effectiveRegenerationThreshold =
    regenerationThreshold ?? selectedDbml?.min_confidence ?? null;
  const regeneration = useRegenerateDbml(runId);

  useEffect(() => {
    if (runId && artifactsQuery.data) adoptCompletedRun(runId);
  }, [adoptCompletedRun, artifactsQuery.data, runId]);

  if (!runId) {
    return (
      <ExportState title="Completed run required" message="Open Exports from Results or ERD." />
    );
  }
  if (artifactsQuery.isLoading) {
    return (
      <ExportState loading title="Run artifacts" message="Checking completed-run artifacts..." />
    );
  }
  if (artifactsQuery.isError) {
    return (
      <ExportState title="Exports unavailable" message={toDisplayMessage(artifactsQuery.error)} />
    );
  }

  const artifacts = artifactsQuery.data!.artifacts;
  return (
    <section className="mx-auto max-w-6xl px-5 py-6 lg:px-8" aria-labelledby="exports-title">
      <header className="flex flex-wrap items-end gap-3 border-b border-border pb-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
            Completed run / {runId.slice(0, 8)} · {artifactsQuery.data!.database_type}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-text" id="exports-title">
            Artifacts & DBML
          </h1>
          <p className="mt-1.5 text-sm text-text-muted">
            Exact core-generated outputs - no database connection required
          </p>
        </div>
        <div className="ml-auto flex items-center border border-border text-xs">
          <Link
            className="inline-flex h-8 items-center gap-2 px-3 text-text-muted hover:text-text"
            to={`/erd?run=${encodeURIComponent(runId)}`}
          >
            <Network aria-hidden="true" className="size-3.5" /> Diagram
          </Link>
          <span className="inline-flex h-8 items-center gap-2 border-l border-border bg-surface-elevated px-3 text-accent">
            <Code2 aria-hidden="true" className="size-3.5" /> DBML Code
          </span>
        </div>
      </header>

      <section className="mt-5 border border-border bg-surface" aria-labelledby="artifacts-title">
        <h2
          className="border-b border-border px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-muted"
          id="artifacts-title"
        >
          Artifacts
        </h2>
        <div className="divide-y divide-border">
          {artifacts
            .filter((artifact) => artifact.type !== "dbml")
            .map((artifact) => (
              <ArtifactRow artifact={artifact} key={artifact.id} runId={runId} />
            ))}
          {dbmlArtifacts.map((artifact) => (
            <ArtifactRow artifact={artifact} key={artifact.id} runId={runId} />
          ))}
        </div>
      </section>

      {dbmlArtifacts.length > 1 ? (
        <label className="mt-4 block text-xs text-text-muted">
          DBML artifact
          <select
            className="ml-2 border border-border bg-surface px-2 py-1.5 text-text"
            onChange={(event) => setSelectedDbmlId(event.target.value)}
            value={selectedDbml?.id}
          >
            {dbmlArtifacts.map((artifact) => (
              <option key={artifact.id} value={artifact.id}>
                {artifact.filename}
                {artifact.min_confidence != null
                  ? ` · confidence ≥ ${artifact.min_confidence}`
                  : ""}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <section
        aria-labelledby="dbml-regeneration-title"
        className="mt-4 flex flex-wrap items-end gap-3 border border-border bg-surface px-4 py-3"
      >
        <div>
          <h2
            className="text-xs font-semibold uppercase tracking-wider text-text-muted"
            id="dbml-regeneration-title"
          >
            Regenerate from completed-run artifacts
          </h2>
          <p className="mt-1 text-[11px] text-text-muted">
            Offline and deterministic · preserves the run scope and safe cardinality rules
          </p>
        </div>
        <label className="ml-auto text-xs text-text-muted">
          Minimum confidence
          <input
            aria-label="DBML minimum confidence"
            className="ml-2 h-8 w-20 border border-border bg-background px-2 text-right font-mono text-text"
            max={100}
            min={0}
            onChange={(event) => setRegenerationThreshold(Number(event.target.value))}
            type="number"
            value={effectiveRegenerationThreshold ?? ""}
          />
        </label>
        <button
          className="inline-flex h-8 items-center gap-2 border border-accent px-3 text-xs text-accent hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={
            regeneration.isPending ||
            effectiveRegenerationThreshold == null ||
            effectiveRegenerationThreshold < 0 ||
            effectiveRegenerationThreshold > 100
          }
          onClick={() => {
            if (effectiveRegenerationThreshold == null) return;
            regeneration.mutate(effectiveRegenerationThreshold, {
              onSuccess: (response) =>
                setSelectedDbmlId(response.generated_artifact_ids[0] ?? null),
            });
          }}
          type="button"
        >
          <RefreshCw
            aria-hidden="true"
            className={`size-3.5 ${regeneration.isPending ? "animate-spin" : ""}`}
          />
          {regeneration.isPending ? "Regenerating…" : "Regenerate DBML"}
        </button>
        {regeneration.isError ? (
          <p className="basis-full text-xs text-danger" role="alert">
            {toDisplayMessage(regeneration.error)}
          </p>
        ) : null}
      </section>

      <div className="mt-4">
        {selectedDbml ? (
          <DbmlCodeViewer artifact={selectedDbml} runId={runId} />
        ) : (
          <ExportState
            title="DBML unavailable"
            message="No DBML artifact is associated with this completed run."
          />
        )}
      </div>

      {selectedDbml?.available ? (
        <aside className="mt-4 border-l-2 border-warning bg-warning/8 px-4 py-3 text-xs leading-5 text-text-muted">
          <DbmlDiagnostics artifact={selectedDbml} />
          <p className="mt-3">
            External service privacy: ReliFinder never uploads DBML automatically. Copy it, then
            explicitly open dbdiagram and import it yourself.
          </p>
          <a
            className="mt-2 inline-flex items-center gap-2 text-accent hover:underline"
            href="https://dbdiagram.io/"
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink aria-hidden="true" className="size-3.5" /> Open dbdiagram
          </a>
        </aside>
      ) : null}
      <Link
        className="mt-4 inline-flex items-center gap-2 text-sm text-text-muted hover:text-text"
        to={`/results?run=${encodeURIComponent(runId)}`}
      >
        <ArrowLeft aria-hidden="true" className="size-4" /> Back to Results
      </Link>
    </section>
  );
}

function DbmlDiagnostics({ artifact }: { artifact: ArtifactMetadata }) {
  const empty = artifact.rendered_relationships === 0;
  const noEligible = artifact.eligible_relationships === 0;
  const diagnostics = [
    ["Export threshold", artifact.min_confidence],
    ["Highest detected confidence", artifact.highest_detected_confidence],
    ["Eligible after filters / limit", artifact.eligible_relationships],
    ["Below threshold", artifact.below_confidence_threshold],
    ["Validation-status filter omitted", artifact.omitted_by_validation_filter],
    ["Scope filter omitted", artifact.omitted_by_scope_filter],
    ["Generic filter omitted", artifact.omitted_by_generic_filter],
    ["Max-relations limit omitted", artifact.omitted_by_limit],
    ["Unknown cardinality omitted", artifact.unknown_cardinality_omitted],
    ["Rendered DBML references", artifact.rendered_relationships],
  ] as const;

  return (
    <div>
      {empty ? (
        <div className="mb-3 border border-warning/40 bg-background/50 px-3 py-2">
          <p className="font-medium text-text">
            {noEligible
              ? "No relationships qualified for this DBML export."
              : "No relationships could be represented safely in this DBML export."}
          </p>
          <p className="mt-1">
            {noEligible
              ? "The export filters excluded every detected relationship. Compare the threshold with the highest detected confidence below."
              : "Eligible relationships were retained as evidence comments, but unknown cardinality was omitted because DBML has no neutral relationship operator."}
          </p>
        </div>
      ) : null}
      <p>
        This DBML reflects the run-generated <b>{artifact.scope ?? "configured"}</b> scope, not the
        current transient GUI filter.
      </p>
      <dl className="mt-2 grid gap-x-5 gap-y-1 sm:grid-cols-2">
        {diagnostics.map(([label, value]) =>
          value == null ? null : (
            <div className="flex justify-between gap-3 border-b border-border/60 py-1" key={label}>
              <dt>{label}</dt>
              <dd className="font-mono text-text">{value.toLocaleString()}</dd>
            </div>
          ),
        )}
      </dl>
    </div>
  );
}
function ArtifactRow({ artifact, runId }: { artifact: ArtifactMetadata; runId: string }) {
  const Icon = artifact.type === "csv" ? FileSpreadsheet : FileCode2;
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3">
      <Icon aria-hidden="true" className="size-4 text-accent" />
      <div className="min-w-48 flex-1">
        <p className="text-sm font-medium text-text">
          {artifact.type === "csv"
            ? "Relationships CSV"
            : artifact.type === "html"
              ? "Analysis HTML Report"
              : "DBML ERD"}
        </p>
        <p className="font-mono text-[10px] text-text-muted">
          {artifact.filename}
          {artifact.size_bytes != null ? ` - ${artifact.size_bytes.toLocaleString()} bytes` : ""}
        </p>
      </div>
      {!artifact.available ? (
        <span className="text-xs text-warning">Not generated or invalid</span>
      ) : artifact.type === "html" ? (
        <div className="flex gap-2">
          <a
            className="inline-flex h-8 items-center gap-2 border border-border px-3 text-xs text-text hover:border-accent"
            href={artifactUrl(runId, artifact.id)}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink aria-hidden="true" className="size-3.5" /> Open Report
          </a>
          <DownloadLink artifact={artifact} runId={runId} label="Download HTML" />
        </div>
      ) : (
        <DownloadLink
          artifact={artifact}
          runId={runId}
          label={artifact.type === "csv" ? "Download CSV" : "Download DBML"}
        />
      )}
    </div>
  );
}

function DownloadLink({
  artifact,
  runId,
  label,
}: {
  artifact: ArtifactMetadata;
  runId: string;
  label: string;
}) {
  return (
    <a
      className="inline-flex h-8 items-center gap-2 border border-accent px-3 text-xs text-accent hover:bg-accent/10"
      download={artifact.filename}
      href={artifactUrl(runId, artifact.id, true)}
    >
      <Download aria-hidden="true" className="size-3.5" /> {label}
    </a>
  );
}

function ExportState({
  title,
  message,
  loading = false,
}: {
  title: string;
  message: string;
  loading?: boolean;
}) {
  return (
    <section className="mx-auto max-w-3xl px-5 py-10">
      <div className="border-l-2 border-warning bg-surface px-5 py-4">
        <h1 className="text-lg font-semibold text-text">{title}</h1>
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
