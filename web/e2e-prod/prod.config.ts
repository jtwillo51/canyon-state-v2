// THROWAWAY: rehearse the deployed demo locally (next start + an API in DEMO_MODE with DEV_AUTH off).
import { defineConfig } from "@playwright/test";
import { e2eDatabaseUrl } from "../e2e/env";
export default defineConfig({
  testDir: ".", workers: 1, timeout: 90_000, reporter: [["list"]],
  use: { baseURL: "http://localhost:3300" },
  webServer: [
    { command: "node ../web/e2e/start-api.mjs", cwd: "../../api", url: "http://localhost:8300/health", timeout: 180_000, reuseExistingServer: true,
      env: { DATABASE_URL: e2eDatabaseUrl(), DEMO_MODE: "true", DEV_AUTH: "false", API_PORT: "8300" } },
    { command: "npx next start -p 3300", cwd: "..", url: "http://localhost:3300/sign-in", timeout: 120_000, reuseExistingServer: true,
      env: { API_URL: "http://localhost:8300", DEMO_MODE: "true" } },
  ],
});
