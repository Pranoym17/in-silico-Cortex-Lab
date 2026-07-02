import { createHmac, randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { expect, Page, test } from "@playwright/test";

let cleanupExperiment: { id: string; token: string } | null = null;

function readEnv(filePath: string) {
  const values: Record<string, string> = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [name, ...parts] = line.split("=");
    values[name.trim()] = parts.join("=").trim().replace(/^['"]|['"]$/g, "");
  }
  return values;
}

function encode(value: unknown) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function createTestToken() {
  const envPath = path.resolve(__dirname, "../../backend/.env");
  const env = {
    ...(fs.existsSync(envPath) ? readEnv(envPath) : {}),
    ...process.env
  };
  if (!env.SUPABASE_JWT_SECRET) {
    throw new Error("SUPABASE_JWT_SECRET is required for local authenticated browser tests");
  }
  const now = Math.floor(Date.now() / 1000);
  const header = encode({ alg: "HS256", typ: "JWT" });
  const payload = encode({
    sub: `playwright-${randomUUID()}`,
    email: "playwright@cortex.local",
    iat: now,
    exp: now + 3600,
    ...(env.SUPABASE_JWT_AUDIENCE ? { aud: env.SUPABASE_JWT_AUDIENCE } : {}),
    ...(env.SUPABASE_JWT_ISSUER ? { iss: env.SUPABASE_JWT_ISSUER } : {})
  });
  const signature = createHmac("sha256", env.SUPABASE_JWT_SECRET)
    .update(`${header}.${payload}`)
    .digest("base64url");
  return `${header}.${payload}.${signature}`;
}

async function openFreshBuilder(page: Page) {
  const token = createTestToken();
  await page.goto("/dashboard");
  await page.getByLabel("Access token").fill(token);
  await page.getByRole("button", { name: "Use token" }).click();
  await expect(page.getByText("Authenticated session")).toBeVisible();
  const experimentName = `Browser QA ${Date.now()} ${randomUUID().slice(0, 8)}`;
  await page.getByLabel("Experiment name").fill(experimentName);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  const experimentRow = page.locator(".experiment-row").filter({ hasText: experimentName });
  await expect(experimentRow).toBeVisible();
  await experimentRow.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/builder\/[0-9a-f-]+$/);
  const experimentId = page.url().split("/").pop();
  if (!experimentId) throw new Error("Builder URL did not contain an experiment ID");
  cleanupExperiment = { id: experimentId, token };
  await expect(page.getByRole("heading", { name: "Timeline" })).toBeVisible();
}

test.afterEach(async ({ request }) => {
  if (!cleanupExperiment) return;
  await request.delete(`http://localhost:8001/api/experiments/${cleanupExperiment.id}`, {
    headers: { authorization: `Bearer ${cleanupExperiment.token}` }
  });
  cleanupExperiment = null;
});

test("builder supports keyboard timing, history, zoom, and playback", async ({ page }) => {
  await openFreshBuilder(page);
  await page.getByRole("button", { name: "Text", exact: true }).click();

  const block = page.getByRole("button", { name: /text block, starts at 0 milliseconds/i });
  await expect(block).toBeVisible();
  await block.focus();
  await block.press("ArrowRight");
  await expect(page.getByText(/text at 500ms for 5000ms/i)).toBeVisible();

  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText(/text at 0ms for 5000ms/i)).toBeVisible();
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(page.getByText(/text at 500ms for 5000ms/i)).toBeVisible();

  await expect(page.locator(".timeline-zoom-controls output")).toHaveText("80%");
  await page.getByRole("button", { name: "Zoom timeline in" }).click();
  await expect(page.locator(".timeline-zoom-controls output")).toHaveText("100%");

  await page.getByRole("button", { name: "Play stimulus playback" }).click();
  await expect(page.locator(".builder-playback-word-active")).toBeVisible();
  await page.getByRole("button", { name: "Pause stimulus playback" }).click();
});

test("microphone denial is explained and mobile layout stays within the viewport", async ({ page, context }) => {
  await context.clearPermissions();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          throw new DOMException("Permission denied by browser QA", "NotAllowedError");
        }
      }
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await openFreshBuilder(page);
  await page.getByRole("button", { name: "Audio", exact: true }).click();
  await page.getByRole("button", { name: "Record microphone" }).click();
  await expect(
    page.getByText(/microphone access was denied|could not access the microphone|recording is not supported/i)
  ).toBeVisible();

  const workspace = page.locator(".builder-workspace");
  const box = await workspace.boundingBox();
  expect(box).not.toBeNull();
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(392);
  await expect(page.getByRole("button", { name: "Zoom timeline in" })).toBeVisible();
});
