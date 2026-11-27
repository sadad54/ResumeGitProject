import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mocks";

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

// Baselines are desktop-only, and CI compares only the desktop project. A
// local full run would otherwise write (and pass) unreviewed mobile
// baselines that nothing ever checks.
test.skip(({ isMobile }) => !!isMobile, "visual baselines are desktop-only");

// Anti-aliasing and sub-pixel text differences across Chromium builds are
// noise; a real regression moves far more than 1% of pixels.
const SCREENSHOT = { fullPage: true, animations: "disabled", maxDiffPixelRatio: 0.01 } as const;

test.describe("signed in", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  for (const route of routes) {
    test(`page ${route} matches baseline`, async ({ page }) => {
      await page.goto(route, { waitUntil: "networkidle" });
      await expect(page).toHaveScreenshot(
        `${route === "/" ? "home" : route.slice(1)}.png`,
        SCREENSHOT,
      );
    });
  }
});

test("page / signed out (landing) matches baseline", async ({ page }) => {
  await mockApi(page, undefined, { user: null });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page).toHaveScreenshot("landing.png", SCREENSHOT);
});
