"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Skeleton } from "@proofhire/design-system/ui";
import { api, unwrap } from "@/lib/api-client";
import { openRunEvents } from "@/lib/events";
import { qk, useOverview, useRepositories, type Repository } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { DEMO_READ_ONLY } from "./session-ui";

type ProgressLine = { id: number; text: string; tone?: "done" | "error" };

const STATUS_TEXT: Record<string, string> = {
  idle: "not synced yet",
  queued: "queued…",
  syncing: "fetching files…",
  extracting: "finding evidence…",
  completed: "✓ evidence ready",
  failed: "failed — sync again",
};

/** Human-readable lines for the worker's run events (RunEventName). */
function describe(event: string, data: Record<string, unknown>, repos: Repository[]): string | null {
  const name = (id: unknown) => {
    const repo = repos.find((r) => r.id === id);
    return repo ? `${repo.owner}/${repo.name}` : "repository";
  };
  switch (event) {
    case "github.sync.started":
      return "Sync started";
    case "github.repo.analyzing":
      return `Analyzing ${data.owner}/${data.name}…`;
    case "github.repo.completed": {
      const scanned = Number(data.files_scanned ?? 0);
      const changed = Number(data.artifacts_created ?? 0);
      const stale = Number(data.evidence_marked_stale ?? 0);
      return `${name(data.repository_id)}: ${scanned} relevant files, ${changed} new or changed${
        stale ? `, ${stale} evidence items marked stale` : ""
      }`;
    }
    case "evidence.created":
      return typeof data.title === "string" ? `Evidence found: ${data.title}` : null;
    case "github.sync.completed":
      return "Files synced. Evidence extraction continues in the background; each repository shows “evidence ready” when it's done.";
    case "github.sync.failed":
      return typeof data.message === "string" ? data.message : "Sync failed.";
    default:
      return null;
  }
}

/**
 * GitHub connection and repository sync (PRD §9.1). Lives in Settings
 * because that's where the OAuth callback returns the browser.
 */
