import { useQuery } from "@tanstack/react-query";

import { getArtifacts, getArtifactText } from "../../api/client";
import { ApiRequestError } from "../../api/errors";

export function useArtifacts(runId: string | null) {
  return useQuery({
    queryKey: ["artifacts", runId],
    queryFn: ({ signal }) => getArtifacts(runId!, signal),
    enabled: Boolean(runId),
    retry: retryTransient,
  });
}

export function useDbmlText(runId: string | null, artifactId: string | null, available: boolean) {
  return useQuery({
    queryKey: ["artifact-text", runId, artifactId],
    queryFn: ({ signal }) => getArtifactText(runId!, artifactId!, signal),
    enabled: Boolean(runId && artifactId && available),
    retry: retryTransient,
  });
}

function retryTransient(failureCount: number, error: Error) {
  return failureCount < 1 && (!(error instanceof ApiRequestError) || error.status >= 500);
}
