"use client";

import { useState } from "react";
import { apiFetch, ApiError, setTokens, getAccessToken } from "@/lib/api";

type TokenResponse = { access_token: string; refresh_token: string };

export function AuthPanel({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (typeof window !== "undefined" && getAccessToken()) {
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<TokenResponse>(`/api/v1/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setTokens(result.access_token, result.refresh_token);
      onAuthed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-sm rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="mb-3 flex gap-2 text-sm">
        <button
          className={mode === "login" ? "font-semibold" : "text-neutral-500"}
          onClick={() => setMode("login")}
        >
          Log in
        </button>
        <button
          className={mode === "signup" ? "font-semibold" : "text-neutral-500"}
          onClick={() => setMode("signup")}
        >
          Sign up
        </button>
      </div>
      <form onSubmit={submit} className="space-y-2">
        <input
          type="email"
          placeholder="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
        <input
          type="password"
          placeholder="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-neutral-900 px-2 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {loading ? "..." : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </form>
    </div>
  );
}
