"use client";

import { useEffect, useRef, useState } from "react";
import { openRunEvents } from "@/lib/events";
import { apiBaseUrl, apiFetch, ApiError, getAccessToken } from "@/lib/api";

type Job = { id: string; role: string | null; company: string | null };

type ResumeContent = {
  summary: string;
  skills: string[];
  experience: {
    employer: string;
    title: string;
    start_date: string;
    end_date: string;
    bullets: string[];
  }[];
};

type CoverLetterContent = { body_paragraphs: string[] };

type GeneratedDocument = {
  id: string;
  type: "resume" | "cover_letter";
  content_json: ResumeContent | CoverLetterContent;
  pdf_ref: string | null;
  template_id: string;
};

type GeneratedClaim = {
  id: string;
  claim_text: string;
  claim_type: string;
  verification_status:
    "supported" | "partially_supported" | "unsupported" | "contradictory";
  confidence: number;
  evidence_id: string | null;
  evidence_title: string | null;
  evidence_repository: string | null;
  source_locator: string | null;
};

const STATUS_COLOR: Record<string, string> = {
  supported: "border-green-400",
  partially_supported: "border-amber-400",
  unsupported: "border-red-400",
  contradictory: "border-red-600",
};

/**
 * Resume workspace (PRD §11.4 signature interaction): click a bullet, see the
 * exact evidence/repository it traces back to, or why it was stripped.
 */
