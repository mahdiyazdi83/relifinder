import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { AnalysisConfiguration, RunStatusResponse } from "../../api/client";
import { ApiRequestError, toDisplayMessage } from "../../api/errors";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { useWorkspaceStore } from "../workspace/workspace-store";
import { AnalysisConfigurationForm } from "./analysis-configuration-form";
import { AnalysisRunView } from "./analysis-run-view";
import { useCancelRun, useCreateRun, useRunStatus } from "./run-api";
import { useRunEvents } from "./use-run-events";

export function AnalysisPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const connection = useWorkspaceStore((state) => state.connection);
  const selectedSchemas = useWorkspaceStore((state) => state.selectedSchemas);
  const workspaceRun = useWorkspaceStore((state) => state.run);
  const startWorkspaceRun = useWorkspaceStore((state) => state.startRun);
  const updateWorkspaceRun = useWorkspaceStore((state) => state.updateRun);
  const clearRun = useWorkspaceStore((state) => state.clearRun);
  const schemas = selectedSchemas.map((schema) => schema.name);
  const runId = workspaceRun?.runId ?? null;
  const [startError, setStartError] = useState<string | null>(null);
  const [reconnectRequired, setReconnectRequired] = useState(false);
  const createMutation = useCreateRun();
  const cancelMutation = useCancelRun();
  const statusQuery = useRunStatus(runId);
  useRunEvents(runId);

  useEffect(() => {
    const run = statusQuery.data;
    if (!run) return;
    updateWorkspaceRun({
      runId: run.run_id,
      state: run.state,
      current: run.current ?? 0,
      total: run.total ?? 0,
      message: run.message,
    });
  }, [statusQuery.data, updateWorkspaceRun]);

  if (!connection || schemas.length === 0) {
    return (
      <section className="mx-auto max-w-3xl px-5 py-10" aria-labelledby="analysis-required-title">
        <div className="rf-panel border-l-2 border-l-warning px-5 py-5">
          <CircleAlert aria-hidden="true" className="size-5 text-warning" />
          <h1 className="mt-3 text-lg font-semibold text-text" id="analysis-required-title">
            Reconnect and select schemas
          </h1>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            Analysis configuration requires an active runtime Oracle session and at least one
            selected schema. Completed artifacts remain available from the workflow rail.
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
        connection_id: connection!.connection_id,
        schemas,
        configuration,
      });
      const queued: RunStatusResponse = {
        sequence: 0,
        run_id: response.run_id,
        state: response.status,
        message: "Analysis is queued",
        stats: {},
        connection_id: connection!.connection_id,
        selected_schemas: schemas,
      };
      queryClient.setQueryData(["run", response.run_id], queued);
      startWorkspaceRun({
        runId: response.run_id,
        state: response.status,
        profile: configuration.profile,
        current: 0,
        total: 0,
        message: queued.message,
      });
    } catch (error) {
      setStartError(toDisplayMessage(error));
      setReconnectRequired(
        error instanceof ApiRequestError && error.code === "CONNECTION_SESSION_NOT_FOUND",
      );
    } finally {
      createMutation.reset();
    }
  }

  const run = runId && !statusQuery.isError ? statusQuery.data : null;

  return (
    <section className="mx-auto max-w-5xl px-5 py-7 lg:px-8" aria-labelledby="analysis-title">
      <div className="border-b border-border pb-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
          Analysis control plane
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text" id="analysis-title">
          {runId ? "Discovery pipeline" : "Analysis Configuration"}
        </h1>
        <p className="mt-1.5 text-sm leading-6 text-text-muted">
          {runId
            ? "Live core state with truthful phase and bounded progress reporting."
            : `${schemas.length} schemas selected. Tune workload and evidence thresholds before starting the local run.`}
        </p>
      </div>

      <div className="rf-panel mt-5 p-5">
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
              clearRun();
            }}
            onViewResults={() => navigate(`/results?run=${encodeURIComponent(runId)}`)}
            run={run}
          />
        ) : statusQuery.isError ? (
          <div
            className="border-l-2 border-danger bg-danger/8 px-4 py-3 text-sm text-danger"
            role="alert"
          >
            <p>{toDisplayMessage(statusQuery.error)}</p>
            <p className="mt-1 text-text-muted">
              The local runtime may have restarted. No second run was started.
            </p>
            <Link
              className="mt-3 inline-flex items-center gap-2 text-accent hover:underline"
              to="/"
            >
              <ArrowLeft aria-hidden="true" className="size-4" /> Return to Connection
            </Link>
          </div>
        ) : (
          <p className="flex items-center gap-2 text-sm text-text-muted" role="status">
            <ActivityIndicator /> Recovering run state...
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
