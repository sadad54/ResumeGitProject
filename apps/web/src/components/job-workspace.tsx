"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@proofhire/design-system/ui";
import { api, unwrap } from "@/lib/api-client";
import { qk, useJob, useJobs } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { EvidenceConstellation } from "./evidence-constellation";
import { DEMO_READ_ONLY, RequireSession } from "./session-ui";

const IN_PROGRESS = ["analyzing", "matching", "analyzed"];
const RETRYABLE = ["captured", "failed", "coverage_failed", "cancelled"];

export function JobWorkspace({ initialJobId = "" }: { initialJobId?: string }) {
  return (
    <RequireSession what="analyze a job">
      <Workspace initialJobId={initialJobId} />
    </RequireSession>
  );
}

function selectInUrl(id: string) {
  window.history.replaceState(null, "", id ? `/jobs?job=${encodeURIComponent(id)}` : "/jobs");
}

function Workspace({ initialJobId }: { initialJobId: string }) {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const [jdText, setJdText] = useState("");
  const [selectedId, setSelectedId] = useState(initialJobId);
  useEffect(() => setSelectedId(initialJobId), [initialJobId]);

  const jobs = useJobs();
  const job = useJob(selectedId);
  const status = job.data?.status;

  // When analysis settles, the graph's requirement overlay has changed.
  useEffect(() => {
    if (status === "ready" || status === "coverage_failed") {
      void queryClient.invalidateQueries({ queryKey: qk.evidence.graph(selectedId) });
      void queryClient.invalidateQueries({ queryKey: qk.overview });
    }
  }, [status, selectedId, queryClient]);

  const analyze = useMutation({
    mutationFn: async (existingId?: string) => {
      const id =
        existingId ??
        unwrap(
          await api.POST("/api/v1/jobs/capture", {
            body: { selected_text: jdText, captured_at: new Date().toISOString() },
          }),
        ).id;
      await api.POST("/api/v1/jobs/{job_id}/analyze", { params: { path: { job_id: id } } });
      return id;
    },
    onSuccess: (id, existingId) => {
      if (!existingId) setJdText("");
      setSelectedId(id);
      selectInUrl(id);
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
  const cancel = useMutation({
    mutationFn: async (id: string) => {
      await api.POST("/api/v1/jobs/{job_id}/cancel", { params: { path: { job_id: id } } });
    },
    onSettled: (_d, _e, id) => queryClient.invalidateQueries({ queryKey: qk.jobs.detail(id) }),
  });

  const readOnly = !canWrite;
  const current = job.data;
  return (
    <div className="space-y-6">
      <section id="capture">
        <label className="ph-field">
          Job description
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={6}
            maxLength={60000}
            placeholder={readOnly ? "The demo is read-only — open a saved job below." : "Paste the role you have in mind…"}
            disabled={readOnly}
          />
        </label>
        <div className="ph-toolbar mt-3">
          <Button
            disabled={readOnly || analyze.isPending || jdText.trim().length < 40}
            title={readOnly ? DEMO_READ_ONLY : undefined}
            onClick={() => analyze.mutate(undefined)}
          >
            {analyze.isPending ? "Starting analysis…" : "Analyze job →"}
          </Button>
          <span className="text-xs">At least 40 characters. Your work supplies the proof.</span>
        </div>
      </section>

      <label className="ph-field">
        Reopen a saved job
        <select
          value={selectedId}
          onChange={(e) => {
            setSelectedId(e.target.value);
            selectInUrl(e.target.value);
          }}
        >
          <option value="">Select a job</option>
          {(jobs.data ?? []).map((j) => (
            <option key={j.id} value={j.id}>
              {j.role || "Untitled job"} {j.company ? `· ${j.company}` : ""}
            </option>
          ))}
        </select>
      </label>

      {[jobs, job].map(
        (q, i) =>
          q.isError && (
            <p key={i} className="ph-error" role="alert">
              {q.error.message}
            </p>
          ),
      )}
      {[analyze, cancel].map(
        (m, i) =>
          m.isError && (
            <p key={`m${i}`} className="ph-error" role="alert">
              {m.error.message}
            </p>
          ),
      )}

      {current && (
        <>
          <div className="ph-toolbar">
            <div className="flex-1">
              <h2 className="text-xl font-semibold">
                {current.role || "Captured job"}
                {current.company ? ` · ${current.company}` : ""}
              </h2>
              <p role="status" className="text-sm mt-2">
                Status: {current.status.replaceAll("_", " ")}
                {IN_PROGRESS.includes(current.status) && " · updating automatically"}
              </p>
            </div>
            {IN_PROGRESS.slice(0, 2).includes(current.status) && (
              <Button
                disabled={readOnly || cancel.isPending}
                title={readOnly ? DEMO_READ_ONLY : undefined}
                onClick={() => cancel.mutate(current.id)}
              >
                Cancel analysis
              </Button>
            )}
            {RETRYABLE.includes(current.status) && (
              <Button
                disabled={readOnly || analyze.isPending}
                title={readOnly ? DEMO_READ_ONLY : undefined}
                onClick={() => analyze.mutate(current.id)}
              >
                {current.status === "captured" ? "Analyze captured job" : "Retry analysis"}
              </Button>
            )}
            <Link className="ph-button" href={`/documents?job=${current.id}`}>
              Create a document ↗
            </Link>
          </div>
          <EvidenceConstellation jobId={current.id} />
        </>
      )}
    </div>
  );
}
