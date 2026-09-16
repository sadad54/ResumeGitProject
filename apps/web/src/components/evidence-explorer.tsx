"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError, getAccessToken } from "@/lib/api";

type Evidence = {
  id: string;
  repository_id: string;
  evidence_type: string;
  title: string;
  normalized_claim: string;
  description: string;
  confidence: number;
  status: "candidate" | "confirmed" | "rejected" | "private" | "stale";
  created_at: string;
};

const STATUS_LABEL: Record<string, string> = {
  candidate: "Needs review",
  confirmed: "Confirmed",
  rejected: "Rejected",
  private: "Private",
  stale: "Stale",
};

/**
 * Explorer View (PRD §10 Evidence page). Graph View (Constellation) and
 * Repository View land in Phase 7 — this is a plain filterable list for now,
 * which is also the permanent accessible fallback the graph view needs (§11.8).
 */
export function EvidenceExplorer() {
  const [query, setQuery] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [items, setItems] = useState<Evidence[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSignedIn(!!getAccessToken());
    if (!getAccessToken()) return;
    void load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const list = await apiFetch<Evidence[]>("/api/v1/evidence");
      setItems(list);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load evidence",
      );
    } finally {
      setLoading(false);
    }
  }

  async function setStatus(id: string, status: string) {
    try {
      const updated = await apiFetch<Evidence>(`/api/v1/evidence/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setItems((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
      window.dispatchEvent(new Event("proofhire:evidence-updated"));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not update evidence.",
      );
    }
  }

  if (!signedIn) {
    return (
      <p className="text-sm text-neutral-500">
        Log in on Home to view evidence.
      </p>
    );
  }

  const visible = items.filter(
    (e) =>
      (statusFilter === "all" || e.status === statusFilter) &&
      `${e.title} ${e.normalized_claim}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="ph-field">
          Search evidence
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter evidence status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="all">All statuses</option>
          <option value="candidate">Needs review</option>
          <option value="confirmed">Confirmed</option>
          <option value="rejected">Rejected</option>
          <option value="private">Private</option>
        </select>
        <button
          onClick={load}
          disabled={loading}
          className="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700"
        >
          Refresh
        </button>
        <span className="text-xs text-neutral-500">{visible.length} items</span>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <ul className="space-y-2">
        {visible.map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{item.title}</span>
                  <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
                    {item.evidence_type}
                  </span>
                  <span className="text-xs text-neutral-500">
                    {STATUS_LABEL[item.status] ?? item.status}
                  </span>
                </div>
                <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
                  {item.normalized_claim}
                </p>
                <p className="mt-1 text-xs text-neutral-500">
                  confidence {Math.round(item.confidence * 100)}%
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button
                  onClick={() => setStatus(item.id, "confirmed")}
                  className="rounded border border-green-300 px-2 py-1 text-xs text-green-700 dark:border-green-800 dark:text-green-400"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setStatus(item.id, "rejected")}
                  className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 dark:border-red-800 dark:text-red-400"
                >
                  Reject
                </button>
                <button
                  onClick={() => setStatus(item.id, "private")}
                  className="rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700"
                >
                  Private
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {visible.length === 0 && !loading && (
        <p className="text-sm text-neutral-500">
          No evidence yet — sync a repository from Home first.
        </p>
      )}
    </div>
  );
}
