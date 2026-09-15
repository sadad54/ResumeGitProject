"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl, apiFetch, ApiError, getAccessToken } from "@/lib/api";

type Repository = {
  id: string;
  owner: string;
  name: string;
  url: string;
  selected: boolean;
  sync_status: string;
  last_analyzed_sha: string | null;
};

type SyncTriggerResponse = { run_id: string; status: string };

/**
 * Phase 1 demo surface (PRD §9.1 onboarding): connect GitHub, select repos,
 * trigger sync, watch progress over SSE. Superseded by the full onboarding flow
 * and Home command center in later phases.
 */
export function GitHubPanel() {
  const [authed, setAuthed] = useState(false);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);

  useEffect(() => {
    setAuthed(!!getAccessToken());
  }, []);

  useEffect(() => {
    if (!authed) return;
    void loadRepositories();
  }, [authed]);

  useEffect(() => {
    if (!runId) return;
    const token = getAccessToken();
    const source = new EventSource(
      `${apiBaseUrl()}/api/v1/events/runs/${runId}?access_token=${token}`,
    );
    source.addEventListener("message", (e) => {
      setProgress((prev) => [...prev, e.data]);
    });
    // Named-event listeners for the specific event types the worker publishes.
    for (const name of ["github.sync.started", "github.repo.analyzing", "github.repo.completed"]) {
      source.addEventListener(name, (e: MessageEvent) => {
        setProgress((prev) => [...prev, `${name}: ${e.data}`]);
      });
    }
    return () => source.close();
  }, [runId]);

  async function connectGitHub() {
    setError(null);
    try {
      const result = await apiFetch<{ authorize_url: string }>("/api/v1/github/connect", {
        method: "POST",
      });
      window.location.href = result.authorize_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start GitHub connect");
    }
  }

  async function loadRepositories() {
    setLoading(true);
    setError(null);
    try {
      const list = await apiFetch<Repository[]>("/api/v1/github/repositories");
      setRepos(list);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load repositories");
    } finally {
      setLoading(false);
    }
  }

  async function refreshFromGitHub() {
    setLoading(true);
    setError(null);
    try {
      const list = await apiFetch<Repository[]>("/api/v1/github/repositories/refresh", {
        method: "POST",
      });
      setRepos(list);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to refresh from GitHub");
    } finally {
      setLoading(false);
    }
  }

  async function toggleSelected(repo: Repository) {
    const updated = await apiFetch<Repository>(`/api/v1/github/repositories/${repo.id}`, {
      method: "PATCH",
      body: JSON.stringify({ selected: !repo.selected }),
    });
    setRepos((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  }

  async function triggerSync() {
    const selectedIds = repos.filter((r) => r.selected).map((r) => r.id);
    if (selectedIds.length === 0) return;
    setProgress([]);
    const result = await apiFetch<SyncTriggerResponse>("/api/v1/github/sync", {
      method: "POST",
      body: JSON.stringify({ repository_ids: selectedIds }),
    });
    setRunId(result.run_id);
  }

  if (!authed) {
    return <p className="text-sm text-neutral-500">Log in above to connect GitHub.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          onClick={connectGitHub}
          className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Connect GitHub
        </button>
        <button
          onClick={refreshFromGitHub}
          disabled={loading}
          className="rounded border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700"
        >
          Refresh repositories
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {repos.length > 0 && (
        <ul className="space-y-1">
          {repos.map((repo) => (
            <li key={repo.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={repo.selected}
                onChange={() => toggleSelected(repo)}
              />
              <span>
                {repo.owner}/{repo.name}
              </span>
              <span className="text-xs text-neutral-500">({repo.sync_status})</span>
            </li>
          ))}
        </ul>
      )}

      {repos.length > 0 && (
        <button
          onClick={triggerSync}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white"
        >
          Sync selected repositories
        </button>
      )}

      {progress.length > 0 && (
        <div className="rounded border border-neutral-200 p-2 text-xs font-mono dark:border-neutral-800">
          {progress.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
