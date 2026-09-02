import { beforeEach, describe, expect, it } from "vitest";

import { resetWorkspaceStore, useWorkspaceStore } from "./workspace-store";

const connection = {
  connection_id: "opaque-id",
  expires_in_seconds: 900,
  checks: [],
  host: "db.internal",
  port: 1521,
  serviceName: "ORCLPDB1",
  username: "APP",
};

describe("workspace store", () => {
  beforeEach(resetWorkspaceStore);

  it("holds only explicitly safe connection identity fields", () => {
    useWorkspaceStore.getState().setConnection(connection);
    expect(useWorkspaceStore.getState().connection).toEqual(connection);
    expect(JSON.stringify(useWorkspaceStore.getState())).not.toContain("password");
  });

  it("clears an active run on disconnect", () => {
    useWorkspaceStore.getState().setConnection(connection);
    useWorkspaceStore
      .getState()
      .startRun({ runId: "run-1", state: "SCORING", current: 2, total: 5, message: "Scoring" });
    useWorkspaceStore.getState().disconnect();
    expect(useWorkspaceStore.getState().connection).toBeNull();
    expect(useWorkspaceStore.getState().run).toBeNull();
  });

  it("preserves a completed artifact reference on disconnect", () => {
    useWorkspaceStore.getState().setConnection(connection);
    useWorkspaceStore.getState().adoptCompletedRun("run-1");
    useWorkspaceStore.getState().disconnect();
    expect(useWorkspaceStore.getState().connection).toBeNull();
    expect(useWorkspaceStore.getState().run?.runId).toBe("run-1");
  });
});
