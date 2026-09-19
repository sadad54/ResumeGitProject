"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, getAccessToken } from "@/lib/api";
import { Button } from "@proofhire/design-system/ui";

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
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    setSignedIn(!!getAccessToken());
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
      const job = await apiFetch<{ id: string }>("/api/v1/jobs/capture", {
        method: "POST",
        body: JSON.stringify(capture),
      });
      setJobId(job.id);
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
      {!signedIn && (
        <p>
          Sign in on{" "}
          <Link href="/" target="_blank" className="ph-text-button">
            Home in a new tab
          </Link>
          , then{" "}
          <Button onClick={() => setSignedIn(!!getAccessToken())}>
            Check sign-in
          </Button>
          . Your session stays in the web app.
        </p>
      )}
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
              !signedIn || busy || capture.selected_text.trim().length < 40
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
