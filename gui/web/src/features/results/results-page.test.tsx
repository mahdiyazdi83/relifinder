import { http, HttpResponse } from "msw";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type {
  RelationshipDetail,
  RelationshipListItem,
  RelationshipListResponse,
} from "../../api/client";
import { AppProviders } from "../../app/providers/app-providers";
import { appRoutes } from "../../app/router/routes";
import { server } from "../../test/mocks/server";

const runId = "opaque-results-run-123456789012345678901234";
const highId = "a".repeat(64);
const mediumId = "b".repeat(64);

const high: RelationshipListItem = {
  id: highId,
  source: {
    schema_name: "SALES",
    table_name: "ORDERS",
    column_name: "CUSTOMER_ID",
    datatype: "NUMBER",
  },
  target: {
    schema_name: "CORE",
    table_name: "CUSTOMERS",
    column_name: "ID",
    datatype: "NUMBER",
  },
  confidence_score: 96,
  confidence_label: "HIGH",
  cardinality: "Many-to-One",
  validation_status: "VALIDATED",
  match_ratio: 0.94,
  cross_schema: true,
  target_key_type: "PRIMARY_KEY",
};

const medium: RelationshipListItem = {
  id: mediumId,
  source: {
    schema_name: "APP",
    table_name: "EVENTS",
    column_name: "ACTOR_ID",
    datatype: "NUMBER",
  },
  target: {
    schema_name: "APP",
    table_name: "USERS",
    column_name: "ID",
    datatype: "NUMBER",
  },
  confidence_score: 78,
  confidence_label: "MEDIUM-HIGH",
  cardinality: "Unknown / Insufficient Evidence",
  validation_status: "NOT_RUN",
  match_ratio: null,
  cross_schema: false,
  target_key_type: "UNIQUE_KEY",
};

const summary = {
  schemas_analyzed: 2,
  tables: 19,
  columns: 123,
  candidates_generated: 287,
  candidates_validated: 84,
  candidates_skipped: 4,
  relationships_in_report: 2,
  run_mode: "sampled",
  elapsed_seconds: 12.5,
} satisfies RelationshipListResponse["summary"];

const listResponse: RelationshipListResponse = {
  run_id: runId,
  summary,
  total: 2,
  relationships: [medium, high],
};

const detail: RelationshipDetail = {
  ...high,
  score_breakdown: {
    name: 20,
    datatype: 15,
    target_key: 20,
    overlap: 29,
    consistency: 7,
    structure: 5,
  },
  validation: {
    status: "VALIDATED",
    sample_size: 100,
    matched_values: 94,
    unmatched_values: 6,
    match_ratio: 0.94,
    source_uniqueness_ratio: 0.61,
    target_uniqueness_ratio: 1,
    source_null_ratio: 0,
    target_sample_size: 80,
    sampling_used: true,
  },
  cardinality_confidence: 0.88,
  cardinality_explanation: "Source values repeat while target values are unique.",
  explanation: "Strong name, key, datatype, and sampled overlap evidence.",
};

function renderResults() {
  return render(
    <AppProviders>
      <RouterProvider
        router={createMemoryRouter(appRoutes, {
          initialEntries: [`/results?run=${runId}`],
        })}
      />
    </AppProviders>,
  );
}

function installResultsApi(response: RelationshipListResponse = listResponse) {
  let detailRequests = 0;
  server.use(
    http.get("/api/runs/:runId/relationships", () => HttpResponse.json(response)),
    http.get("/api/runs/:runId/relationships/:relationshipId", ({ params }) => {
      detailRequests += 1;
      if (params.relationshipId !== highId) {
        return HttpResponse.json(
          { error: { code: "RELATIONSHIP_NOT_FOUND", message: "Relationship not found." } },
          { status: 404 },
        );
      }
      return HttpResponse.json(detail);
    }),
  );
  return () => detailRequests;
}

describe("relationship explorer", () => {
  it("orders by confidence and loads full evidence only after row selection", async () => {
    const user = userEvent.setup();
    const detailRequests = installResultsApi();
    renderResults();

    expect(
      await screen.findByRole("heading", { name: "Relationship Explorer" }),
    ).toBeInTheDocument();
    const rows = await screen.findAllByRole("row");
    expect(within(rows[1]!).getByText("SALES.ORDERS")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("APP.EVENTS")).toBeInTheDocument();
    expect(detailRequests()).toBe(0);

    await user.click(rows[1]!);
    expect(await screen.findByRole("heading", { name: "Score evidence" })).toBeInTheDocument();
    expect(detailRequests()).toBe(1);
    expect(screen.getAllByText("94.00%").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Strong name, key, datatype, and sampled overlap evidence."),
    ).toBeInTheDocument();
    expect(screen.getByText("0.00%")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close inspector" }));
    expect(screen.getByText("Select a relationship")).toBeInTheDocument();
  });

  it("combines search and technical filters and distinguishes a filtered-empty result", async () => {
    const user = userEvent.setup();
    installResultsApi();
    renderResults();
    await screen.findByText("SALES.ORDERS");

    await user.selectOptions(screen.getByLabelText("Target key"), "PRIMARY_KEY");
    await user.click(screen.getByRole("checkbox", { name: "Cross-schema only" }));
    expect(screen.getByText("Showing 1 of 2 relationships")).toBeInTheDocument();
    expect(screen.queryByText("APP.EVENTS")).not.toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "Search relationships" }), "missing");
    expect(
      screen.getByRole("heading", { name: "No relationships match the current filters." }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText("APP.EVENTS")).toBeInTheDocument();
  });

  it("renders NOT_RUN as neutral and preserves an exact zero match ratio", async () => {
    const zeroResponse: RelationshipListResponse = {
      ...listResponse,
      relationships: [{ ...medium, match_ratio: 0 }],
      total: 1,
    };
    installResultsApi(zeroResponse);
    renderResults();

    const row = (await screen.findByText("APP.EVENTS")).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("NOT_RUN")).toHaveAttribute(
      "title",
      "Sampling was not requested; this is not a failure.",
    );
    expect(within(row!).getByText("0.00%")).toBeInTheDocument();
  });

  it("shows distinct empty-run and sanitized API error states", async () => {
    installResultsApi({ ...listResponse, relationships: [], total: 0 });
    const view = renderResults();
    expect(
      await screen.findByRole("heading", { name: "No relationships in this run" }),
    ).toBeInTheDocument();

    view.unmount();
    server.use(
      http.get("/api/runs/:runId/relationships", () =>
        HttpResponse.json(
          { error: { code: "RUN_NOT_COMPLETED", message: "This run is not completed yet." } },
          { status: 409 },
        ),
      ),
    );
    renderResults();
    expect(
      await screen.findByRole("heading", { name: "Results unavailable" }, { timeout: 3_000 }),
    ).toBeInTheDocument();
    expect(screen.getByText("This run is not completed yet.")).toBeInTheDocument();
  });
});
