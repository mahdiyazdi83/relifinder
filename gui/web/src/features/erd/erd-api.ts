import { useQuery } from "@tanstack/react-query";

import { getErdGraph } from "../../api/client";

export function useErdGraph(runId: string | null) {
  return useQuery({
    queryKey: ["erd", runId],
    queryFn: ({ signal }) => getErdGraph(runId!, signal),
    enabled: Boolean(runId),
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  });
}
