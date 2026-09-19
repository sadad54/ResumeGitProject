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

export function Skeleton() {
  return (
    <div className="ph-skeleton" role="status">
      Loading evidence…
    </div>
  );
}
