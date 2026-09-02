import { Ban, Check, Circle, CircleAlert, RotateCcw } from "lucide-react";

import type { RunStatusResponse } from "../../api/client";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { Button } from "../../components/ui/button";

const phases = [
  { state: "READING_METADATA", label: "Metadata" },
  { state: "BUILDING_CANDIDATES", label: "Candidate discovery" },
  { state: "VALIDATING_CANDIDATES", label: "Validation" },
  { state: "SCORING", label: "Scoring" },
  { state: "WRITING_ARTIFACTS", label: "Artifacts" },
] as const;
const order = phases.map((item) => item.state);
const terminal = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function AnalysisRunView({
  run,
  cancelling,
  onCancel,
  onRetry,
  onViewResults,
}: {
  run: RunStatusResponse;
  cancelling: boolean;
  onCancel: () => void;
  onRetry: () => void;
  onViewResults: () => void;
}) {
  const currentIndex = order.indexOf(run.state as (typeof order)[number]);

  if (run.state === "COMPLETED" && run.summary) {
    return (
      <section aria-labelledby="completed-title">
        <div className="flex items-center gap-2 text-success">
          <Check aria-hidden="true" className="size-5" />
          <h2 className="text-lg font-semibold" id="completed-title">
            Completed
          </h2>
        </div>
        <Summary summary={run.summary} />
        <div className="mt-5 flex justify-end">
          <Button onClick={onViewResults} type="button">
            View Results
          </Button>
        </div>
      </section>
    );
  }

  if (run.state === "FAILED") {
    const reconnect = run.error_code === "RECONNECT_REQUIRED";
    return (
      <section aria-labelledby="failed-title">
        <div className="flex items-center gap-2 text-danger">
          <CircleAlert aria-hidden="true" className="size-5" />
          <h2 className="text-lg font-semibold" id="failed-title">
            Analysis failed
          </h2>
        </div>
        <p className="mt-3 border-l-2 border-danger bg-danger/8 px-4 py-3 text-sm text-danger">
          {run.message}
        </p>
        <div className="mt-5 flex gap-2">
          {reconnect ? (
            <Button onClick={() => (window.location.href = "/")} type="button">
              Reconnect
            </Button>
          ) : (
            <Button onClick={onRetry} type="button">
              <RotateCcw aria-hidden="true" className="size-4" /> Retry
            </Button>
          )}
        </div>
      </section>
    );
  }

  if (run.state === "CANCELLED") {
    return (
      <section aria-labelledby="cancelled-title">
        <div className="flex items-center gap-2 text-warning">
          <Ban aria-hidden="true" className="size-5" />
          <h2 className="text-lg font-semibold" id="cancelled-title">
            Analysis cancelled
          </h2>
        </div>
        <p className="mt-2 text-sm text-text-muted">
          Incomplete artifacts are not exposed as valid results.
        </p>
        <Button className="mt-5" onClick={onRetry} type="button" variant="ghost">
          Configure another run
        </Button>
      </section>
    );
  }

  return (
    <section aria-labelledby="run-title">
      <div className="flex flex-wrap items-center gap-3 border-b border-border pb-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-text-muted">
            Run {run.run_id.slice(0, 8)}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-text" id="run-title">
            Analysis Run
          </h2>
        </div>
        {!terminal.has(run.state) ? (
          <Button
            className="ml-auto text-danger"
            disabled={cancelling || run.state === "CANCEL_REQUESTED"}
            onClick={onCancel}
            type="button"
            variant="ghost"
          >
            <Ban aria-hidden="true" className="size-4" />
            {run.state === "CANCEL_REQUESTED" ? "Cancellation requested" : "Cancel"}
          </Button>
        ) : null}
      </div>

      <div className="relative mt-5 h-1 overflow-hidden bg-surface-elevated" aria-hidden="true">
        <span className="rf-scan-line absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent" />
      </div>
      <ol className="mt-3 space-y-1">
        {phases.map((phase, index) => {
          const complete =
            currentIndex > index ||
            run.state === "COMPLETED" ||
            (run.state === "CANCEL_REQUESTED" && index < currentIndex);
          const active = currentIndex === index;
          return (
            <li
              className="grid grid-cols-[1.5rem_1fr] gap-3 border-b border-border/70 py-3"
              key={phase.state}
            >
              <span className="pt-0.5">
                {complete ? (
                  <Check aria-hidden="true" className="size-4 text-success" />
                ) : active ? (
                  <ActivityIndicator label={`${phase.label} in progress`} />
                ) : (
                  <Circle aria-hidden="true" className="size-4 text-text-muted" />
                )}
              </span>
              <div>
                <p className={`text-sm font-medium ${active ? "text-text" : "text-text-muted"}`}>
                  {phase.label}
                </p>
                {active ? (
                  <p className="mt-1 text-xs text-text-muted">
                    {run.message}
                    {run.current != null && run.total != null
                      ? ` · ${run.current.toLocaleString()} / ${run.total.toLocaleString()}`
                      : ""}
                  </p>
                ) : null}
                {phase.state === "READING_METADATA" && complete && run.stats?.schemas != null ? (
                  <p className="mt-1 text-xs text-text-muted">
                    {run.stats.schemas} schemas · {run.stats.tables ?? 0} tables ·{" "}
                    {run.stats.columns ?? 0} columns
                  </p>
                ) : null}
                {phase.state === "BUILDING_CANDIDATES" &&
                complete &&
                run.stats?.candidates_generated != null ? (
                  <p className="mt-1 text-xs text-text-muted">
                    {run.stats.candidates_generated.toLocaleString()} qualified candidates
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Summary({ summary }: { summary: NonNullable<RunStatusResponse["summary"]> }) {
  const rows = [
    ["Schemas analyzed", summary.schemas_analyzed],
    ["Tables", summary.tables],
    ["Columns", summary.columns],
    ["Candidates generated", summary.candidates_generated],
    ["Candidates validated", summary.candidates_validated],
    ["Candidates skipped", summary.candidates_skipped],
    ["Relationships in report", summary.relationships_in_report],
    ["Run mode", summary.run_mode],
    ["Elapsed time", `${summary.elapsed_seconds.toFixed(2)} s`],
  ];
  return (
    <dl className="mt-5 divide-y divide-border border-y border-border">
      {rows.map(([label, value]) => (
        <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-2.5 text-sm" key={label}>
          <dt className="text-text-muted">{label}</dt>
          <dd className="font-mono text-text">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
