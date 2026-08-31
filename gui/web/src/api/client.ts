import type { components } from "./schema";
import { toApiRequestError } from "./errors";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type ConnectionCreateRequest = components["schemas"]["ConnectionCreateRequest"];
export type ConnectionResponse = components["schemas"]["ConnectionResponse"];
export type SchemaListResponse = components["schemas"]["SchemaListResponse"];
export type SchemaSummary = components["schemas"]["SchemaSummaryResponse"];

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
