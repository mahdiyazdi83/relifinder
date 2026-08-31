import { expect, test } from "@playwright/test";

test("connects, discovers schemas, selects, and reaches continue-ready state", async ({ page }) => {
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
        connection_id: "opaque-playwright-session-12345678901234567890",
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
        connection_id: "opaque-playwright-session-12345678901234567890",
        schemas: [
          { name: "APP", table_count: 12, column_count: 84, oracle_maintained: false },
          { name: "CORE", table_count: 7, column_count: 39, oracle_maintained: false },
        ],
      }),
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
  await expect(page.getByText("APP")).toBeHidden();
  await page.getByRole("checkbox", { name: /CORE/ }).check();
  await expect(page.getByText("1 schema selected · 7 tables")).toBeVisible();
  await expect(page.getByText("Ready to configure analysis")).toBeVisible();
  await expect(page.getByRole("button", { name: /Continue/ })).toBeEnabled();
});
