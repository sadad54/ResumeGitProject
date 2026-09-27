import type { Page, Route } from "@playwright/test";

/**
 * Shared API fixture for the browser specs that don't run a backend. Shapes
 * follow the OpenAPI document (src/lib/api-types.generated.ts); a blanket
 * `[]` for every route stopped working once the app read the session from
 * /auth/me and the overview from /me/overview.
 */
export const USER = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "fixture@example.com",
  display_name: null,
  created_at: "2026-09-01T00:00:00Z",
  is_demo: false,
};

export const OVERVIEW = {
  github: {
    connected: true,
    login: "fixture",
    connected_at: "2026-09-01T00:00:00Z",
    last_sync_at: null,
  },
  repositories: { total: 1, selected: 1, synced: 1 },
  evidence: { total: 0, confirmed: 0, candidate: 0, stale: 0 },
  jobs: { total: 0, ready: 0 },
  documents: { total: 0, exported: 0 },
  applications: { total: 0, active: 0 },
};

/** Return from an override that fulfilled the route itself (e.g. a 401). */
export const HANDLED = Symbol("handled");

type Override = (path: string, route: Route) => unknown;

/**
 * Signs the page in with fixture tokens and answers every /api/v1 call:
 * `override` first (return undefined to fall through), then the session and
 * overview shapes above, then `[]` for list endpoints.
 */
export async function mockApi(
  page: Page,
  override?: Override,
  options: { user?: Record<string, unknown> | null } = {},
) {
  if (options.user !== null) {
    await page.addInitScript(() => {
      localStorage.setItem("proofhire.access_token", "fixture-token");
      localStorage.setItem("proofhire.refresh_token", "fixture-refresh");
    });
  }
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const custom = override?.(path, route);
    if (custom === HANDLED) return;
    if (custom !== undefined) return route.fulfill({ json: custom });
    if (path.endsWith("/auth/me")) return route.fulfill({ json: options.user ?? USER });
    if (path.endsWith("/me/overview")) return route.fulfill({ json: OVERVIEW });
    return route.fulfill({ json: [] });
  });
}
