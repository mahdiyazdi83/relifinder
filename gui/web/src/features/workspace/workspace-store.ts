import { create } from "zustand";

import type {
  AnalysisProfile,
  ConnectionResponse,
  RunStatusResponse,
  SchemaSummary,
} from "../../api/client";

export type SafeConnection = Pick<
  ConnectionResponse,
  "connection_id" | "expires_in_seconds" | "checks"
> & {
  host: string;
  port: number;
  serviceName: string;
  username: string;
};

export type RunContext = {
  runId: string;
  state: RunStatusResponse["state"];
  profile?: AnalysisProfile;
  current: number;
  total: number;
  message: string;
};

type WorkspaceState = {
  connection: SafeConnection | null;
  selectedSchemas: SchemaSummary[];
  run: RunContext | null;
  setConnection: (connection: SafeConnection) => void;
  setSelectedSchemas: (schemas: SchemaSummary[]) => void;
  startRun: (run: RunContext) => void;
  updateRun: (run: Partial<RunContext> & Pick<RunContext, "runId">) => void;
  adoptCompletedRun: (runId: string) => void;
  clearRun: () => void;
  disconnect: () => void;
  reset: () => void;
};

const initialState = {
  connection: null,
  selectedSchemas: [],
  run: null,
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,
  setConnection: (connection) =>
    set((state) => ({
      connection,
      selectedSchemas: [],
      run: state.run?.state === "COMPLETED" ? state.run : null,
    })),
  setSelectedSchemas: (selectedSchemas) => set({ selectedSchemas }),
  startRun: (run) => set({ run }),
  updateRun: (next) =>
    set((state) => ({
      run: state.run?.runId === next.runId ? { ...state.run, ...next } : state.run,
    })),
  adoptCompletedRun: (runId) =>
    set((state) => ({
      run:
        state.run?.runId === runId
          ? { ...state.run, state: "COMPLETED" }
          : { runId, state: "COMPLETED", current: 1, total: 1, message: "Artifacts ready" },
    })),
  clearRun: () => set({ run: null }),
  disconnect: () =>
    set((state) => ({
      connection: null,
      selectedSchemas: [],
      run: state.run?.state === "COMPLETED" ? state.run : null,
    })),
  reset: () => set(initialState),
}));

export function resetWorkspaceStore() {
  useWorkspaceStore.getState().reset();
}
