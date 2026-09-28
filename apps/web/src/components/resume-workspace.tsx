"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Skeleton } from "@proofhire/design-system/ui";
import { ApiError } from "@/lib/api";
import { api, unwrap } from "@/lib/api-client";
import { openRunEvents } from "@/lib/events";
import {
  qk,
  useClaims,
  useDocument,
  useDocuments,
  useJobs,
  type GeneratedDocument,
} from "@/lib/queries";
import { useSession } from "@/lib/session";
import { DocumentDiff } from "./document-diff";
import { DocumentPreview } from "./document-preview";
import { DEMO_READ_ONLY, RequireSession } from "./session-ui";

// `content_json` is free-form in the API schema; its shape is defined by the
// worker's writer output schemas (intelligence/schemas.py).
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
  // resume_write:v2; absent on documents written before it.
  projects?: { name: string; bullets: string[] }[];
};
type CoverLetterContent = { body_paragraphs: string[] };
type DocumentType = "resume" | "cover_letter";

const STATUS_COLOR: Record<string, string> = {
  supported: "border-green-400",
  partially_supported: "border-amber-400",
  unsupported: "border-red-400",
  contradictory: "border-red-600",
};
const GENERATION_TIMEOUT_MS = 180_000;

/**
 * Resume workspace (PRD §11.4 signature interaction): click a bullet, see the
 * exact evidence/repository it traces back to, or why it was stripped.
 */
export function ResumeWorkspace() {
  return (
    <RequireSession what="generate verified documents">
      <Workspace />
    </RequireSession>
  );
}

