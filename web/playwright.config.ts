// End-to-end tests: a real browser against a real Next server and a real FastAPI, on their own ports and
// their own freshly seeded database (canyon_e2e). Run with `npm run e2e` from web/.
import { defineConfig, devices } from "@playwright/test";

import { API_PORT, API_URL, WEB_PORT, WEB_URL, e2eDatabaseUrl } from "./e2e/env";

export default defineConfig({
  testDir: "./e2e",
  // One worker, in order: the tests share one database and one of them changes it.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  timeout: 60_000, // the dev server compiles each page on its first visit
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: WEB_URL,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "node ../web/e2e/start-api.mjs",
      cwd: "../api",
      url: `${API_URL}/health`,
      env: { DATABASE_URL: e2eDatabaseUrl(), DEV_AUTH: "true", DEMO_MODE: "false", API_PORT: String(API_PORT) },
      reuseExistingServer: false, // always reseed
      timeout: 120_000,
    },
    {
      command: `npx next dev --port ${WEB_PORT}`,
      url: WEB_URL,
      env: { API_URL, NEXT_DIST_DIR: ".next-e2e", DEMO_MODE: "false" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
