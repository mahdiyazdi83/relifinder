import {
  Check,
  CircleDot,
  Code2,
  Database,
  Grid3X3,
  LockKeyhole,
  Network,
  ScanSearch,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { cn } from "../../lib/utils";
import { useWorkspaceStore } from "./workspace-store";
import { workflowHref, workflowStageState, type WorkflowStageId } from "./workflow";

const stages = [
  { id: "connection", label: "Connection", icon: Database },
  { id: "schemas", label: "Schemas", icon: Grid3X3 },
  { id: "analysis", label: "Analyze", icon: ScanSearch },
  { id: "results", label: "Results", icon: CircleDot },
  { id: "erd", label: "ERD", icon: Network },
  { id: "exports", label: "Export", icon: Code2 },
] satisfies { id: WorkflowStageId; label: string; icon: typeof Database }[];

export function WorkspaceRail() {
  const location = useLocation();
  const connection = useWorkspaceStore((state) => state.connection);
  const selectedSchemas = useWorkspaceStore((state) => state.selectedSchemas);
  const run = useWorkspaceStore((state) => state.run);
  const snapshot = {
    connection,
    selectedSchemaCount: selectedSchemas.length,
    run,
    pathname: location.pathname,
  };

  return (
    <aside
      className="flex min-h-0 flex-col border-r border-border bg-surface/95"
      aria-label="Workflow navigation"
    >
      <div className="border-b border-border px-3 py-3 max-lg:px-2">
        <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-text-muted max-lg:sr-only">
          Workflow
        </p>
        <p className="mt-1 text-xs font-medium text-text max-lg:sr-only">Discovery pipeline</p>
      </div>
      <nav className="relative p-2" aria-label="ReliFinder workflow">
        <div
          className="absolute bottom-5 left-[1.55rem] top-5 w-px bg-border max-lg:left-1/2"
          aria-hidden="true"
        />
        <ol className="relative space-y-1">
          {stages.map((stage, index) => {
            const state = workflowStageState(stage.id, snapshot);
            const Icon = stage.icon;
            const inner = (
              <>
                <span
                  className={cn(
                    "relative z-10 grid size-7 shrink-0 place-items-center border bg-surface",
                    state === "current"
                      ? "border-accent text-accent shadow-[0_0_18px_var(--rf-accent-glow)]"
                      : state === "complete"
                        ? "border-success text-success"
                        : "border-border text-text-muted",
                  )}
                >
                  {state === "complete" ? (
                    <Check aria-hidden="true" className="size-3.5" />
                  ) : state === "locked" ? (
                    <LockKeyhole aria-hidden="true" className="size-3" />
                  ) : (
                    <Icon aria-hidden="true" className="size-3.5" />
                  )}
                </span>
                <span className="min-w-0 max-lg:sr-only">
                  <span className="block font-mono text-[9px] uppercase tracking-wider text-text-muted">
                    0{index + 1}
                  </span>
                  <span className="block truncate text-xs font-medium">{stage.label}</span>
                </span>
              </>
            );
            const className = cn(
              "flex min-h-11 items-center gap-2.5 px-2 text-left transition-colors max-lg:justify-center max-lg:px-0",
              state === "current"
                ? "bg-accent/8 text-text"
                : state === "locked"
                  ? "cursor-not-allowed text-text-muted opacity-55"
                  : "text-text-muted hover:bg-surface-elevated hover:text-text",
            );
            return (
              <li key={stage.id}>
                {state === "locked" ? (
                  <span
                    aria-disabled="true"
                    className={className}
                    title={`${stage.label} is not available yet`}
                  >
                    {inner}
                  </span>
                ) : (
                  <Link
                    aria-current={state === "current" ? "step" : undefined}
                    className={className}
                    to={workflowHref(stage.id, run?.runId)}
                  >
                    {inner}
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      </nav>
      <WorkspaceContext />
    </aside>
  );
}

function WorkspaceContext() {
  const connection = useWorkspaceStore((state) => state.connection);
  const schemas = useWorkspaceStore((state) => state.selectedSchemas);
  const run = useWorkspaceStore((state) => state.run);
  return (
    <div className="mt-auto border-t border-border p-3 max-lg:p-2" aria-label="Workspace context">
      <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-text-muted max-lg:sr-only">
        Live context
      </p>
      <div className="mt-2 space-y-2 max-lg:mt-0">
        <ContextDot
          active={Boolean(connection)}
          label={connection ? `${connection.username}@${connection.serviceName}` : "Offline"}
        />
        <ContextDot
          active={schemas.length > 0}
          label={
            schemas.length
              ? `${schemas.length} schema${schemas.length === 1 ? "" : "s"}`
              : "No scope"
          }
        />
        <ContextDot
          active={Boolean(run)}
          label={run ? `${run.runId.slice(0, 8)} · ${run.state}` : "No run"}
        />
      </div>
    </div>
  );
}

function ContextDot({ active, label }: { active: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2" title={label}>
      <span
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          active ? "bg-accent shadow-[0_0_8px_var(--rf-accent-glow)]" : "bg-text-muted/40",
        )}
      />
      <span className="truncate font-mono text-[9px] text-text-muted max-lg:sr-only">{label}</span>
    </div>
  );
}
