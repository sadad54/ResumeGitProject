import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const source = {
  locator: "src/api.py#L12-L38",
  url: "https://github.com/fixture/api/blob/abc/src/api.py#L12-L38",
  commit_sha: "abc123456789",
  line_start: 12,
  line_end: 38,
};
const node = (id: string, kind: string, label: string, extra = {}) => ({
  id,
  kind,
  label,
  description: "",
  status: null,
  confidence: null,
  repository_id: null,
  evidence_id: null,
  required: null,
  sources: [],
  ...extra,
});
const graph = {
  nodes: [
    node("project:1", "project", "sadad54 / ProofHire"),
    node("evidence:1", "architecture", "Source-backed API architecture", {
      status: "confirmed",
      confidence: 0.92,
      evidence_id: "1",
      description: "A modular FastAPI service with explicit ownership checks.",
      sources: [source],
    }),
    node("evidence:2", "evidence", "Deterministic claim verification", {
      status: "confirmed",
      confidence: 0.96,
      evidence_id: "2",
      sources: [{ ...source, locator: "tests/test_fact_guard.py#L1-L72" }],
    }),
    node("skill:1", "skill", "FastAPI"),
    node("skill:2", "skill", "Python"),
    node("requirement:1", "requirement", "Build production APIs", {
      status: "partial",
      required: true,
      description: "Required · experience",
    }),
    node("requirement:2", "requirement", "Operate Kubernetes clusters", {
      status: "gap",
      required: false,
      description: "Preferred · tooling",
    }),
  ],
  edges: [
    {
      id: "a",
      source: "project:1",
      target: "evidence:1",
      kind: "contains",
      weight: 0.9,
      status: null,
      explanation: "",
    },
    {
      id: "b",
      source: "evidence:1",
      target: "skill:1",
      kind: "demonstrates",
      weight: 0.9,
      status: null,
      explanation: "",
    },
    {
      id: "c",
      source: "evidence:1",
      target: "requirement:1",
      kind: "matches",
      weight: 0.6,
      status: "partial",
      explanation:
        "Implementation is shown; production operation is not established.",
    },
    {
      id: "d",
      source: "project:1",
      target: "evidence:2",
      kind: "contains",
      weight: 0.96,
      status: null,
      explanation: "",
    },
    {
      id: "e",
      source: "evidence:2",
      target: "skill:2",
      kind: "demonstrates",
      weight: 0.9,
      status: null,
      explanation: "",
    },
  ],
  job_id: "job1",
  job_status: "ready",
  truncated: false,
  evidence_limit: 200,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("proofhire.access_token", "fixture-token"),
  );
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const body = url.pathname.endsWith("/evidence/graph")
      ? graph
      : url.pathname.endsWith("/jobs")
        ? [
            {
              id: "job1",
              role: "Backend Engineer",
              company: "Fixture",
              status: "ready",
            },
          ]
        : [];
    await route.fulfill({ json: body });
  });
});

test("source inspection and table provide the same evidence", async ({
  page,
}) => {
  await page.goto("/evidence");
  await page
    .getByRole("button", { name: "Accessible table", exact: true })
    .click();
  await expect(page.getByRole("table").first()).toContainText(
    "Source-backed API architecture",
  );
  await page
    .getByRole("button", {
      name: "Source-backed API architecture",
      exact: true,
    })
    .first()
    .click();
  const rail = page.getByRole("complementary", {
    name: "Selected node details",
  });
  await expect(rail).toContainText("92% confidence");
  await expect(rail.getByRole("link")).toHaveAttribute("href", source.url);
  await expect(page.locator("#graph-coverage")).toContainText("partial");
  await expect(page.locator("#graph-coverage")).toContainText(
    "No supporting evidence found",
  );
  const violations = (
    await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze()
  ).violations;
  expect(violations).toEqual([]);
});

test("command palette works by keyboard and restores focus", async ({
  page,
}) => {
  await page.goto("/evidence");
  const trigger = page.getByRole("button", { name: /Search & actions/ });
  await trigger.focus();
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("textbox", { name: "Search commands" }).fill("theme");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(trigger).toBeFocused();
  await page.keyboard.press("Control+k");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("graph supports reduced motion and mobile does not overflow", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/evidence");
  if (testInfo.project.name === "mobile")
    await expect(
      page.getByRole("button", { name: "Accessible table", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Constellation", exact: true })
    .click();
  await expect(page.locator(".react-flow")).toBeVisible();
  await expect(page.locator(".ph-lit-edge")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("constellation.png"),
    fullPage: true,
  });
});

test("request failure gives a recoverable error", async ({ page }) => {
  await page.route("**/api/v1/evidence/graph*", (route) =>
    route.fulfill({ status: 503, body: "Service unavailable" }),
  );
  await page.goto("/evidence");
  await expect(page.locator(".ph-error")).toContainText("Service unavailable");
  await page.unroute("**/api/v1/evidence/graph*");
  await page.getByRole("button", { name: "Refresh graph" }).click();
  await expect(page.locator(".ph-error")).toHaveCount(0);
});
