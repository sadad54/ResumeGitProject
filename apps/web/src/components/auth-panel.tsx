"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@proofhire/design-system/ui";
import { api, unwrap } from "@/lib/api-client";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";

function message(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

/** Sign in, sign up, or step into the read-only demo. */
export function AuthPanel() {
  const { signIn, startDemo } = useSession();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = useMutation({
    mutationFn: async () =>
      mode === "login"
        ? unwrap(await api.POST("/api/v1/auth/login", { body: { email, password } }))
        : unwrap(await api.POST("/api/v1/auth/signup", { body: { email, password } })),
    onSuccess: signIn,
  });
  const demo = useMutation({ mutationFn: startDemo });
  const busy = submit.isPending || demo.isPending;

  return (
    <div className="ph-auth" id="sign-in">
      <div className="ph-segment" role="group" aria-label="Sign in or create an account">
        {(["login", "signup"] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            className="ph-button"
            onClick={() => {
              setMode(m);
              submit.reset();
            }}
          >
            {m === "login" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>
      <form
        className="ph-auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate();
        }}
      >
        <label className="ph-field">
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="ph-field">
          Password{mode === "signup" && " (at least 8 characters)"}
          <input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {submit.isError && (
          <p className="ph-error" role="alert">
            {message(submit.error, "Something went wrong. Try again.")}
          </p>
        )}
        <Button type="submit" className="ph-button-primary" disabled={busy}>
          {submit.isPending ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>
      <div className="ph-auth-demo">
        <span>No account yet?</span>
        <Button type="button" disabled={busy} onClick={() => demo.mutate()}>
          {demo.isPending ? "Opening demo…" : "Explore the live demo →"}
        </Button>
        {demo.isError && (
          <p className="ph-error" role="alert">
            {message(demo.error, "The demo is unavailable right now.")}
          </p>
        )}
      </div>
    </div>
  );
}
