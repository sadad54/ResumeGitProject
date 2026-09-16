# ADR-0014: Evidence Constellation is a bounded read-only projection

Status: Accepted for phase 7 implementation.

`GET /api/v1/evidence/graph` projects existing repositories, evidence, skills, sources, requirements and matches. There are no new graph domain tables. IDs are namespaced (`project:`, `evidence:`, `skill:`, `requirement:`). Architecture evidence is displayed with a distinct node kind without inventing a second fact. An optional `job_id` adds requirements, and `repository_id` filters the evidence inventory. Both filter IDs must belong to the requesting user; inaccessible IDs return 404.

The default evidence limit is 200 (maximum 1000); requirements are capped at 500. Overflow is explicitly signaled. Unprovenanced, superseded, stale, private and rejected evidence is excluded. Candidate evidence is visible for review but cannot illuminate job matches. Malformed cross-repository provenance is excluded. Only confirmed visible evidence can connect to requirements. Sources link to the exact commit and line locator; source contents and tokens are not sent in the projection.

Strong and Partial labels are preserved verbatim. No match is Unknown while computation is pending/failed or an existing match is hidden by filtering/review. A completed job with no recorded candidate match is Gap. During reanalysis old match edges are suppressed. The worker atomically replaces prior matches when recomputing so old winners cannot accumulate.

Additive job status strings `matching`, `ready`, and `coverage_failed` distinguish extraction from coverage completion. They use the existing string column; no shared enum is changed. Pre-phase-7 jobs with ambiguous `analyzed` status retain Unknown for unmatched requirements until reanalyzed. Polling is bounded and refresh remains available; no new SSE event contract is introduced.

React Flow renders the projection with a deterministic column layout, weighted edges, source inspection and job overlay transitions. The same response backs an accessible node/relationship table and coverage matrix. The mobile default is the table. Motion respects `prefers-reduced-motion`. Text and symbols carry match labels independently of color. Filtering is local to the bounded response and is labeled accordingly.

The design-system primitives are expanded as used: Button, status pill, confidence indicator, skeleton and empty state. A native modal dialog provides keyboard trapping and focus restoration for the command palette. The remaining PRD component inventory and full WCAG review remain tracked in BUILD_STATUS; this ADR does not waive them.

References: PRD §§11.2–11.8, 14, 33; https://reactflow.dev/api-reference/react-flow.
