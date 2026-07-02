import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command: ".venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
      cwd: path.resolve(__dirname, "../backend"),
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: true,
      timeout: 60_000
    },
    {
      command: "node node_modules/next/dist/bin/next dev --hostname localhost --port 3000",
      cwd: __dirname,
      env: {
        NEXT_PUBLIC_SUPABASE_URL: "",
        NEXT_PUBLIC_SUPABASE_ANON_KEY: "",
        NEXT_PUBLIC_API_URL: "http://localhost:8001",
        NEXT_PUBLIC_SITE_URL: "http://localhost:3000"
      },
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 90_000
    }
  ],
  projects: [
    {
      name: "chrome",
      use: { ...devices["Desktop Chrome"], channel: "chrome" }
    },
    {
      name: "edge",
      use: { ...devices["Desktop Edge"], channel: "msedge" }
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] }
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] }
    }
  ]
});
