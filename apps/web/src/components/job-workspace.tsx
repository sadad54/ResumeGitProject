"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, getAccessToken } from "@/lib/api";
import { EvidenceConstellation } from "./evidence-constellation";
import { Button, EmptyState } from "@proofhire/design-system/ui";

type Job = {
  id: string;
  company: string | null;
  role: string | null;
  status: string;
};

export function JobWorkspace({ initialJobId = "" }: { initialJobId?: string }) {
  const [jdText, setJdText] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState(initialJobId);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    setSignedIn(!!getAccessToken());
    if (getAccessToken())
      apiFetch<Job[]>("/api/v1/jobs")
        .then(setJobs)
        .catch(() => setError("Could not load saved jobs."));
  }, [revision]);
  useEffect(() => setSelectedId(initialJobId), [initialJobId]);
  useEffect(() => {
    if (!selectedId || !getAccessToken()) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setJob(null);
    setError("");
    async function poll() {
      try {
        const current = await apiFetch<Job>(
          `/api/v1/jobs/${encodeURIComponent(selectedId)}`,
          { signal: controller.signal },
        );
        setJob(current);
        if (["analyzing", "matching", "analyzed"].includes(current.status)) {
          if (++attempts < 90) timer = setTimeout(poll, 2000);
          else
            setError(
              "Analysis is still running. Refresh status to check again.",
            );
        }
      } catch (err) {
        if (!controller.signal.aborted)
          setError(err instanceof Error ? err.message : "Could not open job.");
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [selectedId, revision]);

  async function analyze(id?: string) {
    setBusy(true);
    setError("");
    try {
      const target =
        id ||
        (
          await apiFetch<Job>("/api/v1/jobs/capture", {
            method: "POST",
            body: JSON.stringify({
              selected_text: jdText,
              captured_at: new Date().toISOString(),
            }),
          })
        ).id;
      await apiFetch(`/api/v1/jobs/${target}/analyze`, { method: "POST" });
      setSelectedId(target);
      setRevision((v) => v + 1);
      window.history.replaceState(
        null,
        "",
        `/jobs?job=${encodeURIComponent(target)}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze job.");
    } finally {
      setBusy(false);
    }
  }
  if (!signedIn)
    return (
      <EmptyState title="Find where your evidence fits" level="h2">
        Log in on Home to capture and analyze a job.
      </EmptyState>
    );
  return (
    <div className="space-y-6">
      <section id="capture">
        <label className="ph-field">
          Job description
          <textarea
            autoFocus={false}
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={6}
            maxLength={60000}
            placeholder="Paste the role you have in mind…"
          />
        </label>
        <div className="ph-toolbar mt-3">
          <Button
            disabled={busy || jdText.trim().length < 40}
            onClick={() => void analyze()}
          >
            {busy ? "Starting analysis…" : "Analyze job →"}
          </Button>
          <span className="text-xs">
            At least 40 characters. Your work supplies the proof.
          </span>
        </div>
      </section>
      <label className="ph-field">
        Reopen a saved job
        <select
          value={selectedId}
          onChange={(e) => {
            setSelectedId(e.target.value);
            window.history.replaceState(
              null,
              "",
              `/jobs?job=${encodeURIComponent(e.target.value)}`,
            );
          }}
        >
          <option value="">Select a job</option>
          {jobs.map((j) => (
            <option key={j.id} value={j.id}>
              {j.role || "Untitled job"} {j.company ? `· ${j.company}` : ""}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p className="ph-error" role="alert">
          {error}
        </p>
      )}
      {job && (
        <>
          <div className="ph-toolbar">
            <div className="flex-1">
              <h2 className="text-xl font-semibold">
                {job.role || "Captured job"}
                {job.company ? ` · ${job.company}` : ""}
              </h2>
              <p role="status" className="text-sm mt-2">
                Status: {job.status.replaceAll("_", " ")}
              </p>
            </div>
            <Button onClick={() => setRevision((v) => v + 1)}>
              Refresh status
            </Button>
            {["captured", "failed", "coverage_failed"].includes(job.status) && (
              <Button disabled={busy} onClick={() => void analyze(job.id)}>
                {job.status === "captured"
                  ? "Analyze captured job"
                  : "Retry analysis"}
              </Button>
            )}
            <Link className="ph-button" href={`/documents?job=${job.id}`}>
              Create a document ↗
            </Link>
          </div>
          <EvidenceConstellation
            jobId={job.id}
            refreshKey={
              revision +
              (job.status === "ready" || job.status === "coverage_failed"
                ? 1000
                : 0)
            }
          />
        </>
      )}
    </div>
  );
}
