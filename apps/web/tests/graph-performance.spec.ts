import { expect, test } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";

/**
 * Graph FPS at 100 / 500 / 1,000 nodes (checklist Track D "Frontend").
 *
 * Feeds a synthetic graph of the requested size through the real Evidence
 * Constellation (React Flow) and measures requestAnimationFrame throughput
 * while the viewport is panned by scripted wheel events for ~2 s. Panning is
 * the interaction that repaints every visible node each frame, so it is the
 * honest worst case for a graph view; an idle graph at 60 fps proves nothing.
 *
 * Results are written to test-results/graph-fps.json so docs/product/metrics
 * can cite a committed artifact rather than a number typed from memory.
 * Numbers are machine-dependent and the environment is recorded alongside.
 */

const SIZES = [100, 500, 1000] as const;

function syntheticGraph(nodeCount: number) {
  const nodes = [];
  const edges = [];
  const kinds = ["evidence", "skill", "architecture", "requirement"] as const;
  nodes.push({
    id: "project:1", kind: "project", label: "fixture / repo", description: "",
    status: null, confidence: null, repository_id: null, evidence_id: null,
    required: null, sources: [],
  });
  for (let i = 1; i < nodeCount; i++) {
    const kind = kinds[i % kinds.length];
    nodes.push({
      id: `${kind}:${i}`, kind, label: `${kind} ${i}`, description: "",
      status: kind === "requirement" ? (i % 3 ? "strong" : "gap") : "confirmed",
      confidence: 0.8, repository_id: null, evidence_id: kind === "evidence" ? String(i) : null,
      required: kind === "requirement" ? i % 2 === 0 : null, sources: [],
    });
    // Each node links to the project and to a previous node, so edge count
    // grows with node count the way a real evidence graph's does.
    edges.push({ id: `e${i}a`, source: "project:1", target: `${kind}:${i}`, kind: "contains", weight: 0.5, status: null });
    if (i > 1) {
      const prev = nodes[i - 1]!;
      edges.push({ id: `e${i}b`, source: prev.id, target: `${kind}:${i}`, kind: "supports", weight: 0.4, status: null });
    }
  }
  return { nodes, edges, job_id: "job1", job_status: "ready", truncated: false, evidence_limit: nodeCount };
}

const results: Record<string, unknown>[] = [];

test.describe.configure({ mode: "serial" });

for (const size of SIZES) {
  test(`graph renders and pans at ${size} nodes`, async ({ page, browserName }) => {
    const graph = syntheticGraph(size);
    await page.addInitScript(() => localStorage.setItem("proofhire.access_token", "fixture-token"));
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const body = url.pathname.endsWith("/evidence/graph")
        ? graph
        : url.pathname.endsWith("/jobs")
          ? [{ id: "job1", role: "Backend Engineer", company: "Fixture", status: "ready" }]
          : [];
      await route.fulfill({ json: body });
    });

    const t0 = Date.now();
    await page.goto("/evidence");
    await page.locator(".react-flow__node").first().waitFor({ timeout: 60_000 });
    const timeToFirstNode = Date.now() - t0;
    await page.waitForTimeout(500);

    const renderedNodes = await page.locator(".react-flow__node").count();

    const pane = page.locator(".react-flow__pane").first();
    const box = await pane.boundingBox();
    expect(box).not.toBeNull();
    const cx = box!.x + box!.width / 2;
    const cy = box!.y + box!.height / 2;

    // Count frames while panning. The counter runs in-page; wheel events are
    // driven from the test so the measurement includes real input handling.
    await page.evaluate(() => {
      const w = window as unknown as { __frames: number; __stop: boolean };
      w.__frames = 0;
      w.__stop = false;
      const tick = () => {
        if (w.__stop) return;
        w.__frames++;
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    const start = Date.now();
    await page.mouse.move(cx, cy);
    for (let i = 0; i < 40; i++) {
      await page.mouse.wheel(i % 2 ? 60 : -60, i % 3 ? 40 : -40);
      await page.waitForTimeout(50);
    }
    const elapsedMs = Date.now() - start;
    const frames = await page.evaluate(() => {
      const w = window as unknown as { __frames: number; __stop: boolean };
      w.__stop = true;
      return w.__frames;
    });
    const fps = Math.round((frames / elapsedMs) * 1000);

    results.push({
      nodes: size,
      edges: graph.edges.length,
      rendered_nodes: renderedNodes,
      time_to_first_node_ms: timeToFirstNode,
      pan_fps: fps,
      frames,
      elapsed_ms: elapsedMs,
      browser: browserName,
    });

    // Loose floor: the point is the recorded number, but a graph that drops
    // below 15 fps while panning is a defect worth failing on.
    expect(fps).toBeGreaterThanOrEqual(15);
  });
}

test.afterAll(async () => {
  mkdirSync("test-results", { recursive: true });
  writeFileSync(
    "test-results/graph-fps.json",
    JSON.stringify(
      {
        measured_at: new Date().toISOString(),
        note: "Synthetic graph; pan_fps = rAF frames during ~2s of scripted wheel panning.",
        platform: `${process.platform} ${process.arch}`,
        node: process.version,
        results,
      },
      null,
      2,
    ),
  );
});
