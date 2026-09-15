# docs/api

The authoritative API contract is the FastAPI-generated OpenAPI schema
(`apps/api` at runtime, `/openapi.json`), not hand-written docs. Snapshot it here
once the first real endpoints land in Phase 1, and regenerate `packages/contracts`'
TypeScript client from it rather than hand-duplicating types (PRD §24, ADR-0010).
