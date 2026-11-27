import { expect, test, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { HANDLED, mockApi, OVERVIEW, USER } from "./api-mocks";

/**
 * Session behaviour the backend contract depends on (lib/api.ts,
 * lib/session.tsx), exercised in a real browser with the API mocked at the
 * network layer. The real-backend journey is in fullstack.spec.ts.
 */

test("signed-out visitors get the landing page with sign-in and the demo", async ({ page }) => {
  await mockApi(page, undefined, { user: null });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Every resume claim, traced to the code that proves it",
  );
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: /Explore the live demo/ })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("an expired access token is renewed once, transparently, for concurrent requests", async ({
  page,
}) => {
  let refreshCalls = 0;
  const expiredCalls: string[] = [];
  await mockApi(page, (path, route: Route) => {
    if (path.endsWith("/auth/refresh")) {
      refreshCalls += 1;
      return { access_token: "fresh-token", refresh_token: "fresh-refresh", token_type: "bearer" };
    }
    if (path.endsWith("/auth/me")) return undefined; // the session itself is still valid
    // The access token expires just after sign-in: the evidence page's three
    // parallel queries all hit a 401 together.
    if (route.request().headers()["authorization"] !== "Bearer fresh-token") {
      expiredCalls.push(path);
      void route.fulfill({ status: 401, json: { detail: "Invalid or expired token" } });
      return HANDLED;
    }
    if (path.endsWith("/evidence/graph"))
      return { nodes: [], edges: [], job_id: null, job_status: null, truncated: false, evidence_limit: 200 };
    return undefined;
  });
  await page.goto("/evidence");
  await expect(page.getByText(/No evidence yet/)).toBeVisible();
  expect(expiredCalls.length).toBeGreaterThanOrEqual(3);
  // Rotation makes a second concurrent refresh fatal (the spent token is
  // revoked), so all of them must share one.
  expect(refreshCalls).toBe(1);
  expect(await page.evaluate(() => localStorage.getItem("proofhire.refresh_token"))).toBe(
    "fresh-refresh",
  );
});

test("a session that can't be renewed ends visibly", async ({ page }) => {
  await mockApi(page, (path, route: Route) => {
    if (path.endsWith("/auth/refresh")) {
      void route.fulfill({ status: 401, json: { detail: "Refresh token has been revoked" } });
      return HANDLED;
    }
    void route.fulfill({ status: 401, json: { detail: "Invalid or expired token" } });
    return HANDLED;
  });
  await page.goto("/evidence");
  await expect(page.getByRole("alert").filter({ hasText: "Your session ended" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sign in to review your evidence" })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("proofhire.access_token"))).toBeNull();
});

test("sign-out revokes the session server-side before forgetting it", async ({ page }) => {
  let logoutBody: unknown = null;
  await mockApi(page, (path, route: Route) => {
    if (path.endsWith("/auth/logout")) {
      logoutBody = route.request().postDataJSON();
      void route.fulfill({ status: 204, body: "" });
      return HANDLED;
    }
    return undefined;
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Every resume claim");
  expect(logoutBody).toEqual({ refresh_token: "fixture-refresh" });
  expect(await page.evaluate(() => localStorage.getItem("proofhire.refresh_token"))).toBeNull();
});

test("the demo account is visibly read-only", async ({ page }) => {
  await mockApi(page, undefined, { user: { ...USER, email: "demo@proofhire.app", is_demo: true } });
  await page.goto("/documents");
  await expect(page.getByRole("note").filter({ hasText: "read-only demo" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Generate/ })).toBeDisabled();
  // Hidden (not removed) on narrow screens to save top-bar space.
  await expect(page.locator(".ph-user-name")).toHaveText("Demo guest");
});

test("an unreachable API reads as waking up, not signed out", async ({ page }) => {
  await mockApi(page, (path, route: Route) => {
    if (path.endsWith("/auth/me")) {
      void route.fulfill({ status: 503, body: "Service Unavailable" });
      return HANDLED;
    }
    return undefined;
  });
  await page.goto("/");
  await expect(page.getByText(/Connecting to the ProofHire API/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByLabel("Email")).toHaveCount(0);
});

test("the OAuth callback outcome is explained on Settings", async ({ page }) => {
  await mockApi(page);
  await page.goto("/settings?github=denied");
  await expect(page.getByRole("alert").filter({ hasText: "access wasn't granted" })).toBeVisible();
  await page.goto("/settings?github=connected");
  await expect(page.getByRole("status").filter({ hasText: "GitHub connected" })).toBeVisible();
});

test("server errors show the message, not raw JSON", async ({ page }) => {
  await mockApi(page, undefined, { user: null });
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ status: 401, json: { detail: "Invalid email or password" } }),
  );
  await page.goto("/");
  await page.getByLabel("Email").fill("someone@example.com");
  await page.getByLabel(/^Password/).fill("not-the-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  // Exactly the server's detail — not the raw {"detail": ...} body.
  await expect(page.locator("p.ph-error[role=alert]")).toHaveText("Invalid email or password");
});

test.describe("overview", () => {
  test("counts link to where the work happens", async ({ page }) => {
    await mockApi(page, (path) =>
      path.endsWith("/me/overview")
        ? { ...OVERVIEW, evidence: { total: 12, confirmed: 7, candidate: 5, stale: 0 } }
        : undefined,
    );
    await page.goto("/");
    await expect(page.getByText("5 awaiting review")).toBeVisible();
    await expect(page.getByRole("link", { name: /Next: Analyze a job/ })).toHaveAttribute(
      "href",
      "/jobs",
    );
  });
});
