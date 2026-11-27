import { defineConfig, devices } from "@playwright/test";

// Configurable because reuseExistingServer (below) will happily run the suite
// against whatever already listens on the port — which, on a machine running
// another project's dev server on :3000, was a different app entirely.
const PORT = process.env.PLAYWRIGHT_PORT ?? "3000";
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
      args: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
        ? ["--no-sandbox", "--disable-dev-shm-usage"]
        : [],
    },
  },
  webServer: {
    command: `npm run start -- --hostname 127.0.0.1 --port ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
});
