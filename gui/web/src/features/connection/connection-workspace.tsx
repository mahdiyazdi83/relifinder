import { ArrowRight, DatabaseZap, LogOut, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiRequestError, toDisplayMessage } from "../../api/errors";
import { Button } from "../../components/ui/button";
import { ActivityIndicator } from "../../components/ui/activity-indicator";
import { SchemaSelector } from "../schemas/schema-selector";
import { useWorkspaceStore } from "../workspace/workspace-store";
import { CapabilityChecks } from "./capability-checks";
import {
  useConnectionSchemas,
  useCreateConnection,
  useDisconnectConnection,
} from "./connection-api";
import { ConnectionForm, type ConnectionFormValues } from "./connection-form";

export function ConnectionWorkspace() {
  const navigate = useNavigate();
  const connection = useWorkspaceStore((state) => state.connection);
  const selectedSchemas = useWorkspaceStore((state) => state.selectedSchemas);
  const setConnection = useWorkspaceStore((state) => state.setConnection);
  const setSelectedSchemas = useWorkspaceStore((state) => state.setSelectedSchemas);
  const clearWorkspaceConnection = useWorkspaceStore((state) => state.disconnect);
  const selectedNames = useMemo(
    () => new Set(selectedSchemas.map((schema) => schema.name)),
    [selectedSchemas],
  );
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const createMutation = useCreateConnection();
  const disconnectMutation = useDisconnectConnection();
  const schemasQuery = useConnectionSchemas(connection?.connection_id ?? null);

  async function connect(values: ConnectionFormValues): Promise<boolean> {
    setConnectionError(null);
    try {
      const response = await createMutation.mutateAsync({
        ...values,
        replace_connection_id: connection?.connection_id,
      });
      setConnection({
        connection_id: response.connection_id,
        expires_in_seconds: response.expires_in_seconds,
        checks: response.checks,
        host: values.host,
        port: values.port,
        serviceName: values.service_name,
        username: values.username,
      });
      return true;
    } catch (error) {
      setConnectionError(toDisplayMessage(error));
      return false;
    } finally {
      createMutation.reset();
    }
  }

  async function disconnect() {
    if (!connection) return;
    setConnectionError(null);
    try {
      await disconnectMutation.mutateAsync(connection.connection_id);
      clearWorkspaceConnection();
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === "CONNECTION_SESSION_NOT_FOUND") {
        clearWorkspaceConnection();
      }
      setConnectionError(toDisplayMessage(error));
    } finally {
      disconnectMutation.reset();
    }
  }

  function changeSchemas(names: Set<string>) {
    const available = schemasQuery.data?.schemas ?? [];
    setSelectedSchemas(available.filter((schema) => names.has(schema.name)));
  }

  const ready = Boolean(connection && selectedSchemas.length > 0);

  return (
    <section aria-labelledby="connection-title" className="mx-auto max-w-7xl px-5 py-7 lg:px-8">
      <div className="border-b border-border pb-5">
        <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
          Workspace initialization
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-text" id="connection-title">
              Secure Oracle connection
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-text-muted">
              Establish an ephemeral SELECT-only session, inspect visible metadata, and define the
              analysis boundary.
            </p>
          </div>
          {connection ? (
            <Button
              className="ml-auto text-danger hover:text-danger"
              disabled={disconnectMutation.isPending}
              onClick={disconnect}
              type="button"
              variant="ghost"
            >
              <LogOut aria-hidden="true" className="size-4" />
              {disconnectMutation.isPending ? "Disconnecting..." : "Disconnect"}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="mt-5 grid items-start gap-5 xl:grid-cols-[23rem_minmax(0,1fr)]">
        <div className="space-y-5">
          <section className="rf-panel" aria-labelledby="connection-form-title">
            <div className="border-b border-border bg-surface-elevated/80 px-4 py-3">
              <h2
                className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted"
                id="connection-form-title"
              >
                Connection endpoint
              </h2>
            </div>
            <div className="p-4">
              <ConnectionForm
                connected={Boolean(connection)}
                errorMessage={connectionError}
                isSubmitting={createMutation.isPending}
                onSubmit={connect}
              />
            </div>
          </section>

          {connection ? (
            <CapabilityChecks
              checks={connection.checks}
              expiresInSeconds={connection.expires_in_seconds}
            />
          ) : (
            <div className="border-l-2 border-accent bg-surface px-4 py-3 text-xs leading-5 text-text-muted">
              <div className="mb-1 flex items-center gap-2 font-medium text-text">
                <ShieldCheck aria-hidden="true" className="size-4 text-accent" /> Runtime-only
                credentials
              </div>
              Credentials live only in backend process memory and are never written to project files
              or browser storage.
            </div>
          )}
        </div>

        <div className="space-y-4">
          {!connection ? (
            <div className="grid min-h-80 place-items-center border border-dashed border-border bg-surface/40 px-6 text-center">
              <div>
                <DatabaseZap
                  aria-hidden="true"
                  className="mx-auto size-8 text-text-muted"
                  strokeWidth={1.4}
                />
                <h2 className="mt-3 text-sm font-medium text-text">No verified connection</h2>
                <p className="mt-1 max-w-sm text-sm leading-5 text-text-muted">
                  Verify authentication and metadata visibility to unlock schema discovery.
                </p>
              </div>
            </div>
          ) : schemasQuery.isLoading ? (
            <div
              className="rf-panel flex items-center gap-3 px-4 py-8 text-sm text-text-muted"
              role="status"
            >
              <ActivityIndicator /> Loading accessible schema metadata...
            </div>
          ) : schemasQuery.isError ? (
            <div
              className="border-l-2 border-danger bg-danger/8 px-4 py-3 text-sm text-danger"
              role="alert"
            >
              {toDisplayMessage(schemasQuery.error)}
            </div>
          ) : (
            <SchemaSelector
              onChange={changeSchemas}
              schemas={schemasQuery.data?.schemas ?? []}
              selected={selectedNames}
            />
          )}

          {connection ? (
            <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
              <div>
                <p className={`text-sm font-medium ${ready ? "text-success" : "text-text-muted"}`}>
                  {ready ? "Analysis boundary ready" : "Select at least one schema to continue"}
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {selectedSchemas
                    .reduce((sum, schema) => sum + schema.table_count, 0)
                    .toLocaleString()}{" "}
                  tables in the current scope.
                </p>
              </div>
              <Button
                className="ml-auto"
                disabled={!ready}
                onClick={() => navigate("/analysis")}
                type="button"
              >
                Continue to analysis <ArrowRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
