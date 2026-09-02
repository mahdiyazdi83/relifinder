import type { RunContext, SafeConnection } from "./workspace-store";

export type WorkflowStageId = "connection" | "schemas" | "analysis" | "results" | "erd" | "exports";
export type WorkflowStageState = "complete" | "current" | "available" | "locked";

export type WorkflowSnapshot = {
  connection: SafeConnection | null;
  selectedSchemaCount: number;
  run: RunContext | null;
  pathname: string;
};

export function workflowStageState(
  stage: WorkflowStageId,
  snapshot: WorkflowSnapshot,
): WorkflowStageState {
  const connected = Boolean(snapshot.connection);
  const scoped = connected && snapshot.selectedSchemaCount > 0;
  const completed = snapshot.run?.state === "COMPLETED";
  const current = currentStage(snapshot);
  if (stage === current) return "current";

  const order: WorkflowStageId[] = [
    "connection",
    "schemas",
    "analysis",
    "results",
    "erd",
    "exports",
  ];
  const available =
    stage === "connection" ||
    (stage === "schemas" && connected) ||
    (stage === "analysis" && scoped) ||
    ((stage === "results" || stage === "erd" || stage === "exports") && completed);
  if (!available) return "locked";
  if (stage === current) return "current";
  return order.indexOf(stage) < order.indexOf(current) ? "complete" : "available";
}

export function currentStage(snapshot: WorkflowSnapshot): WorkflowStageId {
  if (snapshot.pathname.startsWith("/exports")) return "exports";
  if (snapshot.pathname.startsWith("/erd")) return "erd";
  if (snapshot.pathname.startsWith("/results")) return "results";
  if (snapshot.pathname.startsWith("/analysis")) return "analysis";
  return snapshot.connection ? "schemas" : "connection";
}

export function workflowHref(stage: WorkflowStageId, runId?: string): string {
  if (stage === "connection" || stage === "schemas") return "/";
  if (stage === "analysis") return "/analysis";
  return runId ? `/${stage}?run=${encodeURIComponent(runId)}` : `/${stage}`;
}