function Workspace() {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const documents = useDocuments();
  const jobs = useJobs();
  const [documentId, setDocumentId] = useState<string | null>(null);
  const document = useDocument(documentId);
  const claims = useClaims(documentId);

  const [selectedJobId, setSelectedJobId] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>("resume");
  const [template, setTemplate] = useState("ats_minimal");
  const [compareId, setCompareId] = useState("");
  const [showPreview, setShowPreview] = useState(true);
  const [selectedBullet, setSelectedBullet] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastExport, setLastExport] = useState<{ page_count?: number | null; overflowed?: boolean } | null>(null);
  const stopWaiting = useRef<(() => void) | null>(null);
  useEffect(() => () => stopWaiting.current?.(), []);

  useEffect(() => {
    setSelectedJobId(new URLSearchParams(window.location.search).get("job") || "");
  }, []);
  // Opening a document adopts its template, and clears per-document state.
  const doc = document.data;
  useEffect(() => {
    if (!doc) return;
    setTemplate(doc.type === "resume" ? doc.template_id : "ats_minimal");
    setSelectedBullet(null);
    setLastExport(null);
  }, [doc?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const open = (id: string) => {
    setNotice(null);
    setDocumentId(id);
  };

  /** Resolves with the new document's id, or rejects with a user-facing message. */
  function waitForGeneration(jobId: string): Promise<string> {
    stopWaiting.current?.();
    return new Promise((resolve, reject) => {
      const source = openRunEvents(jobId);
      const done = () => {
        clearTimeout(timer);
        source.close();
        stopWaiting.current = null;
      };
      const timer = setTimeout(() => {
        done();
        reject(new Error("Generation is taking longer than expected. It will appear in Saved documents when it finishes."));
      }, GENERATION_TIMEOUT_MS);
      stopWaiting.current = done;
      source.addEventListener("generation.completed", (e) => {
        done();
        try {
          resolve(JSON.parse((e as MessageEvent).data).document_id);
        } catch {
          reject(new Error("Generated, but the new document couldn't be opened. Pick it from Saved documents."));
        }
      });
      source.addEventListener("generation.failed", (e) => {
        done();
        let cancelled = false;
        try {
          cancelled = !!JSON.parse((e as MessageEvent).data).cancelled;
        } catch {
          /* keep default */
        }
        reject(new Error(cancelled ? "Generation was cancelled." : "Generation failed. Try again, or check the job's analysis first."));
      });
      const lost = () => {
        done();
        reject(new Error("Lost the progress stream. Generation continues; check Saved documents in a moment."));
      };
      source.addEventListener("error", lost);
      source.addEventListener("end", lost);
    });
  }

  const generate = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/jobs/{job_id}/generate", {
        params: { path: { job_id: selectedJobId } },
        body: { mode: "conservative", document_type: documentType },
      });
      return waitForGeneration(selectedJobId);
    },
    onSuccess: (id) => open(id),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: qk.documents.all });
      void queryClient.invalidateQueries({ queryKey: qk.overview });
    },
  });

  const exportPdf = useMutation({
    mutationFn: async (target: GeneratedDocument) =>
      unwrap(
        await api.POST("/api/v1/documents/{document_id}/export", {
          params: {
            path: { document_id: target.id },
            query: target.type === "resume" ? { template: template as "ats_minimal" } : {},
          },
        }),
      ),
    onSuccess: (result, target) => {
      setLastExport(result);
      void queryClient.invalidateQueries({ queryKey: qk.documents.detail(target.id) });
      void queryClient.invalidateQueries({ queryKey: qk.documents.all, exact: true });
      void queryClient.invalidateQueries({ queryKey: qk.overview });
    },
  });

  const download = useMutation({
    mutationFn: async ({ target, format }: { target: GeneratedDocument; format: "pdf" | "txt" }) =>
      unwrap(
        await api.GET("/api/v1/documents/{document_id}/download", {
          params: { path: { document_id: target.id }, query: { format } },
        }),
      ),
    // A signed, short-lived URL straight to storage; the response is an
    // attachment, so the browser downloads without leaving the page.
    onSuccess: (link) => window.location.assign(link.url),
    onError: (err, { target }) => {
      if (err instanceof ApiError && err.status === 410) {
        setNotice("That export has expired (the files were cleared). Export it again to download.");
        void queryClient.invalidateQueries({ queryKey: qk.documents.detail(target.id) });
      }
    },
  });

  const claimsByText = new Map((claims.data ?? []).map((c) => [c.claim_text, c]));
  const activeClaim = selectedBullet ? claimsByText.get(selectedBullet) : undefined;
  const saved = documents.data ?? [];
  const errors = [documents, jobs, document, claims, generate, exportPdf, download]
    .filter((q) => q.isError && !(q === download && download.error instanceof ApiError && download.error.status === 410))
    .map((q) => q.error?.message);

  return (
    <div className="flex flex-col xl:flex-row gap-6">
      <div className="flex-1 min-w-0 space-y-4">
        {documents.isPending ? (
          <Skeleton lines={2} label="Loading saved documents" />
        ) : (
          <label className="ph-field">
            Saved documents
            <select value={documentId ?? ""} onChange={(e) => e.target.value && open(e.target.value)}>
              <option value="">Select a saved document</option>
              {saved.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.type.replace("_", " ")} · v{d.version} · {new Date(d.created_at).toLocaleDateString()}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="ph-field">
          Resume export template
          <select
            disabled={doc?.type === "cover_letter"}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
          >
            <option value="ats_minimal">ATS Minimal</option>
            <option value="technical_dense">Technical Dense</option>
            <option value="modern_editorial">Modern Editorial</option>
          </select>
        </label>
        <div className="ph-toolbar">
          <label className="ph-field">
            Job
            <select value={selectedJobId} onChange={(e) => setSelectedJobId(e.target.value)}>
              <option value="">Select a job…</option>
              {(jobs.data ?? []).map((job) => (
                <option key={job.id} value={job.id}>
                  {job.role || "Untitled"} {job.company ? `@ ${job.company}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="ph-field">
            Document type
            <select value={documentType} onChange={(e) => setDocumentType(e.target.value as DocumentType)}>
              <option value="resume">Resume</option>
              <option value="cover_letter">Cover letter</option>
            </select>
          </label>
          <button
            type="button"
            className="ph-button ph-button-primary"
            onClick={() => generate.mutate()}
            disabled={!canWrite || !selectedJobId || generate.isPending}
            title={!canWrite ? DEMO_READ_ONLY : undefined}
          >
            {generate.isPending
              ? "Generating and verifying…"
              : `Generate ${documentType === "resume" ? "resume" : "cover letter"}`}
          </button>
        </div>

        {generate.isPending && (
          <p role="status" className="text-sm">
            Planning positioning, writing, then verifying every claim against your evidence.
            This takes a minute on the free model tier.
          </p>
        )}
        {notice && (
          <p className="ph-banner ph-banner-warn" role="alert">
            {notice}
          </p>
        )}
        {errors.map((message, i) => (
          <p key={i} className="ph-error" role="alert">
            {message}
          </p>
        ))}

        {doc && (
          <div className="ph-toolbar">
            <button
              type="button"
              id="export"
              className="ph-button"
              onClick={() => exportPdf.mutate(doc)}
              disabled={exportPdf.isPending}
            >
              {exportPdf.isPending ? "Exporting…" : doc.pdf_available ? "Re-export PDF" : "Export PDF"}
            </button>
            {doc.pdf_available && (
              <button
                type="button"
                className="ph-button ph-button-primary"
                onClick={() => download.mutate({ target: doc, format: "pdf" })}
                disabled={download.isPending}
              >
                Download PDF
              </button>
            )}
            {doc.plaintext_available && (
              <button
                type="button"
                className="ph-button"
                onClick={() => download.mutate({ target: doc, format: "txt" })}
                disabled={download.isPending}
              >
                Download plain text
              </button>
            )}
            <button
              type="button"
              className="ph-button"
              onClick={() => setShowPreview((v) => !v)}
              aria-pressed={showPreview}
            >
              {showPreview ? "Hide preview" : "Show preview"}
            </button>
            <label className="ph-field">
              Compare with
              <select value={compareId} onChange={(e) => setCompareId(e.target.value)}>
                <option value="">— none —</option>
                {saved
                  .filter((d) => d.id !== doc.id && d.type === doc.type)
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      v{d.version} · {d.template_id} · {new Date(d.created_at).toLocaleDateString()}
                      {d.job_id === doc.job_id ? " (same job)" : ""}
                    </option>
                  ))}
              </select>
            </label>
          </div>
        )}

        {lastExport?.overflowed && (
          <p role="alert" className="ph-error">
            This resume rendered to {lastExport.page_count} pages. Most ATS parsers weight
            first-page content; consider trimming bullets or switching to the Technical Dense
            template.
          </p>
        )}

        {doc && compareId && (
          <DocumentDiff
            before={saved.find((d) => d.id === compareId)?.content_json}
            after={doc.content_json}
            beforeLabel={`v${saved.find((d) => d.id === compareId)?.version ?? "?"}`}
            afterLabel={`v${doc.version}`}
          />
        )}

        {document.isPending && documentId && <Skeleton lines={6} label="Loading document" />}

        {doc && doc.type === "resume" && (
          <div className="space-y-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
            <p className="text-sm">{(doc.content_json as ResumeContent).summary}</p>
            <div className="flex flex-wrap gap-1">
              {(doc.content_json as ResumeContent).skills.map((s) => (
                <span key={s} className="rounded bg-neutral-100 px-2 py-0.5 text-xs dark:bg-neutral-800">
                  {s}
                </span>
              ))}
            </div>
            {[
              ...(doc.content_json as ResumeContent).experience.map((entry) => ({
                heading: `${entry.title} — ${entry.employer} (${entry.start_date}–${entry.end_date})`,
                bullets: entry.bullets,
              })),
              ...((doc.content_json as ResumeContent).projects ?? []).map((project) => ({
                heading: `Project · ${project.name}`,
                bullets: project.bullets,
              })),
            ].map((section, i) => (
              <div key={i}>
                <div className="text-sm font-medium">{section.heading}</div>
                <ul className="ml-4 list-disc space-y-1 text-sm">
                  {section.bullets.map((bullet, j) => {
                    const claim = claimsByText.get(bullet);
                    return (
                      <li
                        key={j}
                        className={`border-l-2 pl-2 hover:bg-neutral-50 dark:hover:bg-neutral-900 ${
                          claim ? STATUS_COLOR[claim.verification_status] : "border-transparent"
                        }`}
                      >
                        <button className="text-left" onClick={() => setSelectedBullet(bullet)}>
                          {bullet}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}

        {doc && doc.type === "cover_letter" && (
          <div className="space-y-2 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
            {(doc.content_json as CoverLetterContent).body_paragraphs.map((paragraph, i) => {
              const claim = claimsByText.get(paragraph);
              return (
                <p
                  key={i}
                  className={`border-l-2 pl-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900 ${
                    claim ? STATUS_COLOR[claim.verification_status] : "border-transparent"
                  }`}
                >
                  <button className="text-left" onClick={() => setSelectedBullet(paragraph)}>
                    {paragraph}
                  </button>
                </p>
              );
            })}
          </div>
        )}

        {!documentId && !documents.isPending && saved.length === 0 && (
          <p className="text-sm text-neutral-500">
            No documents yet. Pick an analyzed job above and generate one.
          </p>
        )}
      </div>

      {doc && showPreview && (
        <div className="w-full shrink-0 xl:w-96">
          <DocumentPreview documentId={doc.id} template={template} />
        </div>
      )}

      {activeClaim && (
        <aside
          className="w-72 shrink-0 space-y-2 rounded-lg border border-neutral-200 p-3 text-sm dark:border-neutral-800"
          aria-label="Claim provenance"
          aria-live="polite"
        >
          <div className="font-medium">Provenance</div>
          <div>
            Status: <span className="font-mono">{activeClaim.verification_status}</span>
          </div>
          {activeClaim.evidence_title && <div>Evidence: {activeClaim.evidence_title}</div>}
          {activeClaim.evidence_repository && (
            <div className="font-mono text-xs">{activeClaim.evidence_repository}</div>
          )}
          {activeClaim.source_locator && (
            <div className="font-mono text-xs text-neutral-500">{activeClaim.source_locator}</div>
          )}
          <div className="text-xs text-neutral-500">
            confidence {Math.round(activeClaim.confidence * 100)}%
          </div>
        </aside>
      )}
    </div>
  );
}
