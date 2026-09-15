"use client";

import { useState } from "react";
import { apiBaseUrl, apiFetch, ApiError, getAccessToken } from "@/lib/api";

type Job = {
  id: string;
  company: string | null;
  role: string | null;
  seniority: string | null;
  status: string;
};

type Requirement = {
  id: string;
  category: string;
  text: string;
  normalized: string[];
  importance: number;
  required: boolean;
};

const CATEGORY_COLOR: Record<string, string> = {
  skill: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  tooling: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  experience: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  seniority: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  responsibility: "bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200",
  domain: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  education: "bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200",
  soft_skill: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

/**
 * Job Workspace (PRD §10, §16). JD paste box -> requirement chip list. The
 * split coverage-matrix layout and animation land in Phase 4/7 once matching
 * exists — this is the requirement-extraction half of the workspace.
 */
export function JobWorkspace() {
  const [jdText, setJdText] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [status, setStatus] = useState<"idle" | "submitting" | "analyzing" | "done">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!getAccessToken()) {
    return <p className="text-sm text-neutral-500">Log in on Home to analyze a job.</p>;
  }

  async function submit() {
    setError(null);
    setStatus("submitting");
    try {
      const created = await apiFetch<Job>("/api/v1/jobs", {
        method: "POST",
        body: JSON.stringify({ source_text: jdText }),
      });
      setJob(created);
      setStatus("analyzing");
      await apiFetch(`/api/v1/jobs/${created.id}/analyze`, { method: "POST" });
      await waitForCompletion(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to analyze job");
      setStatus("idle");
    }
  }

  async function waitForCompletion(jobId: string) {
    const token = getAccessToken();
    await new Promise<void>((resolve) => {
      const source = new EventSource(
        `${apiBaseUrl()}/api/v1/events/runs/${jobId}?access_token=${token}`,
      );
      source.addEventListener("job.analysis.completed", async () => {
        source.close();
        const reqs = await apiFetch<Requirement[]>(`/api/v1/jobs/${jobId}/requirements`);
        setRequirements(reqs);
        setStatus("done");
        resolve();
      });
      // Fallback: if SSE doesn't deliver within 45s (e.g. no worker process,
      // or the event fired before this listener attached), poll once.
      setTimeout(async () => {
        source.close();
        try {
          const reqs = await apiFetch<Requirement[]>(`/api/v1/jobs/${jobId}/requirements`);
          setRequirements(reqs);
        } finally {
          setStatus("done");
          resolve();
        }
      }, 45000);
    });
  }

  return (
    <div className="space-y-4">
      <textarea
        value={jdText}
        onChange={(e) => setJdText(e.target.value)}
        placeholder="Paste a job description..."
        rows={8}
        className="w-full rounded border border-neutral-300 p-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      />
      <button
        onClick={submit}
        disabled={!jdText.trim() || status === "submitting" || status === "analyzing"}
        className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {status === "analyzing" ? "Analyzing..." : "Analyze job"}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {job && (
        <div className="text-sm text-neutral-600 dark:text-neutral-400">
          {job.role || "Role TBD"} {job.company ? `at ${job.company}` : ""}{" "}
          {job.seniority ? `(${job.seniority})` : ""}
        </div>
      )}

      {requirements.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {requirements.map((r) => (
            <span
              key={r.id}
              title={r.text}
              className={`rounded-full px-3 py-1 text-xs ${CATEGORY_COLOR[r.category] ?? "bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200"}`}
            >
              {r.required ? "● " : "○ "}
              {r.normalized[0] ?? r.text.slice(0, 40)}
            </span>
          ))}
        </div>
      )}

      {status === "done" && requirements.length === 0 && (
        <p className="text-sm text-neutral-500">No requirements extracted.</p>
      )}
    </div>
  );
}
