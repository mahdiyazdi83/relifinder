import { expect, test, type Page, type TestInfo } from "@playwright/test";

async function captureVisual(
  page: Page,
  testInfo: TestInfo,
  name: string,
  width: number,
  height: number,
) {
  if (!process.env.RELIFINDER_VISUAL_QA) return;
  await page.setViewportSize({ width, height });
  await page.screenshot({ path: testInfo.outputPath(`${name}-${width}.png`), fullPage: true });
}

test("connects, configures Balanced, runs analysis, and reaches results", async ({
  page,
  context,
}, testInfo) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["warning", "error"].includes(message.type())) consoleProblems.push(message.text());
  });
  page.on("pageerror", (error) => consoleProblems.push(error.message));

  const connectionId = "opaque-playwright-session-12345678901234567890";
  const runId = "opaque-playwright-run-1234567890123456789012";

  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", application: "relifinder" }),
    });
  });
  await page.route("**/api/connections", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        connection_id: connectionId,
        status: "connected",
        expires_in_seconds: 900,
        checks: [
          { key: "oracle_connection", label: "Oracle connection", status: "available" },
          { key: "metadata_visibility", label: "Metadata visibility", status: "available" },
          { key: "schema_discovery", label: "Schema discovery", status: "available" },
        ],
      }),
    });
  });
  await page.route("**/api/connections/*/schemas", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        connection_id: connectionId,
        schemas: [
          { name: "APP", table_count: 12, column_count: 84, oracle_maintained: false },
          { name: "CORE", table_count: 7, column_count: 39, oracle_maintained: false },
        ],
      }),
    });
  });
  await page.route("**/api/runs", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ run_id: runId, status: "QUEUED" }),
    });
  });
  await page.route("**/api/runs/*/events", async (route) => {
    const completed = {
      sequence: 8,
      run_id: runId,
      state: "COMPLETED",
      message: "Analysis completed",
      current: null,
      total: null,
      stats: {
        schemas: 1,
        tables: 7,
        columns: 39,
        candidates_generated: 42,
        candidates_validated: 30,
        candidates_skipped: 2,
        relationships_in_report: 18,
      },
      summary: {
        schemas_analyzed: 1,
        tables: 7,
        columns: 39,
        candidates_generated: 42,
        candidates_validated: 30,
        candidates_skipped: 2,
        relationships_in_report: 18,
        run_mode: "sampled",
        elapsed_seconds: 4.2,
      },
      error_code: null,
    };
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: { "Cache-Control": "no-cache" },
      body: `id: 8\nevent: progress\ndata: ${JSON.stringify(completed)}\n\n`,
    });
  });
  const relationshipId = "c".repeat(64);
  const relationship = {
    id: relationshipId,
    source: {
      schema_name: "CORE",
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
    cross_schema: false,
    target_key_type: "PRIMARY_KEY",
  };
  await page.route("**/api/runs/*/relationships", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        summary: {
          schemas_analyzed: 1,
          tables: 7,
          columns: 39,
          candidates_generated: 42,
          candidates_validated: 30,
          candidates_skipped: 2,
          relationships_in_report: 1,
          run_mode: "sampled",
          elapsed_seconds: 4.2,
        },
        total: 1,
        relationships: [relationship],
      }),
    });
  });
  await page.route("**/api/runs/*/relationships/*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...relationship,
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
        explanation: "Strong bounded evidence supports this relationship.",
      }),
    });
  });

  await page.route("**/api/runs/*/erd", async (route) => {
    const column = (name: string, position: number, primaryKey = false) => ({
      name,
      datatype: "NUMBER",
      nullable: !primaryKey,
      position,
      primary_key: primaryKey,
      unique_key: false,
      composite_key: false,
      relationship_connected: name === "CUSTOMER_ID" || name === "ID",
    });
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        default_min_confidence: 60,
        schemas: ["CORE"],
        tables: [
          {
            id: "d".repeat(64),
            schema_name: "CORE",
            table_name: "ORDERS",
            estimated_rows: 2000,
            columns: [column("ID", 1, true), column("CUSTOMER_ID", 2)],
          },
          {
            id: "e".repeat(64),
            schema_name: "CORE",
            table_name: "CUSTOMERS",
            estimated_rows: 400,
            columns: [column("ID", 1, true), column("NAME", 2)],
          },
        ],
        relationships: [relationship],
      }),
    });
  });

  const dbml =
    "// Generated by ReliFinder\n// Minimum confidence: 80\n// Scope: full\n// Eligible after filters/limit: 1\n// Rendered DBML references: 1\n// Unknown cardinality omitted: 0\n\nProject ReliFinder_ERD {\n  database_type: ''Oracle''\n}\n";
  await page.route("**/api/runs/*/artifacts", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        artifacts: [
          {
            id: "relationships-csv",
            type: "csv",
            filename: "relationships.csv",
            available: true,
            size_bytes: 256,
          },
          {
            id: "analysis-html",
            type: "html",
            filename: "relationship-report.html",
            available: true,
            size_bytes: 512,
          },
          {
            id: "erd-dbml",
            type: "dbml",
            filename: "full.dbml",
            available: true,
            size_bytes: dbml.length,
            scope: "full",
            min_confidence: 80,
            eligible_relationships: 1,
            rendered_relationships: 1,
            unknown_cardinality_omitted: 0,
          },
        ],
      }),
    });
  });
  await page.route("**/api/runs/*/artifacts/erd-dbml**", async (route) => {
    const download = new URL(route.request().url()).searchParams.get("download") === "true";
    await route.fulfill({
      contentType: "text/plain",
      headers: download ? { "Content-Disposition": 'attachment; filename="full.dbml"' } : {},
      body: dbml,
    });
  });
  await page.route("**/api/runs/*/artifacts/analysis-html**", async (route) => {
    const download = new URL(route.request().url()).searchParams.get("download") === "true";
    await route.fulfill({
      contentType: "text/html",
      headers: download
        ? { "Content-Disposition": 'attachment; filename="relationship-report.html"' }
        : {},
      body: "<!doctype html><html><body><h1>Relationship Discovery</h1></body></html>",
    });
  });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await captureVisual(page, testInfo, "connection-dark", 1366, 768);
  await page.getByLabel("Host").fill("db.example.invalid");
  await page.getByLabel("Service name").fill("FAKE_SERVICE");
  await page.getByLabel("Username").fill("FAKE_USER");
  await page.getByLabel("Password", { exact: true }).fill("fake-playwright-password");
  await page.getByRole("button", { name: "Test connection" }).click();

  await expect(page.getByRole("heading", { name: "Accessible schemas" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search schemas" }).fill("CORE");
  await page.getByRole("checkbox", { name: /CORE/ }).check();
  await page.getByRole("button", { name: /Continue/ }).click();

  await expect(page.getByRole("heading", { name: "Analysis Configuration" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Balanced/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: "Run Analysis" }).click();

  await expect(page.getByRole("heading", { name: "Completed" })).toBeVisible();
  await expect(page.getByText("18")).toBeVisible();
  await captureVisual(page, testInfo, "analysis-complete-dark", 1440, 900);
  await page.getByRole("button", { name: "View Results" }).click();
  await expect(page.getByRole("heading", { name: "Relationship Explorer" })).toBeVisible();
  await expect(page.getByText("CORE.ORDERS")).toBeVisible();
  await page.getByText("CORE.ORDERS").click();
  await expect(page.getByRole("heading", { name: "Score evidence" })).toBeVisible();
  await expect(page.getByText("Strong bounded evidence supports this relationship.")).toBeVisible();
  await captureVisual(page, testInfo, "results-dark", 1440, 900);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("complementary", { name: "Relationship inspector" })).toBeVisible();
  await page.getByRole("button", { name: "Close inspector" }).click();
  await expect(page.getByText("Select a relationship")).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("link", { name: "Open ERD" }).click();
  await expect(page.getByRole("heading", { name: "Interactive ERD" })).toBeVisible();
  await expect(page.getByText("2 tables · 1 relationships")).toBeVisible();

  await page.getByLabel("ERD minimum confidence").fill("97");
  await expect(
    page.getByRole("heading", { name: "ERD has no visible relationships" }),
  ).toBeVisible();
  await page.getByLabel("ERD minimum confidence").fill("60");
  await expect(page.getByText("2 tables · 1 relationships")).toBeVisible();

  await page.getByText(/Schemas 1\/1/).click();
  await page.getByRole("checkbox", { name: "CORE" }).uncheck();
  await expect(
    page.getByRole("heading", { name: "ERD has no visible relationships" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "All schemas" }).click();
  await expect(page.getByText("2 tables · 1 relationships")).toBeVisible();

  await captureVisual(page, testInfo, "erd-overview-dark", 1440, 900);
  await page.getByTestId(`erd-edge-${relationshipId}`).dispatchEvent("click");
  await expect(page.getByRole("heading", { name: "Score evidence" })).toBeVisible();
  await expect(page.getByText("Strong bounded evidence supports this relationship.")).toBeVisible();
  await captureVisual(page, testInfo, "erd-inspector-dark", 1440, 900);
  await page.getByRole("button", { name: "Close inspector" }).click();

  await page.getByText("ORDERS", { exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Table inspector" })).toBeVisible();
  await page.getByRole("button", { name: "Focus table (1 hop)" }).click();
  await expect(page.getByRole("button", { name: "Exit Focus" })).toBeVisible();
  await page.getByRole("button", { name: "Exit Focus" }).click();
  await expect(page.getByText("2 tables · 1 relationships")).toBeVisible();
  await captureVisual(page, testInfo, "erd-dark", 1920, 1080);
  await page.waitForTimeout(1100); // Let React Flow complete its delayed attribution visibility audit.
  await page.getByRole("link", { name: "DBML & Exports" }).click();
  await expect(page.getByRole("heading", { name: "Artifacts & DBML" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "DBML Code" })).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await captureVisual(page, testInfo, "exports-light", 1366, 768);
  await page.getByRole("button", { name: "Copy" }).click();
  await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();

  await expect(page.getByRole("link", { name: "Download DBML" }).last()).toHaveAttribute(
    "href",
    new RegExp(`/api/runs/${runId}/artifacts/erd-dbml\\?download=true$`),
  );

  const reportLink = page.getByRole("link", { name: "Open Report" });
  await expect(reportLink).toHaveAttribute(
    "href",
    new RegExp(`/api/runs/${runId}/artifacts/analysis-html$`),
  );
  await expect(reportLink).toHaveAttribute("target", "_blank");

  await expect(page.getByRole("link", { name: "Download HTML" })).toHaveAttribute(
    "href",
    new RegExp(`/api/runs/${runId}/artifacts/analysis-html\\?download=true$`),
  );
  expect(consoleProblems).toEqual([]);
});
