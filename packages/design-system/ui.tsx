import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`ph-button ${className}`} {...props} />;
}

export function StatusPill({ status }: { status: string }) {
  const symbols: Record<string, string> = {
    strong: "✓",
    partial: "◐",
    gap: "×",
    unknown: "?",
    confirmed: "✓",
    candidate: "○",
  };
  return (
    <span className={`ph-status ph-status-${status}`}>
      <span aria-hidden="true">{symbols[status] ?? "·"}</span>{" "}
      {status === "candidate" ? "Needs review" : status}
    </span>
  );
}

export function EmptyState({
  title,
  children,
  level = "h3",
}: {
  title: string;
  children: ReactNode;
  /** Defaults to h3 (the common case: nested under a section's own h2).
   * Pass "h2" when this is the first heading-bearing content on the page,
   * directly under the page's h1 — otherwise heading order skips a level. */
  level?: "h2" | "h3";
}) {
  const Heading = level;
  return (
    <div className="ph-empty">
      <Heading>{title}</Heading>
      <p>{children}</p>
    </div>
  );
}

export function ConfidenceIndicator({ value }: { value: number }) {
  return (
    <span className="ph-confidence">
      <meter min={0} max={1} value={value} aria-label="Evidence confidence" />{" "}
      {Math.round(value * 100)}% confidence
    </span>
  );
}

/**
 * Content-shaped loading placeholder. `lines` renders that many text-width
 * bars; `height` renders a single block (e.g. for a chart or preview). The
 * visible label is for screen readers only — the shape itself is the visual
 * signal, and a "Loading…" caption inside every skeleton would be noise.
 */
export function Skeleton({
  lines = 3,
  height,
  label = "Loading",
}: {
  lines?: number;
  height?: string;
  label?: string;
}) {
  if (height) {
    return (
      <div className="ph-skeleton" style={{ height }} role="status" aria-label={label}>
        <span className="sr-only">{label}…</span>
      </div>
    );
  }
  const widths = ["92%", "78%", "85%", "64%", "88%", "71%"];
  return (
    <div role="status" aria-label={label} className="space-y-2">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="ph-skeleton-line"
          style={{ width: widths[i % widths.length] }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

/** A list of card-shaped skeletons, for list pages while their query runs. */
export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div role="status" aria-label="Loading list" className="space-y-3">
      <span className="sr-only">Loading list…</span>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="ph-source space-y-2" aria-hidden="true">
          <div className="ph-skeleton-line" style={{ width: "40%" }} />
          <div className="ph-skeleton-line" style={{ width: "88%" }} />
          <div className="ph-skeleton-line" style={{ width: "70%" }} />
        </div>
      ))}
    </div>
  );
}
