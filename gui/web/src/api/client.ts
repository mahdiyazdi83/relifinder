import type { components } from "./schema";
import { toApiRequestError } from "./errors";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type ConnectionCreateRequest = components["schemas"]["ConnectionCreateRequest"];
export type ConnectionResponse = components["schemas"]["ConnectionResponse"];
export type SchemaListResponse = components["schemas"]["SchemaListResponse"];
export type SchemaSummary = components["schemas"]["SchemaSummaryResponse"];
export type AnalysisConfiguration = components["schemas"]["AnalysisConfiguration"];
export type AnalysisProfile = components["schemas"]["AnalysisProfile"];
export type RunCreateRequest = components["schemas"]["RunCreateRequest"];
export type RunCreateResponse = components["schemas"]["RunCreateResponse"];
export type RunStatusResponse = components["schemas"]["RunStatusResponse"];
export type RunProgressEvent = Omit<RunStatusResponse, "connection_id" | "selected_schemas">;
export type RunCancelResponse = components["schemas"]["RunCancelResponse"];
export type RelationshipListResponse = components["schemas"]["RelationshipListResponse"];
export type RelationshipListItem = components["schemas"]["RelationshipListItem"];
export type RelationshipDetail = components["schemas"]["RelationshipDetail"];

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw await toApiRequestError(response);
  }
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health", { signal });
}

export function createConnection(payload: ConnectionCreateRequest): Promise<ConnectionResponse> {
  return requestJson<ConnectionResponse>("/api/connections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSchemas(
  connectionId: string,
  signal?: AbortSignal,
): Promise<SchemaListResponse> {
  return requestJson<SchemaListResponse>(
    `/api/connections/${encodeURIComponent(connectionId)}/schemas`,
    { signal },
  );
}

export async function disconnectConnection(connectionId: string): Promise<void> {
  const response = await fetch(`/api/connections/${encodeURIComponent(connectionId)}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await toApiRequestError(response);
  }
}

export function createRun(payload: RunCreateRequest): Promise<RunCreateResponse> {
  return requestJson<RunCreateResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getRun(runId: string, signal?: AbortSignal): Promise<RunStatusResponse> {
  return requestJson<RunStatusResponse>(`/api/runs/${encodeURIComponent(runId)}`, { signal });
}

export function cancelRun(runId: string): Promise<RunCancelResponse> {
  return requestJson<RunCancelResponse>(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
  });
}

export function getRelationships(
  runId: string,
  signal?: AbortSignal,
): Promise<RelationshipListResponse> {
  return requestJson<RelationshipListResponse>(
    `/api/runs/${encodeURIComponent(runId)}/relationships`,
    { signal },
  );
}

export function getRelationshipDetail(
  runId: string,
  relationshipId: string,
  signal?: AbortSignal,
): Promise<RelationshipDetail> {
  return requestJson<RelationshipDetail>(
    `/api/runs/${encodeURIComponent(runId)}/relationships/${encodeURIComponent(relationshipId)}`,
    { signal },
  );
}