export function ResumeWorkspace() {
  const streamCleanup = useRef<(() => void) | null>(null);
  useEffect(() => () => streamCleanup.current?.(), []);
  const [savedDocuments, setSavedDocuments] = useState<GeneratedDocument[]>([]);
  const [template, setTemplate] = useState("ats_minimal");
  const [signedIn, setSignedIn] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [documentType, setDocumentType] = useState<"resume" | "cover_letter">(
    "resume",
  );
  const [document, setDocument] = useState<GeneratedDocument | null>(null);
  const [claims, setClaims] = useState<GeneratedClaim[]>([]);
  const [selectedBullet, setSelectedBullet] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "generating" | "done">("idle");
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSignedIn(!!getAccessToken());
    if (!getAccessToken()) return;
    setSelectedJobId(
      new URLSearchParams(window.location.search).get("job") || "",
    );
    apiFetch<GeneratedDocument[]>("/api/v1/documents")
      .then(setSavedDocuments)
      .catch(() => setError("Could not load saved documents."));
    apiFetch<Job[]>("/api/v1/jobs")
      .then(setJobs)
      .catch(() => {});
  }, []);

  if (!signedIn) {
    return (
      <p className="text-sm text-neutral-500">
        Log in on Home to generate a resume.
      </p>
    );
  }

  async function generate() {
    if (!selectedJobId) return;
    setError(null);
    setStatus("generating");
    setDocument(null);
    setClaims([]);
    try {
      await apiFetch(`/api/v1/jobs/${selectedJobId}/generate`, {
        method: "POST",
        body: JSON.stringify({
          mode: "conservative",
          document_type: documentType,
        }),
      });
      await waitForCompletion(selectedJobId);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to generate resume",
      );
      setStatus("idle");
    }
  }

  async function waitForCompletion(jobId: string) {
    streamCleanup.current?.();
    await new Promise<void>((resolve) => {
      const source = openRunEvents(jobId);
      const finish = () => {
        clearTimeout(timer);
        source.close();
        resolve();
      };
      const timer = setTimeout(() => {
        setError(
          "Generation is taking longer than expected. Reopen Documents to check saved results.",
        );
        setStatus("idle");
        finish();
      }, 120000);
      streamCleanup.current = finish;
      source.addEventListener("generation.completed", async (e) => {
        try {
          const data = JSON.parse((e as MessageEvent).data);
          await loadDocument(data.document_id);
        } catch {
          setError(
            "Could not open the generated document. Reopen it from saved documents.",
          );
          setStatus("idle");
        } finally {
          finish();
        }
      });
      const fail = () => {
        setError(
          "Generation progress is unavailable. Check saved documents before retrying.",
        );
        setStatus("idle");
        finish();
      };
      source.addEventListener("generation.failed", fail);
      source.addEventListener("error", fail);
    });
  }

  async function loadDocument(documentId: string) {
    const doc = await apiFetch<GeneratedDocument>(
      `/api/v1/documents/${documentId}`,
    );
    const docClaims = await apiFetch<GeneratedClaim[]>(
      `/api/v1/documents/${documentId}/claims`,
    );
    setDocument(doc);
    setSavedDocuments((prev) => [doc, ...prev.filter((d) => d.id !== doc.id)]);
    setSelectedBullet(null);
    setTemplate(doc.type === "resume" ? doc.template_id : "ats_minimal");
    setClaims(docClaims);
    setStatus("done");
  }

  async function exportPdf() {
    if (!document) return;
    setExporting(true);
    setError(null);
    try {
      await apiFetch(
        `/api/v1/documents/${document.id}/export${document.type === "resume" ? `?template=${encodeURIComponent(template)}` : ""}`,
        { method: "POST" },
      );
      const refreshed = await apiFetch<GeneratedDocument>(
        `/api/v1/documents/${document.id}`,
      );
      setDocument(refreshed);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Export failed — see worker logs.",
      );
    } finally {
      setExporting(false);
    }
  }

  async function downloadPdf() {
    if (!document) return;
    const token = getAccessToken();
    const response = await fetch(
      `${apiBaseUrl()}/api/v1/documents/${document.id}/pdf`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    if (!response.ok) {
      setError("Failed to download PDF.");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `resume-${document.id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const activeClaim = claims.find((c) => c.claim_text === selectedBullet);

  return (
    <div className="flex flex-col xl:flex-row gap-6">
      <div className="flex-1 min-w-0 space-y-4">
        <label className="ph-field">
          Saved documents
          <select
            value={document?.id || ""}
            onChange={(e) => {
              if (e.target.value)
                void loadDocument(e.target.value).catch(() =>
                  setError("Could not open document."),
                );
            }}
          >
            <option value="">Select a saved document</option>
            {savedDocuments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.type.replace("_", " ")} · {d.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <label id="template" className="ph-field">
          Resume export template
          <select
            disabled={document?.type === "cover_letter"}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
          >
            <option value="ats_minimal">ATS Minimal</option>
            <option value="technical_dense">Technical Dense</option>
            <option value="modern_editorial">Modern Editorial</option>
          </select>
        </label>
        <div className="flex flex-wrap gap-2">
          <select
            aria-label="Job for document"
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
            className="rounded border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            <option value="">Select a job...</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.role || "Untitled"} {job.company ? `@ ${job.company}` : ""}
              </option>
            ))}
          </select>
          <select
            aria-label="Document type"
            value={documentType}
            onChange={(e) =>
              setDocumentType(e.target.value as "resume" | "cover_letter")
            }
            className="rounded border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            <option value="resume">Resume</option>
            <option value="cover_letter">Cover letter</option>
          </select>
          <button
            onClick={generate}
            disabled={!selectedJobId || status === "generating"}
            className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {status === "generating"
              ? "Generating..."
              : `Generate ${documentType === "resume" ? "resume" : "cover letter"}`}
          </button>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        {document && (
          <div className="flex flex-wrap gap-2">
            <button
              id="export"
              onClick={exportPdf}
              disabled={exporting}
              className="rounded border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700"
            >
              {exporting ? "Exporting..." : "Export PDF"}
            </button>
            {document.pdf_ref && (
              <button
                onClick={downloadPdf}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white"
              >
                Download PDF
              </button>
            )}
          </div>
        )}

        {document && document.type === "resume" && (
          <div className="space-y-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
            <p className="text-sm">
              {(document.content_json as ResumeContent).summary}
            </p>
            <div className="flex flex-wrap gap-1">
              {(document.content_json as ResumeContent).skills.map((s) => (
                <span
                  key={s}
                  className="rounded bg-neutral-100 px-2 py-0.5 text-xs dark:bg-neutral-800"
                >
                  {s}
                </span>
              ))}
            </div>
            {(document.content_json as ResumeContent).experience.map(
              (entry, i) => (
                <div key={i}>
                  <div className="text-sm font-medium">
                    {entry.title} — {entry.employer} ({entry.start_date}–
                    {entry.end_date})
                  </div>
                  <ul className="ml-4 list-disc space-y-1 text-sm">
                    {entry.bullets.map((bullet, j) => {
                      const claim = claims.find((c) => c.claim_text === bullet);
                      return (
                        <li
                          key={j}
                          className={`cursor-pointer border-l-2 pl-2 hover:bg-neutral-50 dark:hover:bg-neutral-900 ${
                            claim
                              ? STATUS_COLOR[claim.verification_status]
                              : "border-transparent"
                          }`}
                        >
                          <button
                            className="text-left"
                            onClick={() => setSelectedBullet(bullet)}
                          >
                            {bullet}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ),
            )}
          </div>
        )}

        {document && document.type === "cover_letter" && (
          <div className="space-y-2 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
            {(document.content_json as CoverLetterContent).body_paragraphs.map(
              (paragraph, i) => {
                const claim = claims.find((c) => c.claim_text === paragraph);
                return (
                  <p
                    key={i}
                    className={`cursor-pointer border-l-2 pl-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900 ${
                      claim
                        ? STATUS_COLOR[claim.verification_status]
                        : "border-transparent"
                    }`}
                  >
                    <button
                      className="text-left"
                      onClick={() => setSelectedBullet(paragraph)}
                    >
                      {paragraph}
                    </button>
                  </p>
                );
              },
            )}
          </div>
        )}
      </div>

      {activeClaim && (
        <div className="w-72 shrink-0 space-y-2 rounded-lg border border-neutral-200 p-3 text-sm dark:border-neutral-800">
          <div className="font-medium">Provenance</div>
          <div>
            Status:{" "}
            <span className="font-mono">{activeClaim.verification_status}</span>
          </div>
          {activeClaim.evidence_title && (
            <div>Evidence: {activeClaim.evidence_title}</div>
          )}
          {activeClaim.evidence_repository && (
            <div className="font-mono text-xs">
              {activeClaim.evidence_repository}
            </div>
          )}
          {activeClaim.source_locator && (
            <div className="font-mono text-xs text-neutral-500">
              {activeClaim.source_locator}
            </div>
          )}
          <div className="text-xs text-neutral-500">
            confidence {Math.round(activeClaim.confidence * 100)}%
          </div>
        </div>
      )}
    </div>
  );
}
