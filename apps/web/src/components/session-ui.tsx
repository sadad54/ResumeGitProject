"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Skeleton } from "@proofhire/design-system/ui";
import { useSession } from "@/lib/session";

/** Top-bar identity: who you are and how to leave, or how to get in. */
export function UserMenu() {
  const { status, user, isDemo, signOut } = useSession();
  if (status === "loading") return <span className="ph-user" aria-hidden="true" />;
  if (status !== "authenticated" || !user) {
    return (
      <Link className="ph-button" href="/#sign-in">
        Sign in
      </Link>
    );
  }
  return (
    <span className="ph-user">
      <span className="ph-user-name" title={user.email}>
        {isDemo ? "Demo guest" : (user.display_name ?? user.email)}
      </span>
      <button type="button" className="ph-button" onClick={() => void signOut()}>
        Sign out
      </button>
    </span>
  );
}

/** Session-level notices shown above every page. */
export function SessionBanners() {
  const { status, isDemo, expired, dismissExpired, retry } = useSession();
  return (
    <>
      {expired && status === "anonymous" && (
        <div className="ph-banner ph-banner-warn" role="alert">
          <span>Your session ended. Sign in again to pick up where you left off.</span>
          <Link className="ph-text-button" href="/#sign-in" onClick={dismissExpired}>
            Sign in
          </Link>
        </div>
      )}
      {status === "unreachable" && (
        <div className="ph-banner ph-banner-warn" role="status" aria-live="polite">
          <span>
            Connecting to the ProofHire API… The free-tier backend sleeps when idle, so the
            first request can take up to a minute.
          </span>
          <button type="button" className="ph-text-button" onClick={retry}>
            Retry now
          </button>
        </div>
      )}
      {isDemo && (
        <div className="ph-banner" role="note">
          <span>
            You&apos;re exploring a <strong>read-only demo</strong>: a real account whose
            evidence, analysis and documents were produced by the live pipeline. Sign up to
            connect your own GitHub.
          </span>
        </div>
      )}
    </>
  );
}

/**
 * Renders children only with a session; otherwise the matching state. Every
 * page used to do this itself from localStorage, each with its own wording.
 */
export function RequireSession({
  children,
  what,
}: {
  children: ReactNode;
  /** Completes "Sign in to …". */
  what: string;
}) {
  const { status } = useSession();
  if (status === "loading" || status === "unreachable") {
    return <Skeleton lines={4} label="Loading your workspace" />;
  }
  if (status === "anonymous") {
    return (
      <div className="ph-empty">
        <h2>Sign in to {what}</h2>
        <p>
          <Link className="ph-text-button" href="/#sign-in">
            Sign in or create an account
          </Link>{" "}
          — or explore the read-only demo from the home page.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}

/** Explains why a control is disabled for the demo account. */
export const DEMO_READ_ONLY = "Read-only demo — sign up to make changes";
