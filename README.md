# ProofHire

**Evidence-grounded AI career agent for software engineers.**

ProofHire converts authorized GitHub repositories into a provenance-aware developer
Evidence Graph, maps job requirements to defensible code-derived evidence using hybrid
retrieval and reranking, and generates verified application materials with claim-level
citations and hallucination guards. Unsupported claims are blocked from export.

> Status: phase 7/8 implementation plus evaluation and hardening foundations. See
> [`docs/product/BUILD_STATUS.md`](docs/product/BUILD_STATUS.md) for verified behavior and remaining release gates. See [`docs/product/PRD.md`](docs/product/PRD.md) for the full
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

**With Docker** (what `infra/docker/docker-compose.yml` assumes):

```bash
cp .env.example .env   # fill in secrets before running anything that touches them
docker compose -f infra/docker/docker-compose.yml up -d
```

**Without Docker** (verified working setup, e.g. on a machine without Docker Desktop):
run Postgres+pgvector and Redis inside WSL2 instead — they're both native Linux
services, so this works as well as the container images do.

```bash
# One-time setup, inside WSL (Ubuntu):
sudo apt-get install -y postgresql postgresql-18-pgvector redis-server
# If port 5432 is already taken by a native Windows Postgres install, change WSL's
# Postgres to listen on 5433 instead (edit /etc/postgresql/18/main/postgresql.conf:
# port = 5433, listen_addresses = '*') and add a scram-sha-256 host rule to
# pg_hba.conf for 0.0.0.0/0 so the Windows-side API process can reach it.
sudo -u postgres psql -c "CREATE USER proofhire WITH PASSWORD 'proofhire' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE proofhire OWNER proofhire;"
sudo -u postgres psql -d proofhire -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo service postgresql start
redis-server --daemonize yes --bind 0.0.0.0 --protected-mode no
```

WSL2 forwards ports its services listen on to `localhost` on the Windows side
automatically, so `DATABASE_URL`/`REDIS_URL` in `.env` can point at
`localhost:5433`/`localhost:6379` (adjust the Postgres port to match whatever you
configured) whether the API/worker processes run on Windows or inside WSL.

**Running the API** (Python 3.13+ required — WSL's Ubuntu ships a new enough
Python; Windows may not):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/contracts -e 'apps/api[dev]' -e 'apps/worker[dev]'
cd apps/api && alembic upgrade head
uvicorn proofhire_api.main:app --reload
```

Verify with `curl localhost:8000/health` and `curl localhost:8000/ready`.

**Running the web app:**

```bash
cd apps/web
cp .env.example .env.local
npm install && npm run dev
```

**GitHub OAuth** requires registering an OAuth App (github.com → Settings →
Developer settings → OAuth Apps) with callback URL
`http://localhost:8000/api/v1/github/callback`, then setting
`GITHUB_OAUTH_CLIENT_ID`/`GITHUB_OAUTH_CLIENT_SECRET` in `.env`. Everything else
(auth, health checks, repository listing once connected) works without it.

## Build plan

This project is being built in dependency-ordered phases (data plane → evidence →
job understanding → matching → generation/safety → rendering → graph UI → extension →
eval → hardening). Every phase ends in a runnable, demoable state against a fixture
GitHub repository and a set of fixture job descriptions before scope broadens.

## License

TBD.

