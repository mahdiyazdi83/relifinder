import type { components } from "./schema";
import { toApiRequestError } from "./errors";

export type HealthResponse = components["schemas"]["HealthResponse"];

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/health", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw await toApiRequestError(response);
  }
  return (await response.json()) as HealthResponse;
}
