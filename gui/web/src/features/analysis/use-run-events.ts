import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import type { RunProgressEvent, RunStatusResponse } from "../../api/client";

const terminalStates = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
const MAX_RECONNECTS = 3;

export function useRunEvents(runId: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!runId) return;
    let source: EventSource | null = null;
    let retryTimer: number | null = null;
    let reconnects = 0;
    let disposed = false;

    function connect() {
      if (disposed) return;
      source = new EventSource(`/api/runs/${encodeURIComponent(runId!)}/events`);

      function receive(message: MessageEvent<string>) {
        try {
          const event = JSON.parse(message.data) as RunProgressEvent;
          queryClient.setQueryData<RunStatusResponse>(["run", runId], (current) =>
            current ? { ...current, ...event } : current,
          );
          reconnects = 0;
          if (terminalStates.has(event.state)) source?.close();
        } catch {
          // A malformed local event is ignored; status polling remains the recovery path.
        }
      }

      function recover() {
        source?.close();
        void queryClient.invalidateQueries({ queryKey: ["run", runId] });
        if (disposed || reconnects >= MAX_RECONNECTS) return;
        reconnects += 1;
        retryTimer = window.setTimeout(connect, reconnects * 1000);
      }

      source.addEventListener("progress", receive as EventListener);
      source.addEventListener("error", recover);
    }

    connect();
    return () => {
      disposed = true;
      if (retryTimer != null) window.clearTimeout(retryTimer);
      source?.close();
    };
  }, [queryClient, runId]);
}
