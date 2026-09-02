import {
  ArrowLeft,
  Code2,
  Download,
  ExternalLink,
  FileCode2,
  FileSpreadsheet,
  Network,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { artifactUrl, type ArtifactMetadata } from "../../api/client";
import { toDisplayMessage } from "../../api/errors";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { useWorkspaceStore } from "../workspace/workspace-store";
import { DbmlCodeViewer } from "./dbml-code-viewer";
import { useArtifacts } from "./export-api";

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
  const selectedDbml = dbmlArtifacts.find((item) => item.id === selectedDbmlId) ?? dbmlArtifacts[0];

  return (
    <section className="mx-auto max-w-6xl px-5 py-6 lg:px-8" aria-labelledby="exports-title">
      <header className="flex flex-wrap items-end gap-3 border-b border-border pb-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
            Completed run / {runId.slice(0, 8)}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-text" id="exports-title">
            Artifacts & DBML
          </h1>
          <p className="mt-1.5 text-sm text-text-muted">
            Exact core-generated outputs - no Oracle connection required
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
              </option>
            ))}
          </select>
        </label>
      ) : null}

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
          <p>
            This DBML reflects the run-generated <b>{selectedDbml.scope ?? "configured"}</b> scope
            {selectedDbml.min_confidence != null ? (
              <>
                {" "}
                at minimum confidence <b>{selectedDbml.min_confidence}</b>
              </>
            ) : null}
            , not the current transient GUI filter.
          </p>
          {selectedDbml.rendered_relationships != null ? (
            <p className="mt-1">
              DBML references: {selectedDbml.rendered_relationships.toLocaleString()}
              {selectedDbml.unknown_cardinality_omitted != null ? (
                <>
                  {" "}
                  - Unknown-cardinality relationships omitted:{" "}
                  {selectedDbml.unknown_cardinality_omitted.toLocaleString()}
                </>
              ) : null}
            </p>
          ) : null}
          <p className="mt-2">
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
