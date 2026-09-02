import { describe, expect, it } from "vitest";

import type { WorkflowSnapshot } from "./workflow";
import { currentStage, workflowStageState } from "./workflow";

const disconnected: WorkflowSnapshot = {
  connection: null,
  selectedSchemaCount: 0,
  run: null,
  pathname: "/",
};

const connection = {
  connection_id: "opaque-id",
  expires_in_seconds: 900,
  checks: [],
  host: "db.internal",
  port: 1521,
  serviceName: "ORCLPDB1",
  username: "APP",
};

describe("workflow derivation", () => {
  it("locks downstream stages before their prerequisites", () => {
    expect(workflowStageState("connection", disconnected)).toBe("current");
    expect(workflowStageState("schemas", disconnected)).toBe("locked");
    expect(workflowStageState("analysis", disconnected)).toBe("locked");
    expect(workflowStageState("results", disconnected)).toBe("locked");
  });

  it("unlocks schema selection and analysis from safe workspace state", () => {
    const connected = { ...disconnected, connection };
    expect(currentStage(connected)).toBe("schemas");
    expect(workflowStageState("schemas", connected)).toBe("current");
    expect(workflowStageState("analysis", connected)).toBe("locked");
    expect(workflowStageState("analysis", { ...connected, selectedSchemaCount: 2 })).toBe(
      "available",
    );
  });

  it("keeps completed artifact stages available without a live connection", () => {
    const completed: WorkflowSnapshot = {
      ...disconnected,
      pathname: "/results",
      run: { runId: "run-1", state: "COMPLETED", current: 1, total: 1, message: "Ready" },
    };
    expect(workflowStageState("results", completed)).toBe("current");
    expect(workflowStageState("erd", completed)).toBe("available");
    expect(workflowStageState("exports", completed)).toBe("available");
    expect(workflowStageState("analysis", completed)).toBe("locked");
  });
});
