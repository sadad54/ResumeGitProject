"use client";

import { useMemo } from "react";
import { diffLines, documentToLines, summarize } from "@/lib/diff";

/**
 * Before/after diff between two generated documents (PRD §11, checklist
 * §10.8). Colour is never the only signal: every line carries a leading
 * `+` / `−` / ` ` glyph and an sr-only label, per the WCAG non-colour-only
 * requirement the rest of the UI follows.
 */
export function DocumentDiff({
  before,
  after,
  beforeLabel,
  afterLabel,
}: {
  before: unknown;
  after: unknown;
  beforeLabel: string;
  afterLabel: string;
}) {
  const lines = useMemo(
    () => diffLines(documentToLines(before), documentToLines(after)),
    [before, after],
  );
  const totals = useMemo(() => summarize(lines), [lines]);

  return (
    <section
      aria-label={`Changes from ${beforeLabel} to ${afterLabel}`}
      className="rounded-lg border border-neutral-200 dark:border-neutral-800"
    >
      <div className="flex flex-wrap items-center gap-3 border-b border-neutral-200 px-3 py-2 text-xs dark:border-neutral-800">
        <span className="font-medium">
          {beforeLabel} → {afterLabel}
        </span>
        <span role="status">
          <span className="text-green-700 dark:text-green-400">+{totals.added}</span>{" "}
          <span className="text-red-700 dark:text-red-400">−{totals.removed}</span>{" "}
          <span className="text-neutral-500">{totals.unchanged} unchanged</span>
        </span>
      </div>
      <ol className="max-h-[28rem] overflow-auto font-mono text-xs leading-5" data-testid="diff-lines">
        {lines.map((line, i) => {
          const glyph = line.op === "added" ? "+" : line.op === "removed" ? "−" : " ";
          const tone =
            line.op === "added"
              ? "bg-green-50 text-green-900 dark:bg-green-950/40 dark:text-green-200"
              : line.op === "removed"
                ? "bg-red-50 text-red-900 line-through decoration-red-400/60 dark:bg-red-950/40 dark:text-red-200"
                : "text-neutral-700 dark:text-neutral-300";
          return (
            <li key={i} data-op={line.op} className={`flex gap-2 px-3 py-0.5 ${tone}`}>
              <span aria-hidden="true" className="w-3 shrink-0 select-none text-center">
                {glyph}
              </span>
              <span className="sr-only">
                {line.op === "added" ? "Added: " : line.op === "removed" ? "Removed: " : ""}
              </span>
              <span className="whitespace-pre-wrap break-words">{line.text}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
