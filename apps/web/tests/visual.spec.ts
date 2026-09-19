import { expect, test } from "@playwright/test";

/**
 * Visual regression (checklist §18.9). Screenshot baselines live next to this
 * file under tests/visual.spec.ts-snapshots/, one per platform suffix
 * (-win32, -linux), because font rasterization differs between them and a
 * Windows baseline would fail on Linux CI for reasons that aren't regressions.
 *
 * Bootstrapping a platform: run `npx playwright test tests/visual.spec.ts
 * --update-snapshots` on it and commit the result. CI does this automatically
 * when no Linux baselines exist and uploads them as the `visual-baselines`
 * artifact for someone to commit; until then the Linux comparison is a
 * no-op, and that is stated rather than hidden.
 *
 * Animations are disabled and the API is mocked so the only thing that can
 * change between runs is the UI itself.
 */

const routes = ["/", "/evidence", "/jobs", "/documents", "/applications", "/settings"];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("proofhire.access_token", "fixture-token"));
  await page.route("**/api/v1/**", (route) => route.fulfill({ json: [] }));
  await page.emulateMedia({ reducedMotion: "reduce" });
});

for (const route of routes) {
  test(`page ${route} matches baseline`, async ({ page }) => {
    await page.goto(route, { waitUntil: "networkidle" });
    await expect(page).toHaveScreenshot(`${route === "/" ? "home" : route.slice(1)}.png`, {
      fullPage: true,
      animations: "disabled",
      // Anti-aliasing and sub-pixel text differences across Chromium builds
      // are noise; a real regression moves far more than 1% of pixels.
      maxDiffPixelRatio: 0.01,
    });
  });
}
