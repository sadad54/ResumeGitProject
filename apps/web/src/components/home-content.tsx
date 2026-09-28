"use client";

import Link from "next/link";
import { Skeleton } from "@proofhire/design-system/ui";
import { useOverview, type Overview } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { AuthPanel } from "./auth-panel";

export function HomeContent() {
  const { status } = useSession();
  if (status === "authenticated") return <WorkspaceOverview />;
  if (status === "anonymous") return <Landing />;
  return <Skeleton lines={6} label="Loading" />;
}

function Landing() {
  return (
    <div className="ph-hero">
      <div className="ph-hero-copy">
        <span className="ph-eyebrow">Evidence-grounded AI career agent</span>
        <h1>
          Every resume claim, traced to the code that proves it
          <span className="ph-accent">.</span>
        </h1>
        <p>
          ProofHire reads your GitHub repositories, builds an evidence graph with provenance
          for every item, matches it to a job description with hybrid retrieval, and writes a
          resume in which every claim is checked against that evidence. Claims it can&apos;t
          support are blocked from export.
        </p>
        <ul className="ph-points">
          <li>
            <strong>Evidence from real code.</strong> Manifests, CI, infrastructure and source
            are classified and cited down to the file and commit.
          </li>
          <li>
            <strong>Requirement-by-requirement coverage.</strong> Lexical, vector and skill
            signals fused, then reranked into Strong, Partial or Gap.
          </li>
          <li>
            <strong>Claims that cite their sources.</strong> An independent verifier and a
            deterministic fact guard check every bullet before it reaches a PDF.
          </li>
        </ul>
        <p className="ph-hero-meta">
          <a
            className="ph-text-button"
            href="https://github.com/sadad54/ResumeGitProject"
            rel="noreferrer"
            target="_blank"
          >
            Source on GitHub
          </a>
        </p>
      </div>
      <AuthPanel />
    </div>
  );
}

type Step = { done: boolean; label: string; href: string; action: string };

function steps(o: Overview): Step[] {
  return [
    { done: o.github.connected, label: "Connect GitHub", href: "/settings#github", action: "Connect" },
    {
      done: o.repositories.synced > 0,
      label: "Select and sync repositories",
      href: "/settings#github",
      action: "Choose repositories",
    },
    {
      done: o.evidence.confirmed > 0,
      label: "Review the evidence found in your code",
      href: "/evidence#review",
      action: "Review evidence",
    },
    { done: o.jobs.ready > 0, label: "Analyze a job description", href: "/jobs", action: "Analyze a job" },
    {
      done: o.documents.total > 0,
      label: "Generate a verified resume or cover letter",
      href: "/documents",
      action: "Generate",
    },
  ];
}

function WorkspaceOverview() {
  const { user, isDemo } = useSession();
  const overview = useOverview();

  if (overview.isPending) return <Skeleton lines={6} label="Loading your workspace" />;
  if (overview.isError)
    return (
      <p className="ph-error" role="alert">
        Couldn&apos;t load your workspace. {overview.error.message}
      </p>
    );

  const o = overview.data;
  const plan = steps(o);
  const next = isDemo ? undefined : plan.find((s) => !s.done);

  return (
    <div className="space-y-8">
      <div className="ph-workspace-heading">
        <div>
          <span className="ph-eyebrow">{isDemo ? "Demo workspace" : "Your workspace"}</span>
          <h1 className="text-3xl font-semibold mt-2">
            {isDemo ? "A real account, end to end" : `Welcome back${user?.display_name ? `, ${user.display_name}` : ""}`}
            <span className="ph-accent">.</span>
          </h1>
          <p className="mt-2">
            {o.github.connected
              ? `GitHub connected as @${o.github.login}${o.github.last_sync_at ? ` · last synced ${new Date(o.github.last_sync_at).toLocaleString()}` : ""}.`
              : "GitHub isn't connected yet."}
          </p>
          {o.repositories.in_progress > 0 && (
            <p className="mt-2 text-sm" role="status" aria-live="polite">
              Finding evidence in {o.repositories.in_progress}{" "}
              {o.repositories.in_progress === 1 ? "repository" : "repositories"}… these
              numbers update as it finishes.
            </p>
          )}
        </div>
        {next && (
          <Link className="ph-button ph-button-primary" href={next.href}>
            Next: {next.action} →
          </Link>
        )}
      </div>

      <dl className="ph-stat-grid">
        <Stat label="Repositories synced" value={o.repositories.synced} of={o.repositories.total} href="/settings#github" />
        <Stat
          label="Evidence confirmed"
          value={o.evidence.confirmed}
          of={o.evidence.total}
          note={o.evidence.candidate ? `${o.evidence.candidate} awaiting review` : undefined}
          href="/evidence"
        />
        <Stat label="Jobs analyzed" value={o.jobs.ready} of={o.jobs.total} href="/jobs" />
        <Stat label="Documents exported" value={o.documents.exported} of={o.documents.total} href="/documents" />
        <Stat label="Applications in progress" value={o.applications.active} of={o.applications.total} href="/applications" />
      </dl>

      <section aria-labelledby="pipeline-heading">
        <h2 id="pipeline-heading" className="text-lg font-semibold">
          From repository to verified resume
        </h2>
        <ol className="ph-steps">
          {plan.map((step) => (
            <li key={step.label} data-done={step.done}>
              <span aria-hidden="true">{step.done ? "✓" : "○"}</span>
              <span className="sr-only">{step.done ? "Done: " : "To do: "}</span>
              {step.done ? (
                step.label
              ) : (
                <Link className="ph-text-button" href={step.href}>
                  {step.label}
                </Link>
              )}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  of,
  note,
  href,
}: {
  label: string;
  value: number;
  of: number;
  note?: string;
  href: string;
}) {
  return (
    <div className="ph-stat">
      <dt>{label}</dt>
      <dd>
        <Link href={href}>
          <b>{value}</b>
          <span> of {of}</span>
        </Link>
        {note && <small>{note}</small>}
      </dd>
    </div>
  );
}
