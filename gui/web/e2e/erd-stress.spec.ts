import { expect, test } from "@playwright/test";

import { stressGraph } from "../src/features/erd/erd-test-fixtures";

for (const [tables, edges] of [
  [25, 50],
  [75, 300],
  [150, 600],
] as const) {
  test(`ERD remains usable with ${tables} tables and ${edges} relationships`, async ({ page }) => {
    const graph = stressGraph(tables, edges);
    await page.route("**/api/health", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", application: "relifinder" }),
      });
    });
    await page.route("**/api/runs/*/erd", async (route) => {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(graph) });
    });

    const started = performance.now();
    await page.goto(`/erd?run=${graph.run_id}`);
    await expect(page.getByRole("heading", { name: "Interactive ERD" })).toBeVisible();
    await expect(page.getByText(`${tables} tables · ${edges} relationships`)).toBeVisible();
    await expect(page.getByRole("button", { name: "Auto Layout" })).toBeEnabled();
    const renderDuration = performance.now() - started;

    await page.getByLabel("ERD minimum confidence").fill("95");
    await expect(page.getByText(`${tables} tables · ${edges} relationships`)).not.toBeVisible();
    await expect(page.getByTestId("erd-canvas")).toBeVisible();
    console.log(
      `ERD_RENDER tables=${tables} edges=${edges} usable=true load_ms=${renderDuration.toFixed(1)}`,
    );
  });
}
