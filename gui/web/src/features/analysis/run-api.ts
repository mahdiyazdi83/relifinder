import { useMutation, useQuery } from "@tanstack/react-query";

import { cancelRun, createRun, getRun, type RunStatusResponse } from "../../api/client";
import { ApiRequestError } from "../../api/errors";

const terminalStates = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function useCreateRun() {
  return useMutation({ mutationFn: createRun });
}

export function useRunStatus(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: ({ signal }) => getRun(runId!, signal),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const data = query.state.data as RunStatusResponse | undefined;
      return data && terminalStates.has(data.state) ? false : 3000;
    },
    retry: (failureCount, error) =>
      failureCount < 1 && (!(error instanceof ApiRequestError) || error.status >= 500),
  });
}

export function useCancelRun() {
  return useMutation({ mutationFn: cancelRun });
}
