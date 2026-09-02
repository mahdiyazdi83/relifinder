import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { resetWorkspaceStore } from "../features/workspace/workspace-store";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetWorkspaceStore();
  window.localStorage.clear();
  document.documentElement.dataset.theme = "dark";
});
afterAll(() => server.close());
