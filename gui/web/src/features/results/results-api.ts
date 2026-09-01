import { useQuery } from "@tanstack/react-query";

import { getRelationshipDetail, getRelationships } from "../../api/client";

export function useRelationships(runId: string | null) {
  return useQuery({
    queryKey: ["relationships", runId],
    queryFn: ({ signal }) => getRelationships(runId!, signal),
    enabled: Boolean(runId),
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  });
}

export function useRelationshipDetail(runId: string | null, relationshipId: string | null) {
  return useQuery({
    queryKey: ["relationship", runId, relationshipId],
    queryFn: ({ signal }) => getRelationshipDetail(runId!, relationshipId!, signal),
    enabled: Boolean(runId && relationshipId),
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  });
}
