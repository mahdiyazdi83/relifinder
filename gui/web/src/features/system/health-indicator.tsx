import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../../api/client";
import { toDisplayMessage } from "../../api/errors";

export function HealthIndicator() {
  const health = useQuery({
    queryKey: ["system", "health"],
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: 30_000,
  });

  const healthy = health.data?.status === "ok";
  const label = healthy
    ? "Local Core: Healthy"
    : health.isError
      ? "Local Core: Unavailable"
      : "Local Core: Checking";

  return (
    <div
      className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-text-muted"
      role="status"
      title={health.isError ? toDisplayMessage(health.error) : undefined}
    >
      <span
        aria-hidden="true"
        className={`size-1.5 ${healthy ? "bg-success" : health.isError ? "bg-danger" : "bg-warning"}`}
      />
      <span className="max-sm:sr-only">{label}</span>
    </div>
  );
}
