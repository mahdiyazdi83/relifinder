import { expect, test } from "@playwright/test";

test("frontend loads the ReliFinder application shell", async ({ page }) => {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", application: "relifinder" }),
    });
  });

  await page.goto("/");

  await expect(page.getByText("ReliFinder", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ReliFinder workbench" })).toBeVisible();
  await expect(page.getByText("Local Core: Healthy")).toBeVisible();
});
