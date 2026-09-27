"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@proofhire/design-system/ui";
import { api } from "@/lib/api-client";
import { clearTokens } from "@/lib/api";
import { useSession } from "@/lib/session";
import { DEMO_READ_ONLY } from "./session-ui";

const CONFIRMATION = "delete my account";

/** Identity, sign-out and permanent deletion (ADR-0016: a hard delete). */
export function AccountSettings() {
  const { user, isDemo, canWrite, signOut } = useSession();
  const router = useRouter();
  const [confirm, setConfirm] = useState("");
  const remove = useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/auth/me");
    },
    onSuccess: async () => {
      // The account and its tokens no longer exist server-side.
      clearTokens();
      await signOut();
      router.push("/");
    },
  });

  if (!user) return null;
  return (
    <div className="space-y-6">
      <dl className="ph-facts">
        <div>
          <dt>Email</dt>
          <dd>{isDemo ? "Shared demo account" : user.email}</dd>
        </div>
        <div>
          <dt>Member since</dt>
          <dd>{new Date(user.created_at).toLocaleDateString()}</dd>
        </div>
      </dl>
      <Button onClick={() => void signOut()}>Sign out</Button>

      <section className="ph-danger" aria-labelledby="delete-heading">
        <h3 id="delete-heading">Delete account</h3>
        <p>
          Permanently deletes your account and everything in it: repositories, evidence,
          jobs, generated documents and exported files. This can&apos;t be undone.
        </p>
        <label className="ph-field">
          Type “{CONFIRMATION}” to confirm
          <input
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={!canWrite}
            autoComplete="off"
          />
        </label>
        <Button
          className="ph-button-danger"
          disabled={!canWrite || confirm.trim().toLowerCase() !== CONFIRMATION || remove.isPending}
          title={!canWrite ? DEMO_READ_ONLY : undefined}
          onClick={() => remove.mutate()}
        >
          {remove.isPending ? "Deleting…" : "Delete my account permanently"}
        </Button>
        {remove.isError && (
          <p className="ph-error" role="alert">
            {remove.error.message}
          </p>
        )}
      </section>
    </div>
  );
}
