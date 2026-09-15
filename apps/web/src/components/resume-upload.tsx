"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError, getAccessToken } from "@/lib/api";

type ProfileFact = {
  id: string;
  type: string;
  value_json: Record<string, string>;
  source: string;
  immutable: boolean;
  confirmed: boolean;
};

/**
 * Resume upload -> ProfileFact extraction and confirmation (PRD §13, Phase 5).
 * A fact stays unconfirmed (and so unusable by the fact guard/writer) until
 * the user reviews and confirms it — no ProfileFact is trusted sight-unseen.
 */
export function ResumeUpload() {
  const [facts, setFacts] = useState<ProfileFact[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) return;
    void loadFacts();
  }, []);

  async function loadFacts() {
    try {
      const result = await apiFetch<ProfileFact[]>("/api/v1/profile/facts");
      setFacts(result);
    } catch {
      // silent — page still usable without facts loaded
    }
  }

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await apiFetch("/api/v1/profile/resume", { method: "POST", body: formData });
      await loadFacts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to process resume");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function confirmFact(id: string) {
    const updated = await apiFetch<ProfileFact>(`/api/v1/profile/facts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ confirmed: true }),
    });
    setFacts((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
  }

  if (!getAccessToken()) return null;

  return (
    <div className="space-y-3">
      <div>
        <input type="file" accept=".pdf,.docx" onChange={upload} disabled={uploading} className="text-sm" />
        {uploading && <span className="ml-2 text-xs text-neutral-500">Processing...</span>}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {facts.length > 0 && (
        <ul className="space-y-1">
          {facts.map((fact) => (
            <li key={fact.id} className="flex items-center justify-between rounded border border-neutral-200 px-2 py-1.5 text-sm dark:border-neutral-800">
              <span>
                <span className="mr-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs dark:bg-neutral-800">
                  {fact.type}
                </span>
                {Object.values(fact.value_json).filter(Boolean).join(" — ")}
              </span>
              {fact.confirmed ? (
                <span className="text-xs text-green-600">confirmed</span>
              ) : (
                <button
                  onClick={() => confirmFact(fact.id)}
                  className="rounded border border-neutral-300 px-2 py-0.5 text-xs dark:border-neutral-700"
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
