"use client";

import { useQuery } from "@tanstack/react-query";
import { apiBaseUrl, authFetch, errorFromResponse } from "@/lib/api";

/**
 * Live preview of the export (checklist §10.7). Fetches HTML from the API's
 * preview endpoint — the same template renderer the PDF uses — and shows it
 * in a fully sandboxed iframe, re-rendering whenever the template changes.
 * Cached per (document, template), so flipping back to a template is instant.
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
  const preview = useQuery({
    queryKey: ["documents", documentId, "preview", template],
    queryFn: async ({ signal }) => {
      const response = await authFetch(
        `${apiBaseUrl()}/api/v1/documents/${encodeURIComponent(documentId)}/preview?template=${encodeURIComponent(template)}`,
        { signal },
      );
      if (!response.ok) throw await errorFromResponse(response);
      return response.text();
    },
    placeholderData: (previous) => previous,
    staleTime: 5 * 60_000,
  });

  const state = preview.isError ? "error" : preview.isFetching ? "loading" : "ready";
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
          preview.data === undefined && state === "loading" ? "ph-skeleton" : ""
        }`}
        style={{ aspectRatio: "8.5 / 11" }}
      >
        {preview.data !== undefined && (
          <iframe
            title="Document preview"
            sandbox=""
            srcDoc={preview.data}
            className="h-full w-full rounded-lg"
            style={{ opacity: state === "ready" ? 1 : 0.4 }}
          />
        )}
      </div>
    </div>
  );
}
