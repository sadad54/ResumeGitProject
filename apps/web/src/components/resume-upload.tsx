"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { api, unwrap } from "@/lib/api-client";
import { qk, useProfileFacts, type ProfileFact } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { DEMO_READ_ONLY } from "./session-ui";

/**
 * Resume upload -> ProfileFact extraction and confirmation (PRD §13, Phase 5).
 * A fact stays unconfirmed (and so unusable by the fact guard/writer) until
 * the user reviews and confirms it — no ProfileFact is trusted sight-unseen.
 */
export function ResumeUpload() {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const facts = useProfileFacts();

  const upload = useMutation({
    // Multipart, so the untyped helper (it still goes through authFetch).
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiFetch<ProfileFact[]>("/api/v1/profile/resume", { method: "POST", body: form });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.facts }),
  });
  const confirm = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.PATCH("/api/v1/profile/facts/{fact_id}", {
          params: { path: { fact_id: id } },
          body: { confirmed: true },
        }),
      ),
    onSuccess: (updated) =>
      queryClient.setQueryData<ProfileFact[]>(qk.facts, (list) =>
        list?.map((f) => (f.id === updated.id ? updated : f)),
      ),
  });

  return (
    <div className="space-y-3">
      <label className="ph-field">
        Resume (PDF or DOCX)
        <input
          type="file"
          accept=".pdf,.docx"
          disabled={!canWrite || upload.isPending}
          title={!canWrite ? DEMO_READ_ONLY : undefined}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
      </label>
      {upload.isPending && (
        <p role="status" className="text-xs text-neutral-500">
          Extracting facts…
        </p>
      )}
      {(upload.isError || confirm.isError) && (
        <p className="ph-error" role="alert">
          {(upload.error ?? confirm.error)?.message}
        </p>
      )}
      {facts.data && facts.data.length > 0 && (
        <ul className="space-y-1">
          {facts.data.map((fact) => (
            <li
              key={fact.id}
              className="flex items-center justify-between gap-3 rounded border border-neutral-200 px-2 py-1.5 text-sm dark:border-neutral-800"
            >
              <span>
                <span className="mr-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs dark:bg-neutral-800">
                  {fact.type}
                </span>
                {Object.values(fact.value_json).filter(Boolean).join(" — ")}
              </span>
              {fact.confirmed ? (
                <span className="text-xs ph-ok">✓ confirmed</span>
              ) : (
                <button
                  type="button"
                  className="ph-button"
                  disabled={!canWrite || confirm.isPending}
                  onClick={() => confirm.mutate(fact.id)}
                >
                  Confirm
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
