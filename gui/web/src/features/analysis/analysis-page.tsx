import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CircleAlert } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import type { AnalysisConfiguration, RunStatusResponse } from "../../api/client";
import { ApiRequestError, toDisplayMessage } from "../../api/errors";
import { AnalysisConfigurationForm } from "./analysis-configuration-form";
import { AnalysisRunView } from "./analysis-run-view";
import { useCancelRun, useCreateRun, useRunStatus } from "./run-api";
import { useRunEvents } from "./use-run-events";

export function AnalysisPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const connectionId =
    typeof location.state?.connectionId === "string" ? location.state.connectionId : null;
  const schemas = Array.isArray(location.state?.schemas)
    ? location.state.schemas.filter((value: unknown): value is string => typeof value === "string")
    : [];
  const [runId, setRunId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [reconnectRequired, setReconnectRequired] = useState(false);
  const createMutation = useCreateRun();
  const cancelMutation = useCancelRun();
  const statusQuery = useRunStatus(runId);
  useRunEvents(runId);

  if (!connectionId || schemas.length === 0) {
    return (
      <section className="mx-auto max-w-3xl px-5 py-10" aria-labelledby="analysis-required-title">
        <div className="border-l-2 border-warning bg-surface px-5 py-4">
          <CircleAlert aria-hidden="true" className="size-5 text-warning" />
          <h1 className="mt-3 text-lg font-semibold text-text" id="analysis-required-title">
            Reconnect and select schemas
          </h1>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            Analysis configuration requires an active runtime Oracle session and at least one
            selected schema.
          </p>
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

  async function start(configuration: AnalysisConfiguration) {
    setStartError(null);
    setReconnectRequired(false);
    try {
      const response = await createMutation.mutateAsync({
        connection_id: connectionId!,
        schemas,
        configuration,
      });
      const queued: RunStatusResponse = {
        sequence: 0,
        run_id: response.run_id,
        state: response.status,
        message: "Analysis is queued",
        stats: {},
        connection_id: connectionId!,
        selected_schemas: schemas,
      };
      queryClient.setQueryData(["run", response.run_id], queued);
      setRunId(response.run_id);
    } catch (error) {
      setStartError(toDisplayMessage(error));
      setReconnectRequired(
        error instanceof ApiRequestError && error.code === "CONNECTION_SESSION_NOT_FOUND",
      );
    } finally {
      createMutation.reset();
    }
  }

  const run = runId ? statusQuery.data : null;

  return (
    <section className="mx-auto max-w-4xl px-5 py-6 lg:px-8" aria-labelledby="analysis-title">
      <div className="border-b border-border pb-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
          Local workflow / Phase 3
        </p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-text" id="analysis-title">
          {runId ? "Analysis workflow" : "Analysis Configuration"}
        </h1>
        <p className="mt-1.5 text-sm leading-6 text-text-muted">
          {runId
            ? "Live state comes from real core boundaries; numeric progress appears only when known."
            : "Choose a workload profile, review thresholds, and start a local background run."}
        </p>
      </div>

      <div className="mt-5 border border-border bg-surface p-5">
        {!runId ? (
          <>
            {reconnectRequired ? (
              <div className="mb-5 border-l-2 border-warning bg-warning/8 px-4 py-3 text-sm text-warning">
                The runtime session expired. Return to Connection and reconnect before retrying.
              </div>
            ) : null}
            <AnalysisConfigurationForm
              errorMessage={startError}
              onSubmit={start}
              selectedSchemas={schemas}
              submitting={createMutation.isPending}
            />
          </>
        ) : run ? (
          <AnalysisRunView
            cancelling={cancelMutation.isPending}
            onCancel={() => {
              cancelMutation.mutate(runId, {
                onSuccess: (response) => {
                  queryClient.setQueryData<RunStatusResponse>(["run", runId], (current) =>
                    current
                      ? {
                          ...current,
                          state: response.status,
                          message:
                            "Cancellation requested; waiting for the current bounded operation",
                        }
                      : current,
                  );
                },
              });
            }}
            onRetry={() => {
              queryClient.removeQueries({ queryKey: ["run", runId] });
              setRunId(null);
            }}
            onViewResults={() => navigate("/results", { state: { runId } })}
            run={run}
          />
        ) : statusQuery.isError ? (
          <div
            className="border-l-2 border-danger bg-danger/8 px-4 py-3 text-sm text-danger"
            role="alert"
          >
            {toDisplayMessage(statusQuery.error)}
          </div>
        ) : (
          <p className="text-sm text-text-muted" role="status">
            Recovering run state…
          </p>
        )}
      </div>

      {!runId ? (
        <Link
          className="mt-4 inline-flex items-center gap-2 text-sm text-text-muted hover:text-text"
          to="/"
        >
          <ArrowLeft aria-hidden="true" className="size-4" /> Back to schema selection
        </Link>
      ) : null}
    </section>
  );
}
