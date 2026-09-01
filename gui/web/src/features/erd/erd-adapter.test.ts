import { describe, expect, it } from "vitest";

import { buildErdVisualization, columnHandle } from "./erd-adapter";
import { fallbackGridLayout, layoutErdGraph } from "./erd-layout";
import { erdFixture, stressGraph } from "./erd-test-fixtures";
import type { ErdFilters } from "./erd-types";

const allFilters: ErdFilters = {
  minConfidence: 0,
  schemas: ["APP", "CORE"],
  validationStatus: "",
  crossSchemaOnly: false,
};

function build(overrides: Partial<ErdFilters> = {}, focus: string | null = null) {
  return buildErdVisualization(
    erdFixture(),
    { ...allFilters, ...overrides },
    new Set(),
    focus,
    null,
    null,
  );
}

describe("ERD graph adapter", () => {
  it("maps table nodes and anchors edges to the actual connected columns", () => {
    const graph = erdFixture();
    const result = build();
    const request = result.nodes.find((node) => node.data.table.table_name === "REQUEST")!;
    const edge = result.edges.find((item) => item.data!.relationship.confidence_score === 96)!;

    expect(request.data.visibleColumns.some((column) => column.name === "PARTY_ID")).toBe(true);
    expect(request.data.visibleColumns.find((column) => column.name === "ID")!.primary_key).toBe(
      true,
    );
    expect(edge.source).toBe(graph.tables[0]!.id);
    expect(edge.target).toBe(graph.tables[1]!.id);
    expect(edge.sourceHandle).toBe(columnHandle("source", "PARTY_ID"));
    expect(edge.targetHandle).toBe(columnHandle("target", "ID"));

    const selected = buildErdVisualization(
      graph,
      allFilters,
      new Set(),
      null,
      graph.tables[0]!.id,
      null,
    );
    expect(selected.edges.filter((item) => item.data!.highlighted)).toHaveLength(2);
  });

  it("keeps unknown cardinality edges and applies confidence, validation, schema and cross-schema filters", () => {
    const unknown = build().edges.find(
      (edge) => edge.data!.relationship.cardinality === "Unknown / Insufficient Evidence",
    );
    expect(unknown).toBeDefined();
    expect(build({ minConfidence: 80 }).edges).toHaveLength(1);
    expect(build({ validationStatus: "NOT_RUN" }).edges).toHaveLength(1);
    expect(build({ schemas: ["APP"] }).edges).toHaveLength(2);
    expect(build({ crossSchemaOnly: true }).edges).toHaveLength(1);
  });

  it("focuses a table and its one-hop incoming/outgoing neighbors", () => {
    const graph = erdFixture();
    const focused = build({}, graph.tables[0]!.id);
    expect(focused.edges).toHaveLength(2);
    expect(focused.nodes.map((node) => node.data.table.table_name).sort()).toEqual([
      "AUDIT",
      "PARTY",
      "REQUEST",
    ]);
    expect(focused.focusHasNeighbors).toBe(true);

    const isolated = build({ validationStatus: "FAILED" }, graph.tables[0]!.id);
    expect(isolated.nodes).toHaveLength(1);
    expect(isolated.edges).toHaveLength(0);
    expect(isolated.focusHasNeighbors).toBe(false);
  });

  it("preserves key and connected columns while collapsing large tables", () => {
    const graph = erdFixture();
    const collapsed = buildErdVisualization(graph, allFilters, new Set(), null, null, null);
    const request = collapsed.nodes.find((node) => node.data.table.table_name === "REQUEST")!;
    expect(request.data.visibleColumns).toHaveLength(10);
    expect(request.data.hiddenColumnCount).toBe(6);

    const expanded = buildErdVisualization(
      graph,
      allFilters,
      new Set([graph.tables[0]!.id]),
      null,
      null,
      null,
    );
    expect(
      expanded.nodes.find((node) => node.data.table.table_name === "REQUEST")!.data.visibleColumns,
    ).toHaveLength(16);
  });
});

describe("ELK layout adapter", () => {
  it("is deterministic for identical graph input", async () => {
    const visualization = build();
    const first = await layoutErdGraph(visualization.nodes, visualization.edges);
    const second = await layoutErdGraph(visualization.nodes, visualization.edges);
    expect(first.map((node) => node.position)).toEqual(second.map((node) => node.position));
  });

  it.each([
    [25, 50],
    [75, 300],
    [150, 600],
  ])(
    "lays out representative %i-table / %i-edge graphs",
    async (tables, edges) => {
      const graph = stressGraph(tables, edges);
      const filters = { ...allFilters, schemas: [...graph.schemas] };
      const visualization = buildErdVisualization(graph, filters, new Set(), null, null, null);
      const started = performance.now();
      const layouted = await layoutErdGraph(visualization.nodes, visualization.edges);
      const duration = performance.now() - started;
      console.info(`ERD_PERF tables=${tables} edges=${edges} layout_ms=${duration.toFixed(1)}`);
      expect(layouted).toHaveLength(tables);
      expect(layouted.every((node) => Number.isFinite(node.position.x))).toBe(true);
      expect(duration).toBeLessThan(15_000);
      expect(fallbackGridLayout(layouted)).toHaveLength(tables);
    },
    20_000,
  );
});