export function GitHubPanel() {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const overview = useOverview();
  const repositories = useRepositories();
  const [progress, setProgress] = useState<ProgressLine[]>([]);
  const [running, setRunning] = useState(false);
  const closeStream = useRef<(() => void) | null>(null);
  useEffect(() => () => closeStream.current?.(), []);

  const repos = repositories.data ?? [];
  const connected = overview.data?.github.connected ?? false;

  const connect = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/github/connect")),
    onSuccess: ({ authorize_url }) => window.location.assign(authorize_url),
  });
  const disconnect = useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/github/connection");
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.overview });
      void queryClient.invalidateQueries({ queryKey: qk.repositories });
    },
  });
  const refresh = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/github/repositories/refresh")),
    onSuccess: (list) => queryClient.setQueryData(qk.repositories, list),
  });
  const toggle = useMutation({
    mutationFn: async (repo: Repository) =>
      unwrap(
        await api.PATCH("/api/v1/github/repositories/{repository_id}", {
          params: { path: { repository_id: repo.id } },
          body: { selected: !repo.selected },
        }),
      ),
    // Optimistic: the checkbox answers immediately; rolled back on failure.
    onMutate: async (repo) => {
      await queryClient.cancelQueries({ queryKey: qk.repositories });
      const previous = queryClient.getQueryData<Repository[]>(qk.repositories);
      queryClient.setQueryData<Repository[]>(qk.repositories, (list) =>
        list?.map((r) => (r.id === repo.id ? { ...r, selected: !r.selected } : r)),
      );
      return { previous };
    },
    onError: (_err, _repo, context) => queryClient.setQueryData(qk.repositories, context?.previous),
    onSettled: () => queryClient.invalidateQueries({ queryKey: qk.repositories }),
  });
  const sync = useMutation({
    mutationFn: async (ids: string[]) =>
      unwrap(await api.POST("/api/v1/github/sync", { body: { repository_ids: ids } })),
    onSuccess: ({ run_id }) => watch(run_id),
  });

  function watch(runId: string) {
    closeStream.current?.();
    setRunning(true);
    let lineId = 0;
    const push = (text: string, tone?: ProgressLine["tone"]) =>
      setProgress((prev) => [...prev, { id: ++lineId, text, tone }]);
    const source = openRunEvents(runId);
    const finish = () => {
      source.close();
      closeStream.current = null;
      setRunning(false);
      for (const key of [qk.repositories, qk.overview, qk.evidence.all]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    };
    closeStream.current = finish;
    for (const event of [
      "github.sync.started",
      "github.repo.analyzing",
      "github.repo.completed",
      "evidence.created",
      "github.sync.completed",
      "github.sync.failed",
    ]) {
      source.addEventListener(event, (e) => {
        let data: Record<string, unknown> = {};
        try {
          data = JSON.parse((e as MessageEvent).data);
        } catch {
          /* keep empty */
        }
        const text = describe(event, data, repos);
        const tone = event === "github.sync.failed" ? "error" : event.endsWith("completed") ? "done" : undefined;
        if (text) push(text, tone);
        // Exactly one terminal event per run, success or failure (sync.py).
        if (event === "github.sync.completed" || event === "github.sync.failed") finish();
      });
    }
    source.addEventListener("error", () => {
      push("Lost the progress stream. The sync keeps running; refresh to see results.", "error");
      finish();
    });
  }

  if (overview.isPending || repositories.isPending) return <Skeleton lines={4} label="Loading GitHub connection" />;

  const selectedIds = repos.filter((r) => r.selected).map((r) => r.id);
  const readOnly = !canWrite;

  return (
    <div className="space-y-4">
      <p className="text-sm">
        {connected ? (
          <>
            Connected as <strong>@{overview.data?.github.login}</strong>.
          </>
        ) : (
          "Not connected. ProofHire asks for read access to your repositories to find evidence."
        )}
      </p>
      <div className="ph-toolbar">
        <Button
          className={connected ? "" : "ph-button-primary"}
          disabled={readOnly || connect.isPending}
          title={readOnly ? DEMO_READ_ONLY : undefined}
          onClick={() => connect.mutate()}
        >
          {connected ? "Reconnect GitHub" : "Connect GitHub"}
        </Button>
        {connected && (
          <>
            <Button
              disabled={readOnly || refresh.isPending}
              title={readOnly ? DEMO_READ_ONLY : undefined}
              onClick={() => refresh.mutate()}
            >
              {refresh.isPending ? "Fetching…" : "Refresh repository list"}
            </Button>
            <Button
              disabled={readOnly || disconnect.isPending}
              title={readOnly ? DEMO_READ_ONLY : undefined}
              onClick={() => {
                if (window.confirm("Disconnect GitHub? Your repositories list is removed; evidence you've already reviewed is kept.")) {
                  disconnect.mutate();
                }
              }}
            >
              Disconnect
            </Button>
          </>
        )}
      </div>

      {[connect, disconnect, refresh, toggle, sync].map(
        (m, i) =>
          m.isError && (
            <p key={i} className="ph-error" role="alert">
              {m.error.message}
            </p>
          ),
      )}

      {repos.length > 0 && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Repositories to analyze</legend>
          <ul className="ph-repo-list">
            {repos.map((repo) => (
              <li key={repo.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={repo.selected}
                    disabled={readOnly}
                    onChange={() => toggle.mutate(repo)}
                  />
                  <span>
                    {repo.owner}/{repo.name}
                  </span>
                  <span className="text-xs text-neutral-500" data-status={repo.sync_status}>
                    {STATUS_TEXT[repo.sync_status] ?? repo.sync_status}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <Button
            className="ph-button-primary"
            disabled={readOnly || running || sync.isPending || selectedIds.length === 0}
            title={readOnly ? DEMO_READ_ONLY : undefined}
            onClick={() => {
              setProgress([]);
              sync.mutate(selectedIds);
            }}
          >
            {running ? "Syncing…" : `Sync ${selectedIds.length} selected`}
          </Button>
        </fieldset>
      )}
      {connected && repos.length === 0 && (
        <p className="text-sm text-neutral-500">
          No repositories yet — use “Refresh repository list” to fetch them from GitHub.
        </p>
      )}

      {progress.length > 0 && (
        <ol className="ph-progress" aria-live="polite">
          {progress.map((line) => (
            <li key={line.id} data-tone={line.tone}>
              {line.text}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
