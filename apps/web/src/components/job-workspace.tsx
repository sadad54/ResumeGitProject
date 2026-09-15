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

type CoverageRow = {
  requirement_id: string;
  requirement_text: string;
  category: string;
  required: boolean;
  importance: number;
  match_label: "strong" | "partial" | "gap" | "unknown";
  evidence_id: string | null;
  evidence_title: string | null;
  evidence_repository: string | null;
  confidence: number | null;
  explanation: string;
  action: string;
};

const MATCH_LABEL_STYLE: Record<string, string> = {
  strong: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  partial: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  gap: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  unknown: "bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200",
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
  const [coverage, setCoverage] = useState<CoverageRow[]>([]);
  const [coverageLoading, setCoverageLoading] = useState(false);
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

  async function loadCoverage() {
    if (!job) return;
    setCoverageLoading(true);
    try {
      const rows = await apiFetch<CoverageRow[]>(`/api/v1/jobs/${job.id}/coverage`);
      setCoverage(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load coverage");
    } finally {
      setCoverageLoading(false);
    }
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

      {status === "done" && requirements.length > 0 && (
        <div className="space-y-2">
          <button
            onClick={loadCoverage}
            disabled={coverageLoading}
            className="rounded border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700"
          >
            {coverageLoading ? "Loading..." : coverage.length > 0 ? "Refresh coverage" : "Load coverage matrix"}
          </button>
          <p className="text-xs text-neutral-500">
            Coverage computation runs in the background after analysis and may
            take a little longer than requirement extraction — refresh if it
            looks incomplete.
          </p>
        </div>
      )}

      {coverage.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-neutral-200 text-left dark:border-neutral-800">
              <th className="py-1 pr-2">Requirement</th>
              <th className="py-1 pr-2">Match</th>
              <th className="py-1 pr-2">Evidence</th>
              <th className="py-1 pr-2">Repository</th>
              <th className="py-1">Action</th>
            </tr>
          </thead>
          <tbody>
            {coverage.map((row) => (
              <tr key={row.requirement_id} className="border-b border-neutral-100 dark:border-neutral-900">
                <td className="py-1.5 pr-2" title={row.explanation}>
                  {row.requirement_text.slice(0, 60)}
                  {row.required ? " *" : ""}
                </td>
                <td className="py-1.5 pr-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${MATCH_LABEL_STYLE[row.match_label]}`}>
                    {row.match_label}
                  </span>
                </td>
                <td className="py-1.5 pr-2">{row.evidence_title ?? "—"}</td>
                <td className="py-1.5 pr-2 font-mono text-xs">{row.evidence_repository ?? "—"}</td>
                <td className="py-1.5 text-xs text-neutral-600 dark:text-neutral-400">{row.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
