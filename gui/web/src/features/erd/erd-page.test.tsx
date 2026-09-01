import { http, HttpResponse } from "msw";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { RelationshipDetail } from "../../api/client";
import { AppProviders } from "../../app/providers/app-providers";
import { appRoutes } from "../../app/router/routes";
import { server } from "../../test/mocks/server";
import { erdFixture } from "./erd-test-fixtures";

vi.mock("./erd-layout", async () => {
  const actual = await vi.importActual<typeof import("./erd-layout")>("./erd-layout");
  return {
    ...actual,
    layoutErdGraph: async (nodes: Parameters<typeof actual.layoutErdGraph>[0]) => nodes,
  };
});

const runId = "erd-page-run-123456789012345678901234";
const graph = erdFixture();
const high = graph.relationships[0]!;
const detail: RelationshipDetail = {
  ...high,
  score_breakdown: {
    name: 34,
    datatype: 15,
    target_key: 15,
    overlap: 24,
    consistency: 4,
    structure: 4,
  },
  validation: {
    status: "VALIDATED",
    sample_size: 100,
    matched_values: 94,
    unmatched_values: 6,
    match_ratio: 0.94,
    source_uniqueness_ratio: 0.6,
    target_uniqueness_ratio: 1,
    target_sample_size: 80,
    source_null_ratio: 0,
    sampling_used: true,
  },
  cardinality_confidence: 0.9,
  cardinality_explanation: "The target is unique and source values repeat.",
  explanation: "Safe aggregate evidence supports this relationship.",
};

beforeAll(() => {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
});

function installApi() {
  server.use(
    http.get("/api/runs/:runId/erd", () => HttpResponse.json({ ...graph, run_id: runId })),
    http.get("/api/runs/:runId/relationships/:relationshipId", ({ params }) =>
      params.relationshipId === high.id
        ? HttpResponse.json(detail)
        : HttpResponse.json(
            { error: { code: "RELATIONSHIP_NOT_FOUND", message: "Relationship not found." } },
            { status: 404 },
          ),
    ),
  );
}

function renderErd(entry = `/erd?run=${runId}`) {
  return render(
    <AppProviders>
      <RouterProvider
        router={createMemoryRouter(appRoutes, {
          initialEntries: [entry],
        })}
      />
    </AppProviders>,
  );
}

describe("interactive ERD page", () => {
  it("renders tables, collapses large nodes, filters and focuses one-hop neighbors", async () => {
    const user = userEvent.setup();
    installApi();
    renderErd();

    expect(await screen.findByRole("heading", { name: "Interactive ERD" })).toBeInTheDocument();
    expect(await screen.findByText("REQUEST")).toBeInTheDocument();
    expect(screen.getByText("3 tables · 2 relationships")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Expand APP.REQUEST" }));
    expect(screen.getByRole("button", { name: "Collapse APP.REQUEST" })).toBeInTheDocument();

    await user.clear(screen.getByLabelText("ERD minimum confidence"));
    await user.type(screen.getByLabelText("ERD minimum confidence"), "90");
    expect(await screen.findByText("2 tables · 1 relationships")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("ERD minimum confidence"));
    await user.type(screen.getByLabelText("ERD minimum confidence"), "60");
    fireEvent.click(screen.getByText("AUDIT"));
    expect(
      await screen.findByRole("complementary", { name: "Table inspector" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Focus table (1 hop)" }));
    expect(screen.getByRole("button", { name: "Exit Focus" })).toBeInTheDocument();
    expect(screen.getByText("2 tables · 1 relationships")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Exit Focus" }));
    expect(screen.getByText("3 tables · 2 relationships")).toBeInTheDocument();
  });

  it("selects an edge and reuses the full Phase 4 evidence inspector", async () => {
    installApi();
    renderErd(`/erd?run=${runId}&rel=${high.id}`);
    await screen.findByText("REQUEST");
    expect(await screen.findByRole("heading", { name: "Score evidence" })).toBeInTheDocument();
    expect(
      screen.getByText("Safe aggregate evidence supports this relationship."),
    ).toBeInTheDocument();
    expect(screen.getAllByText("94.00%").length).toBeGreaterThan(0);
  });

  it("shows an explained empty graph when filters remove all relationships", async () => {
    const user = userEvent.setup();
    installApi();
    renderErd();
    await screen.findByText("REQUEST");

    await user.clear(screen.getByLabelText("ERD minimum confidence"));
    await user.type(screen.getByLabelText("ERD minimum confidence"), "100");
    expect(
      await screen.findByRole("heading", { name: "ERD has no visible relationships" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No relationships match the current ERD filters.")).toBeInTheDocument();
  });

  it("applies multi-schema selection without leaving orphan edges", async () => {
    const user = userEvent.setup();
    installApi();
    renderErd();
    await screen.findByText("REQUEST");

    await user.click(screen.getByText(/Schemas 2\/2/));
    const core = screen.getByRole("checkbox", { name: "CORE" });
    await user.click(core);
    await waitFor(() => expect(screen.getByText("2 tables · 1 relationships")).toBeInTheDocument());
    expect(screen.queryByText("PARTY")).not.toBeInTheDocument();
  });
});
