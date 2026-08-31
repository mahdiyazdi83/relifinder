import { ArrowRight, DatabaseZap, LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ConnectionResponse } from "../../api/client";
import { ApiRequestError, toDisplayMessage } from "../../api/errors";
import { Button } from "../../components/ui/button";
import { SchemaSelector } from "../schemas/schema-selector";
import { CapabilityChecks } from "./capability-checks";
import {
  useConnectionSchemas,
  useCreateConnection,
  useDisconnectConnection,
} from "./connection-api";
import { ConnectionForm, type ConnectionFormValues } from "./connection-form";
import { WorkflowStatus } from "./workflow-status";

export function ConnectionWorkspace() {
  const navigate = useNavigate();
  const [connection, setConnection] = useState<ConnectionResponse | null>(null);
  const [selectedSchemas, setSelectedSchemas] = useState<Set<string>>(new Set());
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const createMutation = useCreateConnection();
  const disconnectMutation = useDisconnectConnection();
  const schemasQuery = useConnectionSchemas(connection?.connection_id ?? null);

  function clearConnection() {
    setConnection(null);
    setSelectedSchemas(new Set());
  }
  async function connect(values: ConnectionFormValues): Promise<boolean> {
    setConnectionError(null);
    try {
      const response = await createMutation.mutateAsync({
        ...values,
        replace_connection_id: connection?.connection_id,
      });
      setConnection(response);
      setSelectedSchemas(new Set());
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
      clearConnection();
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === "CONNECTION_SESSION_NOT_FOUND") {
        clearConnection();
      }
      setConnectionError(toDisplayMessage(error));
    } finally {
      disconnectMutation.reset();
    }
  }

  const ready = Boolean(connection && selectedSchemas.size > 0);

  return (
    <section aria-labelledby="connection-title" className="mx-auto max-w-6xl px-5 py-6 lg:px-8">
      <WorkflowStatus connected={Boolean(connection)} schemaSelected={ready} />

      <div className="mt-6 border-b border-border pb-4">
        <p className="mb-1 font-mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
          Local workflow / Phase 2
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-text" id="connection-title">
              Secure Oracle connection
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-text-muted">
              Verify SELECT-only ReliFinder access and choose schemas visible through Oracle
              metadata.
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
              {disconnectMutation.isPending ? "Disconnecting…" : "Disconnect"}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="space-y-5">
          <section
            className="border border-border bg-surface"
            aria-labelledby="connection-form-title"
          >
            <div className="border-b border-border bg-surface-elevated px-4 py-2.5">
              <h2
                className="font-mono text-xs uppercase tracking-wider text-text-muted"
                id="connection-form-title"
              >
                Connection details
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
              The backend keeps credentials only in process memory. They are never written to
              project files or browser storage. Standard browser password-manager behavior remains
              available.
            </div>
          )}
        </div>

        <div className="space-y-4">
          {!connection ? (
            <div className="grid min-h-72 place-items-center border border-dashed border-border px-6 text-center">
              <div>
                <DatabaseZap
                  aria-hidden="true"
                  className="mx-auto size-7 text-text-muted"
                  strokeWidth={1.5}
                />
                <h2 className="mt-3 text-sm font-medium text-text">No verified connection</h2>
                <p className="mt-1 max-w-sm text-sm leading-5 text-text-muted">
                  Submit connection details to verify authentication, required metadata views, and
                  schema discovery.
                </p>
              </div>
            </div>
          ) : schemasQuery.isLoading ? (
            <div
              className="border border-border bg-surface px-4 py-8 text-sm text-text-muted"
              role="status"
            >
              Loading accessible schema metadata…
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
              onChange={setSelectedSchemas}
              schemas={schemasQuery.data?.schemas ?? []}
              selected={selectedSchemas}
            />
          )}

          {connection ? (
            <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
              <div>
                <p className={`text-sm font-medium ${ready ? "text-success" : "text-text-muted"}`}>
                  {ready ? "Ready to configure analysis" : "Select at least one schema to continue"}
                </p>
                <p className="mt-0.5 text-xs text-text-muted">Continue does not start analysis.</p>
              </div>
              <Button
                className="ml-auto"
                disabled={!ready}
                onClick={() =>
                  navigate("/analysis", {
                    state: { schemas: [...selectedSchemas].sort() },
                  })
                }
                type="button"
              >
                Continue <ArrowRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
