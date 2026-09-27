"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@proofhire/design-system/ui";
import { api, unwrap } from "@/lib/api-client";
import { qk } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { DEMO_READ_ONLY } from "./session-ui";

type Capture = {
  capture_id: string;
  selected_text: string;
  page_url: string | null;
  title: string | null;
  captured_at: string;
};
type ExtensionRuntime = {
  sendMessage: (
    id: string,
    message: object,
    callback: (result: { payload?: Capture; error?: string }) => void,
  ) => void;
  lastError?: { message?: string };
};

export function CaptureHandoff({
  extensionId,
  captureId,
}: {
  extensionId: string;
  captureId: string;
}) {
  const [capture, setCapture] = useState<Capture | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState("");
  // Signing in on another tab updates this page by itself (the session
  // provider follows localStorage across tabs), so no "check again" step.
  const { status, canWrite } = useSession();
  const signedIn = status === "authenticated";
  const queryClient = useQueryClient();
  useEffect(() => {
    const runtime = (
      window as unknown as { chrome?: { runtime?: ExtensionRuntime } }
    ).chrome?.runtime;
    if (
      !runtime ||
      !/^[a-p]{32}$/.test(extensionId) ||
      !/^[0-9a-f-]{36}$/.test(captureId)
    ) {
      setError(
        "Open this page from the ProofHire extension, or paste the description in Jobs.",
      );
      return;
    }
    let cancelled = false;
    runtime.sendMessage(
      extensionId,
      { type: "read-capture", capture_id: captureId },
      (result) => {
        const runtimeError = runtime.lastError;
        if (cancelled) return;
        if (
          runtimeError ||
          !result?.payload ||
          result.payload.capture_id !== captureId
        ) {
          setError(
            result?.error ||
              "Could not retrieve this capture. Select the job again.",
          );
          return;
        }
        setCapture(result.payload);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [extensionId, captureId]);
  async function submit() {
    if (!capture) return;
    setBusy(true);
    setError("");
    try {
      const job = unwrap(await api.POST("/api/v1/jobs/capture", { body: capture }));
      setJobId(job.id);
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      const runtime = (
        window as unknown as { chrome?: { runtime?: ExtensionRuntime } }
      ).chrome?.runtime;
      runtime?.sendMessage(
        extensionId,
        { type: "finish-capture", capture_id: captureId },
        () => {
          void runtime.lastError;
        },
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Capture failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="space-y-5">
      <h1 className="text-3xl font-semibold">Your next opportunity.</h1>
      <p>Review the selected text, then save it to your ProofHire account.</p>
      {error && (
        <p role="alert" className="ph-error">
          {error}
        </p>
      )}
      {status === "anonymous" && (
        <p>
          <Link href="/#sign-in" target="_blank" className="ph-text-button">
            Sign in in a new tab
          </Link>
          ; this page picks up the session as soon as you do. Your session stays in the
          web app.
        </p>
      )}
      {signedIn && !canWrite && <p role="note">{DEMO_READ_ONLY}.</p>}
      {capture && !jobId && (
        <>
          <p className="text-sm">
            {capture.title}
            {capture.page_url && (
              <span className="block break-all">{capture.page_url}</span>
            )}
          </p>
          {!capture.selected_text && (
            <p>No text was selected. Paste the job description below.</p>
          )}
          <label className="ph-field">
            Job description
            <textarea
              rows={14}
              maxLength={60000}
              value={capture.selected_text}
              onChange={(e) =>
                setCapture({ ...capture, selected_text: e.target.value })
              }
            />
          </label>
          <Button
            disabled={
              !canWrite || busy || capture.selected_text.trim().length < 40
            }
            onClick={() => void submit()}
          >
            {busy ? "Saving…" : "Save job"}
          </Button>
        </>
      )}
      {jobId && (
        <div role="status">
          <p>Job saved to your workspace.</p>
          <Link
            className="ph-button inline-block mt-3"
            href={`/jobs?job=${jobId}`}
          >
            Open analysis →
          </Link>
        </div>
      )}
      <Link className="ph-text-button block" href="/jobs">
        Go to Jobs
      </Link>
    </section>
  );
}
