import { expect, test } from "@playwright/test";

test("connects, configures Balanced, runs analysis, and reaches results", async ({ page }) => {
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

  await page.goto("/");
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
  await page.getByRole("button", { name: "View Results" }).click();
  await expect(
    page.getByRole("heading", { name: "Relationship results belong to Phase 4" }),
  ).toBeVisible();
});
