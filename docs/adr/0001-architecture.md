# ADR-0001: Modular monolith + async workers, not microservices

## Status
Accepted

## Context
ProofHire's V1 scope spans GitHub ingestion, LLM-based evidence/JD extraction, hybrid
retrieval/reranking, claim verification, PDF rendering, and a web app + browser
extension. It is being built by a single sequential builder (see
`docs/product/PRD.md` §12.1, §34 note on execution model). Microservices add
deployment, versioning, and cross-service contract overhead that is not justified at
this stage of scale or team size.

## Decision
Build as a modular monorepo:
- `apps/api` — one FastAPI application, internally organized into routers/services/
  repositories with clear module boundaries (see `packages/contracts` for the enums
  and schemas those boundaries share).
- `apps/worker` — a separate async worker process (Dramatiq + Redis) for
  ingestion/AI/render tasks, so long-running or bursty work never blocks API request
  latency, without needing a distinct service per task type.
- Strong internal module boundaries (`repositories/` as Protocol interfaces,
  `intelligence/` isolated from persistence) so any component can later be extracted
  into its own service if measured scale requires it (PRD §12.1, §28 "Scale path").

## Consequences
- Single deployable API + single deployable worker (scalable via replica count and
  per-queue worker pools) rather than N independently deployed services.
- Cross-cutting changes (e.g. adding a field to `Evidence`) touch one codebase, not a
  coordinated multi-repo/multi-service rollout.
- Extraction to a separate service is deferred until a concrete, measured need
  (see ADR-0012).
