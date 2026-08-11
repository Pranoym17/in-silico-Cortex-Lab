import { expect, test } from "@playwright/test";

test("landing page exposes the real product entry points", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Cortex Lab", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: /Build an experiment/i })).toHaveAttribute("href", "/dashboard");
  await expect(page.locator(".landing-brain-canvas canvas")).toBeVisible();

  await page.getByRole("button", { name: "Text" }).click();
  await expect(page.getByRole("status")).toContainText("Ready to compose with: Text");
  await expect(page.getByRole("link", { name: /Open workspace/i })).toHaveAttribute("href", "/dashboard");

  const canvasBox = await page.locator(".landing-brain-canvas canvas").boundingBox();
  expect(canvasBox?.width).toBeGreaterThan(200);
  expect(canvasBox?.height).toBeGreaterThan(200);

  await page.getByRole("link", { name: /Browse FFA faces versus houses/i }).click();
  await expect(page).toHaveURL(/\/library$/);
});

test("landing navigation works on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toContainText("Build an experiment");
});

test("public information routes remain available", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: /Research data should remain under deliberate control/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Terms" })).toBeVisible();
});
