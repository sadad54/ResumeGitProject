/**
 * Line diff for the resume diff viewer (PRD §11 "before/after tailoring",
 * checklist §10.8).
 *
 * Classic LCS over lines. Documents here are small (tens of bullets), so the
 * O(n·m) table is fine and a dependency-free implementation is preferable to
 * pulling in a diff library for one screen.
 */

export type DiffOp = "equal" | "added" | "removed";

export interface DiffLine {
  op: DiffOp;
  text: string;
}

export function diffLines(before: string[], after: string[]): DiffLine[] {
  const n = before.length;
  const m = after.length;
  const w = m + 1;
  // lcs[i*w + j] = length of LCS of before[i..] and after[j..]. A flat typed
  // array keeps every index defined, which the strict indexed-access setting
  // requires, and avoids allocating n+1 row arrays.
  const lcs = new Uint16Array((n + 1) * w);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i * w + j] =
        before[i] === after[j]
          ? (lcs[(i + 1) * w + j + 1] ?? 0) + 1
          : Math.max(lcs[(i + 1) * w + j] ?? 0, lcs[i * w + j + 1] ?? 0);
    }
  }

  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    const b = before[i] ?? "";
    const a = after[j] ?? "";
    if (b === a) {
      out.push({ op: "equal", text: b });
      i++;
      j++;
    } else if ((lcs[(i + 1) * w + j] ?? 0) >= (lcs[i * w + j + 1] ?? 0)) {
      // Prefer emitting removals first so a replaced line reads as
      // "- old / + new", which is what people expect from a diff.
      out.push({ op: "removed", text: b });
      i++;
    } else {
      out.push({ op: "added", text: a });
      j++;
    }
  }
  while (i < n) out.push({ op: "removed", text: before[i++] ?? "" });
  while (j < m) out.push({ op: "added", text: after[j++] ?? "" });
  return out;
}

export interface DiffSummary {
  added: number;
  removed: number;
  unchanged: number;
}

export function summarize(lines: DiffLine[]): DiffSummary {
  return lines.reduce(
    (acc, l) => {
      if (l.op === "added") acc.added++;
      else if (l.op === "removed") acc.removed++;
      else acc.unchanged++;
      return acc;
    },
    { added: 0, removed: 0, unchanged: 0 },
  );
}

/**
 * Flatten a generated document's content into comparable lines. Section
 * headers are included so a bullet moving between roles shows as a move
 * rather than silently matching.
 */
export function documentToLines(content: unknown): string[] {
  if (!content || typeof content !== "object") return [];
  const c = content as Record<string, unknown>;

  if (Array.isArray(c.body_paragraphs)) {
    return (c.body_paragraphs as unknown[]).map(String);
  }

  const lines: string[] = [];
  if (typeof c.summary === "string") lines.push(`Summary: ${c.summary}`);
  if (Array.isArray(c.skills)) lines.push(`Skills: ${(c.skills as unknown[]).join(", ")}`);
  if (Array.isArray(c.experience)) {
    for (const entry of c.experience as Record<string, unknown>[]) {
      lines.push(`## ${entry.title ?? ""} — ${entry.employer ?? ""}`);
      if (Array.isArray(entry.bullets)) {
        for (const b of entry.bullets as unknown[]) lines.push(`• ${String(b)}`);
      }
    }
  }
  return lines;
}
