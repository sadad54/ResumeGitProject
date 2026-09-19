"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError, getAccessToken } from "@/lib/api";

type Job = { id: string; role: string | null; company: string | null };

type Application = {
  id: string;
  job_id: string;
  stage: "saved" | "analyzing" | "ready" | "applied" | "screen" | "interview" | "offer" | "rejected" | "archived";
  created_at: string;
  updated_at: string;
};

const STAGES: Application["stage"][] = [
  "saved", "analyzing", "ready", "applied", "screen", "interview", "offer", "rejected", "archived",
];

/**
 * Application tracking (PRD §13 Application, §37 item 16 "revisit the
 * application later"). Basic list + stage dropdown for V1 — a kanban board
 * view is a natural later enhancement, not required for the Definition of Done.
 */
export function ApplicationsBoard() {
  const [signedIn, setSignedIn] = useState(false);
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [apps, jobList] = await Promise.all([
        apiFetch<Application[]>("/api/v1/applications"),
        apiFetch<Job[]>("/api/v1/jobs"),
      ]);
      setApplications(apps);
      setJobs(Object.fromEntries(jobList.map((j) => [j.id, j])));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load applications");
    }
  }

  useEffect(() => {
    // See resume-upload.tsx for why this is deferred to an effect rather
    // than called directly in the render body (SSR/hydration mismatch).
    setSignedIn(!!getAccessToken());
    if (!getAccessToken()) return;
    void load();
  }, []);



  async function trackJob(jobId: string) {
    const created = await apiFetch<Application>("/api/v1/applications", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId }),
    });
    setApplications((prev) => (prev.some((a) => a.id === created.id) ? prev : [created, ...prev]));
  }

  async function setStage(id: string, stage: Application["stage"]) {
    // Optimistic: a stage change is the user's own decision about their own
    // record, so it's shown immediately and rolled back only if the server
    // refuses. Waiting on the round trip here made the dropdown feel stuck.
    const previous = applications.find((a) => a.id === id);
    setApplications((prev) => prev.map((a) => (a.id === id ? { ...a, stage } : a)));
    setError(null);
    try {
      const updated = await apiFetch<Application>(`/api/v1/applications/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ stage }),
      });
      setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      if (previous) {
        setApplications((prev) => prev.map((a) => (a.id === id ? previous : a)));
      }
      setError(err instanceof ApiError ? err.message : "Could not update stage.");
    }
  }

  if (!signedIn) {
    return <p className="text-sm text-neutral-500">Log in on Home to track applications.</p>;
  }

  const untracked = Object.values(jobs).filter((j) => !applications.some((a) => a.job_id === j.id));

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red-600">{error}</p>}

      {untracked.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">Jobs not yet tracked:</p>
          {untracked.map((job) => (
            <button
              key={job.id}
              onClick={() => trackJob(job.id)}
              className="mr-2 rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700"
            >
              + Track: {job.role || "Untitled"} {job.company ? `@ ${job.company}` : ""}
            </button>
          ))}
        </div>
      )}

      <ul className="space-y-2">
        {applications.map((app) => {
          const job = jobs[app.job_id];
          return (
            <li
              key={app.id}
              className="flex items-center justify-between rounded-lg border border-neutral-200 p-3 text-sm dark:border-neutral-800"
            >
              <span>
                {job ? `${job.role || "Untitled"} ${job.company ? `@ ${job.company}` : ""}` : app.job_id}
              </span>
              <select
                value={app.stage}
                onChange={(e) => setStage(app.id, e.target.value as Application["stage"])}
                className="rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-700 dark:bg-neutral-900"
              >
                {STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </li>
          );
        })}
      </ul>

      {applications.length === 0 && (
        <p className="text-sm text-neutral-500">No tracked applications yet.</p>
      )}
    </div>
  );
}

