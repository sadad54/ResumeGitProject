"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import {
  Button,
  ConfidenceIndicator,
  EmptyState,
  Skeleton,
  StatusPill,
} from "@proofhire/design-system/ui";
import { useEvidenceGraph, useJobs } from "@/lib/queries";
import { useSession } from "@/lib/session";

const Canvas = dynamic(() => import("./constellation-canvas"), {
  ssr: false,
  loading: () => <Skeleton height="420px" label="Loading graph" />,
});

/**
 * The signature view (PRD §11): evidence as a graph, optionally overlaid with
 * one job's requirements and how each is covered. Data comes from the shared
 * query cache, so reviewing evidence elsewhere on the page (which
 * invalidates the "evidence" keys) refreshes this without any wiring.
 */
export function EvidenceConstellation({ jobId }: { jobId?: string }) {
  const { status } = useSession();
  const [overlay, setOverlay] = useState("");
  const [view, setView] = useState<"graph" | "table">("table");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(true);
  const activeJob = jobId || overlay;
  const inspect = useCallback((id: string) => setSelected(id), []);

  const jobs = useJobs();
  const graphQuery = useEvidenceGraph(activeJob || null);
  const graph = graphQuery.data ?? null;
  const loading = graphQuery.isPending && status === "authenticated";
  const error = graphQuery.isError
    ? graphQuery.error.message
    : jobs.isError && !jobId
      ? "Could not load saved jobs. Refresh to retry."
      : "";

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    setView(window.matchMedia("(min-width: 900px)").matches ? "graph" : "table");
    return () => media.removeEventListener("change", update);
  }, []);
  // A different overlay is a different graph; the old selection means nothing there.
  useEffect(() => setSelected(null), [activeJob]);

  const active = graph?.nodes.find((n) => n.id === selected);
  const visible =
    graph?.nodes.filter((n) =>
      `${n.label} ${n.description} ${n.kind}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    ) ?? [];
  const ids = new Set(visible.map((n) => n.id));
  const filteredGraph = graph && {
    ...graph,
    nodes: visible,
    edges: graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target)),
  };
  const requirements =
    graph?.nodes.filter((n) => n.kind === "requirement") ?? [];

  if (status === "anonymous")
    return (
      <EmptyState title="Your proof starts here" level="h2">
        Sign in, then connect GitHub in Settings and sync your repositories.
      </EmptyState>
    );
  return (
    <section className="ph-constellation" aria-label="Evidence constellation">
      <div className="ph-workspace-heading">
        <div>
          <span className="ph-eyebrow">Your work, connected</span>
          <h2>
            Evidence constellation<span className="ph-accent">.</span>
          </h2>
          <p>Follow a skill back to the code that proves it.</p>
        </div>
        <div className="ph-segment" aria-label="Evidence view">
          <Button
            aria-pressed={view === "graph"}
            onClick={() => setView("graph")}
          >
            Constellation
          </Button>
          <Button
            aria-pressed={view === "table"}
            onClick={() => setView("table")}
          >
            Accessible table
          </Button>
        </div>
      </div>
      <div className="ph-toolbar">
        <label className="ph-field">
          Find in this view
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search skills, projects, proof…"
          />
        </label>
        {!jobId && (
          <label className="ph-field">
            Overlay a job
            <select
              value={overlay}
              onChange={(e) => setOverlay(e.target.value)}
            >
              <option value="">Your evidence only</option>
              {(jobs.data ?? []).map((job) => (
                <option key={job.id} value={job.id}>
                  {job.role || "Untitled job"}
                  {job.company ? ` · ${job.company}` : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        <Button
          onClick={() => void graphQuery.refetch()}
          disabled={graphQuery.isFetching}
        >
          {graphQuery.isFetching && !loading ? "Refreshing…" : "Refresh graph"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="ph-error">
          {error}
        </p>
      )}
      {loading && <Skeleton lines={4} label="Loading evidence" />}
      {graph?.truncated && (
        <p role="status">
          Showing a bounded subset of your evidence. Use the Review list to
          inspect all items; absent paths here do not establish a gap.
        </p>
      )}
      {requirements.length > 0 && (
        <div className="ph-coverage-summary" aria-label="Requirement coverage">
          {["strong", "partial", "gap", "unknown"].map((status) => (
            <span key={status}>
              <b>{requirements.filter((n) => n.status === status).length}</b>{" "}
              <StatusPill status={status} />
            </span>
          ))}
          <a href="#graph-coverage">Read coverage matrix ↓</a>
        </div>
      )}
      {!loading && graph && visible.length === 0 && (
        <EmptyState
          title={query ? "No matching nodes" : "No visible evidence yet"}
        >
          {query
            ? "Try a broader search."
            : "Sync a repository and review its evidence. Private, rejected and stale evidence are excluded."}
        </EmptyState>
      )}
      {filteredGraph && visible.length > 0 && (
        <div className="ph-graph-layout">
          {view === "graph" ? (
            <Canvas
              key={activeJob}
              graph={filteredGraph}
              selected={selected}
              onSelect={inspect}
              reducedMotion={reducedMotion}
            />
          ) : (
            <div className="ph-table-wrap">
              <table className="ph-table">
                <caption>
                  Graph nodes, sources and weighted relationships
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Node</th>
                    <th scope="col">Type / status</th>
                    <th scope="col">Connections</th>
                    <th scope="col">Sources</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((n) => (
                    <tr key={n.id}>
                      <th scope="row">
                        <button
                          className="ph-text-button"
                          onClick={() => inspect(n.id)}
                        >
                          {n.label}
                        </button>
                        <p>{n.description}</p>
                        {n.confidence !== null && (
                          <ConfidenceIndicator value={n.confidence} />
                        )}
                      </th>
                      <td>
                        {n.kind}
                        {n.status && <StatusPill status={n.status} />}
                      </td>
                      <td>
                        <ul>
                          {graph?.edges
                            .filter(
                              (e) => e.source === n.id || e.target === n.id,
                            )
                            .map((e) => (
                              <li key={e.id}>
                                {e.kind} →{" "}
                                {
                                  graph.nodes.find(
                                    (other) =>
                                      other.id ===
                                      (e.source === n.id ? e.target : e.source),
                                  )?.label
                                }{" "}
                                ({Math.round(e.weight * 100)}%)
                                {e.status && <StatusPill status={e.status} />}
                                {e.explanation && <p>{e.explanation}</p>}
                              </li>
                            ))}
                        </ul>
                      </td>
                      <td>
                        {n.sources.map((s) => (
                          <a
                            key={`${s.url}-${s.locator}`}
                            href={s.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {s.locator}
                          </a>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {active && (
            <aside
              className="ph-provenance"
              aria-label="Selected node details"
              aria-live="polite"
            >
              <div className="ph-toolbar">
                <span className="ph-eyebrow">Source trail</span>
                <Button
                  aria-label="Close source trail"
                  onClick={() => setSelected(null)}
                >
                  ×
                </Button>
              </div>
              <h3>{active.label}</h3>
              <p>{active.description}</p>
              {active.status && <StatusPill status={active.status} />}
              {active.confidence !== null && (
                <ConfidenceIndicator value={active.confidence} />
              )}
              {active.sources.map((s) => (
                <div className="ph-source" key={`${s.url}-${s.locator}`}>
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.locator} ↗
                  </a>
                  <code>{s.commit_sha.slice(0, 12)}</code>
                </div>
              ))}
              {active.sources.length === 0 && (
                <p>Select connected evidence to see its source.</p>
              )}
            </aside>
          )}
        </div>
      )}
      {requirements.length > 0 && (
        <div id="graph-coverage" className="ph-table-wrap ph-coverage-reveal">
          <table className="ph-table">
            <caption>Evidence coverage matrix</caption>
            <thead>
              <tr>
                <th scope="col">Requirement</th>
                <th scope="col">Coverage</th>
                <th scope="col">Evidence and reasoning</th>
              </tr>
            </thead>
            <tbody>
              {requirements.map((r) => (
                <tr key={r.id}>
                  <th scope="row">
                    {r.label}
                    <p>{r.description}</p>
                  </th>
                  <td>
                    <StatusPill status={r.status || "unknown"} />
                  </td>
                  <td>
                    {graph?.edges
                      .filter((e) => e.target === r.id)
                      .map((e) => (
                        <div key={e.id}>
                          <button
                            className="ph-text-button"
                            onClick={() => inspect(e.source)}
                          >
                            {graph.nodes.find((n) => n.id === e.source)?.label}
                          </button>
                          <p>{e.explanation}</p>
                        </div>
                      ))}
                    {!graph?.edges.some((e) => e.target === r.id) && (
                      <span>
                        {r.status === "gap"
                          ? "No supporting evidence found. Do not claim this."
                          : "Not yet established. Refresh after matching, or review excluded evidence."}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
