import { defineConfig, devices } from "@playwright/test";

// End-to-end tests against the real API and the built front end (`npm run build` first).
const PORT = 8799;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `uv run uvicorn openenergy.app:app --port ${PORT}`,
    cwd: "..",
    url: `http://127.0.0.1:${PORT}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
