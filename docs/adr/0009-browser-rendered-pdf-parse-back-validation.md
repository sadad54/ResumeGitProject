# ADR-0009: Browser-rendered PDF + parse-back validation

## Status
Accepted

## Context
PRD §21 requires PDF generation via Playwright/Chromium plus a parse-back
validator that confirms the rendered PDF's actual text content matches what
was generated — catching rendering bugs (overflow, encoding corruption, a
CSS change silently dropping content) that a purely visual check would miss.

Before committing to final template CSS, the build plan calls for a spike on:
1. Which text-extraction library to use (`pypdf` vs `pdfplumber`).
2. What normalization/matching rule the validator applies.

## Spike results
Rendered a representative single-column resume layout (heading, contact line
with `|` separator, section headers, bullets with em-dashes/en-dashes/
percentages) via Playwright, then extracted text with both libraries.

**Result: identical output from both libraries** for this layout. Both
correctly preserved punctuation, dashes (`—`, `–`), percentages, and line
structure. No fidelity difference observed.

Testing whitespace-collapsed, lowercased substring containment
(`" ".join(text.split()).lower()`, then `expected in actual`) against 11
representative strings (name, email, section headers, full sentences with
punctuation, a comma-separated skills list) — all 11 matched correctly with
zero false negatives.

## Decision
- Use **pypdf** for parse-back extraction, not pdfplumber. Given no observed
  fidelity difference for ProofHire's single-column ATS-safe template
  (PRD §21 explicitly requires single-column ATS-safe layout), and pypdf is
  already a dependency (Phase 5 resume upload parsing) — avoids adding
  pdfplumber as a second, redundant PDF library.
- Use **whitespace-collapse + lowercase + substring containment** as the
  matching rule: `" ".join(text.split()).lower()` on both the extracted PDF
  text and the expected string, then check containment. This is simple,
  fast, and the spike confirms it handles real content patterns (dashes,
  percentages, multi-sentence bullets) correctly without over-engineering a
  fuzzy-matching scheme V1 doesn't need.
- If a future template introduces multi-column layouts, this decision must be
  revisited — multi-column PDF text extraction commonly reorders text in ways
  that break simple substring matching. Single-column-only is itself a PRD
  §21 requirement ("single-column ATS-safe option"), so this is not expected
  to be a near-term concern.

## Consequences
- `apps/worker/proofhire_worker/render/parse_back.py` implements this exact
  rule: extract via pypdf, normalize both sides, check required section
  headers and every SUPPORTED claim's text are present as substrings.
- A parse-back failure (missing expected content) fails the export — the PDF
  is not returned to the user until the underlying rendering bug is fixed.
