"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SkeletonList } from "@proofhire/design-system/ui";
import { api, unwrap } from "@/lib/api-client";
import { qk, useEvidence, type Evidence } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { DEMO_READ_ONLY, RequireSession } from "./session-ui";

const STATUS_LABEL: Record<string, string> = {
  candidate: "Needs review",
  confirmed: "Confirmed",
  rejected: "Rejected",
  private: "Private",
  stale: "Stale",
};

/**
 * Explorer view (PRD §10 Evidence page): the filterable list that is also
 * the permanent accessible equivalent of the graph view (§11.8).
 */
export function EvidenceExplorer() {
  return (
    <RequireSession what="review your evidence">
      <Explorer />
    </RequireSession>
  );
}

function Explorer() {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const evidence = useEvidence();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const setStatus = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Evidence["status"] }) =>
      unwrap(
        await api.PATCH("/api/v1/evidence/{evidence_id}", {
          params: { path: { evidence_id: id } },
          body: { status },
        }),
      ),
    // Optimistic: reviewing is a stream of quick decisions; each one shows
    // immediately and rolls back only if the server refuses it.
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: qk.evidence.all, exact: true });
      const previous = queryClient.getQueryData<Evidence[]>(qk.evidence.all);
      queryClient.setQueryData<Evidence[]>(qk.evidence.all, (list) =>
        list?.map((e) => (e.id === id ? { ...e, status } : e)),
      );
      return { previous };
    },
    onError: (_err, _vars, context) =>
      queryClient.setQueryData(qk.evidence.all, context?.previous),
    onSettled: () => {
      // The graph and the overview counters read the same rows.
      void queryClient.invalidateQueries({ queryKey: qk.evidence.all });
      void queryClient.invalidateQueries({ queryKey: qk.overview });
    },
  });

  if (evidence.isPending) return <SkeletonList count={3} />;
  if (evidence.isError)
    return (
      <p className="ph-error" role="alert">
        Couldn&apos;t load evidence. {evidence.error.message}
      </p>
    );

  const visible = evidence.data.filter(
    (e) =>
      (statusFilter === "all" || e.status === statusFilter) &&
      `${e.title} ${e.normalized_claim}`.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div className="space-y-4">
      <div className="ph-toolbar">
        <label className="ph-field">
          Search evidence
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label className="ph-field">
          Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="candidate">Needs review</option>
            <option value="confirmed">Confirmed</option>
            <option value="rejected">Rejected</option>
            <option value="private">Private</option>
            <option value="stale">Stale</option>
          </select>
        </label>
        <span className="text-xs text-neutral-500" role="status">
          {visible.length} of {evidence.data.length} items
          {evidence.isFetching && " · refreshing"}
        </span>
      </div>

      {setStatus.isError && (
        <p className="ph-error" role="alert">
          {setStatus.error.message}
        </p>
      )}

      <ul className="space-y-2">
        {visible.map((item) => (
          <li key={item.id} className="ph-source">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.title}</span>
                  <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs dark:bg-neutral-800">
                    {item.evidence_type.replaceAll("_", " ")}
                  </span>
                  <span className={`ph-status ph-status-${item.status}`}>
                    {STATUS_LABEL[item.status] ?? item.status}
                  </span>
                </div>
                <p className="mt-1 text-sm">{item.normalized_claim}</p>
                <p className="mt-1 text-xs text-neutral-500">
                  confidence {Math.round(item.confidence * 100)}%
                </p>
              </div>
              <div className="flex shrink-0 gap-1" role="group" aria-label={`Review ${item.title}`}>
                {(["confirmed", "rejected", "private"] as const).map((status) => (
                  <button
                    key={status}
                    type="button"
                    className="ph-button"
                    aria-pressed={item.status === status}
                    disabled={!canWrite}
                    title={!canWrite ? DEMO_READ_ONLY : undefined}
                    onClick={() => setStatus.mutate({ id: item.id, status })}
                  >
                    {status === "confirmed" ? "Confirm" : status === "rejected" ? "Reject" : "Private"}
                  </button>
                ))}
              </div>
            </div>
          </li>
        ))}
      </ul>

      {visible.length === 0 && (
        <p className="text-sm text-neutral-500">
          {evidence.data.length === 0
            ? "No evidence yet. Connect GitHub and sync a repository in Settings."
            : "Nothing matches these filters."}
        </p>
      )}
    </div>
  );
}
