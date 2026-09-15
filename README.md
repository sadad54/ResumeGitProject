# ProofHire

**Evidence-grounded AI career agent for software engineers.**

ProofHire converts authorized GitHub repositories into a provenance-aware developer
Evidence Graph, maps job requirements to defensible code-derived evidence using hybrid
retrieval and reranking, and generates verified application materials with claim-level
citations and hallucination guards. Unsupported claims are blocked from export.

> Status: early build. See [`docs/product/PRD.md`](docs/product/PRD.md) for the full
> product spec and [`docs/adr/`](docs/adr/) for architectural decisions.

## Why this exists

Resume tailoring tools generally start from a resume. A one-page resume captures only a
sliver of a developer's real technical history, and generated claims are rarely traceable
to concrete source material. ProofHire instead builds a persistent, source-cited Evidence
Graph from a candidate's actual code, then generates resumes where every material claim
carries provenance back to a specific file, commit, or confirmed profile fact.

## Architecture

Modular monolith + async workers, not microservices (see
[ADR-0001](docs/adr/0001-architecture.md)).

```text
apps/
├── web/          # Next.js web app
├── api/           # FastAPI API
├── worker/         # async ingestion / AI workers
└── extension/       # Manifest V3 browser extension
packages/
├── contracts/       # shared enums, generated OpenAPI TS client
├── design-system/     # shared UI tokens/components
├── prompts/         # versioned prompt definitions
├── evals/           # eval datasets + harness
└── config/
infra/
├── docker/          # local Postgres+pgvector, Redis
├── migrations/
└── deployment/
docs/
├── adr/            # architectural decision records
├── api/
└── product/          # PRD
tests/
├── fixtures/         # fixture repo + JDs used for end-to-end demos
├── integration/
├── evals/
└── e2e/
```

**Stack:** Next.js 16 / React 19 / TypeScript / Tailwind / shadcn / Framer Motion / TanStack
Query (web) · Python 3.13 / FastAPI / Pydantic v2 / SQLAlchemy 2 (API) · Dramatiq + Redis
(workers) · PostgreSQL + pgvector · S3-compatible object storage · provider-independent LLM
interface (OpenAI + Anthropic) · SSE for streaming · Playwright/Chromium for PDF rendering.

## Local development

```bash
cp .env.example .env   # fill in secrets before running anything that touches them
docker compose -f infra/docker/docker-compose.yml up -d
```

API and web app setup instructions land as each is scaffolded — see the build plan below.

## Build plan

This project is being built in dependency-ordered phases (data plane → evidence →
job understanding → matching → generation/safety → rendering → graph UI → extension →
eval → hardening). Every phase ends in a runnable, demoable state against a fixture
GitHub repository and a set of fixture job descriptions before scope broadens.

## License

TBD.
