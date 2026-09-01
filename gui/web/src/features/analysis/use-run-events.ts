import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import type { RunProgressEvent, RunStatusResponse } from "../../api/client";

const terminalStates = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function useRunEvents(runId: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);

    function receive(message: MessageEvent<string>) {
      try {
        const event = JSON.parse(message.data) as RunProgressEvent;
        queryClient.setQueryData<RunStatusResponse>(["run", runId], (current) =>
          current ? { ...current, ...event } : current,
        );
        if (terminalStates.has(event.state)) source.close();
      } catch {
        // A malformed local event is ignored; status polling remains the recovery path.
      }
    }

    source.addEventListener("progress", receive as EventListener);
    return () => source.close();
  }, [queryClient, runId]);
}
