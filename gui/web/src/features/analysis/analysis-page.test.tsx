import { http, HttpResponse } from "msw";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "../../app/providers/app-providers";
import { appRoutes } from "../../app/router/routes";
import { server } from "../../test/mocks/server";

const runId = "opaque-run-id-123456789012345678901234";
const connectionId = "opaque-session-id-12345678901234567890";

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners = new Map<string, EventListener>();
  close = vi.fn();

  constructor(readonly url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener);
  }

  emit(payload: object) {
    this.listeners.get("progress")?.(
      new MessageEvent("progress", { data: JSON.stringify(payload) }),
    );
  }
}

function renderAnalysis() {
  return render(
    <AppProviders>
      <RouterProvider
        router={createMemoryRouter(appRoutes, {
          initialEntries: [
            {
              pathname: "/analysis",
              state: { connectionId, schemas: ["CORE", "APP"] },
            },
          ],
        })}
      />
    </AppProviders>,
  );
}

function installRunApi() {
  server.use(
    http.post("/api/runs", () =>
      HttpResponse.json({ run_id: runId, status: "QUEUED" }, { status: 202 }),
    ),
    http.post("/api/runs/:runId/cancel", ({ params }) =>
      HttpResponse.json({ run_id: params.runId, status: "CANCEL_REQUESTED" }),
    ),
  );
}

function event(state: string, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    sequence: 2,
    run_id: runId,
    state,
    message: "Working",
    current: null,
    total: null,
    stats: {},
    summary: null,
    error_code: null,
    ...overrides,
  };
}

async function startRun(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Run Analysis" }));
  expect(await screen.findByRole("heading", { name: "Analysis Run" })).toBeInTheDocument();
  return MockEventSource.instances.at(-1)!;
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  installRunApi();
});

describe("analysis configuration and run workflow", () => {
  it("starts in Balanced and changes profiles deterministically", async () => {
    const user = userEvent.setup();
    renderAnalysis();

    expect(screen.getByRole("button", { name: /Balanced/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: /Fast/ }));
    expect(screen.getByRole("button", { name: /Fast/ })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByText("Advanced settings"));
    expect(screen.getByLabelText("Worker count")).toHaveValue(1);
    expect(screen.getByLabelText("Metadata candidate threshold")).toHaveValue(55);
  });

  it("marks advanced edits Custom and validates client-side ranges", async () => {
    const user = userEvent.setup();
    renderAnalysis();

    await user.click(screen.getByText("Advanced settings"));
    await user.clear(screen.getByLabelText("Worker count"));
    await user.type(screen.getByLabelText("Worker count"), "3");
    expect(screen.getByText(/Custom ·/)).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Minimum report confidence"));
    await user.type(screen.getByLabelText("Minimum report confidence"), "101");
    await user.click(screen.getByRole("button", { name: "Run Analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Values must stay within the documented ranges.",
    );
  });

  it("starts a run and renders real numeric validation progress", async () => {
    const user = userEvent.setup();
    renderAnalysis();
    const source = await startRun(user);

    source.emit(
      event("VALIDATING_CANDIDATES", {
        sequence: 4,
        message: "Validating relationship candidates",
        current: 84,
        total: 287,
        stats: { schemas: 2, tables: 19, columns: 123, candidates_generated: 287 },
      }),
    );

    expect(await screen.findByText(/84 \/ 287/)).toBeInTheDocument();
    expect(screen.getByText("287 qualified candidates")).toBeInTheDocument();
  });

  it("requests cooperative cancellation", async () => {
    const user = userEvent.setup();
    renderAnalysis();
    const source = await startRun(user);
    source.emit(event("READING_METADATA", { message: "Reading Oracle metadata" }));

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(await screen.findByRole("button", { name: "Cancellation requested" })).toBeDisabled();
  });

  it("shows completed summary and exposes only the Phase 4 navigation", async () => {
    const user = userEvent.setup();
    renderAnalysis();
    const source = await startRun(user);
    source.emit(
      event("COMPLETED", {
        sequence: 8,
        message: "Analysis completed",
        stats: {
          schemas: 2,
          tables: 19,
          columns: 123,
          candidates_generated: 287,
          candidates_validated: 84,
          candidates_skipped: 4,
          relationships_in_report: 32,
        },
        summary: {
          schemas_analyzed: 2,
          tables: 19,
          columns: 123,
          candidates_generated: 287,
          candidates_validated: 84,
          candidates_skipped: 4,
          relationships_in_report: 32,
          run_mode: "sampled",
          elapsed_seconds: 12.5,
        },
      }),
    );

    expect(await screen.findByRole("heading", { name: "Completed" })).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View Results" }));
    expect(
      await screen.findByRole("heading", { name: "Relationship results belong to Phase 4" }),
    ).toBeInTheDocument();
  });

  it("shows sanitized failure retry and reconnect-required creation state", async () => {
    const user = userEvent.setup();
    const view = renderAnalysis();
    const source = await startRun(user);
    source.emit(
      event("FAILED", {
        message: "Oracle connection was lost.",
        error_code: "ORACLE_CONNECTION_LOST",
      }),
    );

    expect(await screen.findByRole("heading", { name: "Analysis failed" })).toBeInTheDocument();
    expect(screen.getByText("Oracle connection was lost.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/ })).toBeInTheDocument();

    view.unmount();
    server.use(
      http.post("/api/runs", () =>
        HttpResponse.json(
          {
            error: {
              code: "CONNECTION_SESSION_NOT_FOUND",
              message: "The local Oracle connection session is missing or has expired.",
            },
          },
          { status: 404 },
        ),
      ),
    );
    renderAnalysis();
    await user.click(screen.getByRole("button", { name: "Run Analysis" }));
    expect(await screen.findByText(/runtime session expired/i)).toBeInTheDocument();
  });
});
