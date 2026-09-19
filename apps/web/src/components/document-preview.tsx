"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl, getAccessToken } from "@/lib/api";

/**
 * Live preview of the export (checklist §10.7). Fetches HTML from the API's
 * preview endpoint — the same template renderer the PDF uses — and shows it
 * in a fully sandboxed iframe, re-rendering whenever the template changes.
 *
 * `sandbox` with no allow-* tokens means the document can't run script, submit
 * forms, or navigate the parent, on top of the CSP the endpoint already sets.
 */
export function DocumentPreview({
  documentId,
  template,
}: {
  documentId: string;
  template: string;
}) {
  const [html, setHtml] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    const token = getAccessToken();
    fetch(
      `${apiBaseUrl()}/api/v1/documents/${encodeURIComponent(documentId)}/preview?template=${encodeURIComponent(template)}`,
      {
        signal: controller.signal,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    )
      .then(async (r) => {
        if (!r.ok) throw new Error(String(r.status));
        setHtml(await r.text());
        setState("ready");
      })
      .catch((err) => {
        if (!controller.signal.aborted) setState("error");
        void err;
      });
    return () => controller.abort();
  }, [documentId, template]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-neutral-500">
        <span>Export preview</span>
        <span role="status" aria-live="polite">
          {state === "loading" && "Rendering…"}
          {state === "error" && "Preview unavailable"}
        </span>
      </div>
      <div
        className={`relative rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 ${
          state === "loading" ? "ph-skeleton" : ""
        }`}
        style={{ aspectRatio: "8.5 / 11" }}
      >
        {html !== null && (
          <iframe
            title="Document preview"
            sandbox=""
            srcDoc={html}
            className="h-full w-full rounded-lg"
            style={{ opacity: state === "ready" ? 1 : 0.4 }}
          />
        )}
      </div>
    </div>
  );
}
