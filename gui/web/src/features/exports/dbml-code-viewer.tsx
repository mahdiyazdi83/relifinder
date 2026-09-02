import { Check, Clipboard, Download } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import { artifactUrl, type ArtifactMetadata } from "../../api/client";
import { toDisplayMessage } from "../../api/errors";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { useDbmlText } from "./export-api";

export function DbmlCodeViewer({ artifact, runId }: { artifact: ArtifactMetadata; runId: string }) {
  const dbmlQuery = useDbmlText(runId, artifact.id, artifact.available);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (copyState === "idle") return;
    const timer = window.setTimeout(() => setCopyState("idle"), 2200);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  async function copyDbml() {
    if (!dbmlQuery.data) return;
    try {
      await navigator.clipboard.writeText(dbmlQuery.data);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  if (!artifact.available) {
    return <DbmlState message="DBML was not generated as a valid completed-run artifact." />;
  }
  if (dbmlQuery.isLoading) return <DbmlState loading message="Loading DBML code..." />;
  if (dbmlQuery.isError) return <DbmlState error message={toDisplayMessage(dbmlQuery.error)} />;
  if (!dbmlQuery.data) {
    return <DbmlState message="The generated DBML is empty. Download is disabled." />;
  }

  return (
    <section
      className="overflow-hidden border border-border bg-surface"
      aria-labelledby="dbml-code-title"
    >
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text" id="dbml-code-title">
            DBML Code
          </h2>
          <p className="mt-1 font-mono text-[10px] text-text-muted">
            {artifact.filename} - {formatBytes(artifact.size_bytes)}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            className="inline-flex h-8 items-center gap-2 border border-border px-3 text-xs text-text hover:border-accent"
            onClick={copyDbml}
            type="button"
          >
            {copyState === "copied" ? (
              <Check aria-hidden="true" className="size-3.5 text-success" />
            ) : (
              <Clipboard aria-hidden="true" className="size-3.5" />
            )}
            {copyState === "copied" ? "Copied" : "Copy"}
          </button>
          <a
            className="inline-flex h-8 items-center gap-2 border border-accent px-3 text-xs text-accent hover:bg-accent/10"
            download={artifact.filename}
            href={artifactUrl(runId, artifact.id, true)}
          >
            <Download aria-hidden="true" className="size-3.5" /> Download DBML
          </a>
        </div>
        {copyState === "failed" ? (
          <p className="w-full text-xs text-danger" role="alert">
            Clipboard access failed. Select the code manually or download the file.
          </p>
        ) : null}
        {copyState === "copied" ? (
          <span className="sr-only" role="status">
            Copied
          </span>
        ) : null}
      </header>
      <pre
        className="max-h-[32rem] overflow-auto bg-background p-4 font-mono text-xs leading-5 text-text"
        tabIndex={0}
      >
        <code>
          {dbmlQuery.data.split("\n").map((line, index) => (
            <HighlightedLine key={index} line={line} />
          ))}
        </code>
      </pre>
    </section>
  );
}

function HighlightedLine({ line }: { line: string }) {
  if (line.trimStart().startsWith("//")) {
    return <span className="block text-text-muted">{line || " "}</span>;
  }
  const tokens = line.split(
    /(\b(?:Table|Ref|Project|Note|indexes|pk|unique|not|null)\b|'[^']*'|\b\d+(?:\.\d+)?\b)/g,
  );
  return (
    <span className="block">
      {tokens.map((token, index) => {
        const className = /^(Table|Ref|Project|Note|indexes)$/.test(token)
          ? "text-accent"
          : /^'.*'$/.test(token)
            ? "text-success"
            : /^(pk|unique|not|null)$/.test(token)
              ? "text-warning"
              : /^\d/.test(token)
                ? "text-warning"
                : "";
        return (
          <Fragment key={index}>
            <span className={className}>{token}</span>
          </Fragment>
        );
      })}{" "}
    </span>
  );
}

function DbmlState({
  message,
  error = false,
  loading = false,
}: {
  message: string;
  error?: boolean;
  loading?: boolean;
}) {
  return (
    <div
      className="border-l-2 border-warning bg-surface px-4 py-4 text-sm text-text-muted"
      role={error ? "alert" : "status"}
    >
      <span className="inline-flex items-center gap-2">
        {loading ? <ActivityIndicator /> : null}
        {message}
      </span>
    </div>
  );
}

function formatBytes(size: number | null | undefined) {
  if (size == null) return "size unavailable";
  if (size < 1024) return `${size} B`;
  return `${(size / 1024).toFixed(1)} KB`;
}
