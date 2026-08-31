import { useMutation, useQuery } from "@tanstack/react-query";

import { createConnection, disconnectConnection, getSchemas } from "../../api/client";

export function useCreateConnection() {
  return useMutation({ mutationFn: createConnection });
}

export function useConnectionSchemas(connectionId: string | null) {
  return useQuery({
    queryKey: ["connections", connectionId, "schemas"],
    queryFn: ({ signal }) => getSchemas(connectionId!, signal),
    enabled: Boolean(connectionId),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

export function useDisconnectConnection() {
  return useMutation({ mutationFn: disconnectConnection });
}
