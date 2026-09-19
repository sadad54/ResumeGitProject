import { test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

/**
 * Initial JavaScript payload per route (checklist Track D "Frontend").
 * Sums the transfer size of every script the browser fetched to reach a
 * loaded page — what a user actually downloads, measured against the
 * production build the Playwright webServer runs.
 */
const ROUTES = ["/", "/evidence", "/jobs", "/documents", "/applications", "/settings"];

// One measurement per build is enough; the mobile project would duplicate it.
test.skip(({ isMobile }) => !!isMobile, "measured once, on desktop");

test("initial JS payload per route", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("proofhire.access_token", "fixture-token"));
  await page.route("**/api/v1/**", (route) => route.fulfill({ json: [] }));
  const results: Record<string, unknown>[] = [];
  for (const path of ROUTES) {
    const scripts: { url: string; bytes: number }[] = [];
    const onResponse = async (r: import("@playwright/test").Response) => {
      const ct = r.headers()["content-type"] || "";
      if (r.url().includes("/_next/static/") && ct.includes("javascript")) {
        try {
          const body = await r.body();
          scripts.push({ url: new URL(r.url()).pathname, bytes: body.length });
        } catch {
          /* response body unavailable (cached/aborted) */
        }
      }
    };
    page.on("response", onResponse);
    await page.goto(path, { waitUntil: "networkidle" });
    page.off("response", onResponse);
    const total = scripts.reduce((a, s) => a + s.bytes, 0);
    results.push({ route: path, script_count: scripts.length, js_bytes_uncompressed: total, js_kib: Math.round(total / 1024) });
  }
  mkdirSync("test-results", { recursive: true });
  writeFileSync("test-results/js-payload.json", JSON.stringify({ measured_at: new Date().toISOString(), note: "Uncompressed bytes of /_next/static JS fetched on a cold navigation to each route, production build.", results }, null, 2));
  console.log(JSON.stringify(results));
});
