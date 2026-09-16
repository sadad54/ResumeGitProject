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
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="ph-empty">
      <h3>{title}</h3>
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
