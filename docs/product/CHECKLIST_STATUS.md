# Checklist cross-check

Item-by-item against `ProofHire_Flagship_AI_FullStack_Checklist.md`, as of
2026-09-20. **Done** means a committed artifact was run and verified, not that
code exists. **Partial** says what's missing. **Open** says why.

Excluded by decision (need hosting, spend, or human labelling the builder can't
supply): backend (API/worker) hosting — frontend and database are live, see
below — the 100+ labelled JD benchmark, object storage, load testing.

## Track A — AI Engineering

### 1. Repository Intelligence — 9/9

| Item | Status | Evidence |
|---|---|---|
| GitHub OAuth works with real repositories | Done | `routers/github.py`; real sync of `sadad54/agentic-planner` observed this session (120 source artifacts) |
| Repository tree analyzed automatically | Done | `ingestion/sync.py` |
| Relevant files selected, not everything embedded | Done | `ingestion/classifier.py` P0/P1/P2; P2 capped at 60 |
| Manifests, Docker, CI/CD, K8s/IaC, tests analyzed | Done | `classifier.py` types; `tech_extraction.py` |
| ML/model infrastructure detected | Done | `tech_extraction.py` `ML_DEPENDENCY_SIGNALS` / `ML_FILE_SIGNALS` / GPU base images; `test_ml_infrastructure_detection.py` (7) |
| README/documentation evidence extracted | Done | README classified P0; extraction prompt |
| Generated/vendor/irrelevant excluded | Done | `VENDOR_DIR_PATTERNS`, `BINARY_EXTENSIONS` |
| Secrets and credential files excluded | Done | `secret_scanner.py` + `is_secret_like_path`; capture endpoint also scans |
| Repository changes trigger incremental reprocessing | Done | per-path change detection → only changed artifacts extracted; `test_incremental_resync.py` (6) |

### 2. Developer Evidence Graph — 9/9

All entities, provenance (`EvidenceSource` with commit SHA + content hash),
confidence, candidate/confirmed/rejected/private/stale lifecycle, many sources
per evidence, evidence across many requirements (`EvidenceMatch`), claims →
evidence (`ClaimEvidence`), and stale-on-change (`ingestion/staleness.py`).

### 3. JD Intelligence — 10/10

`jd_extract_v1` prompt + `JDAnalysisOutput` schema: role/company/seniority,
required vs preferred, importance, normalization, duplicate merging, original
text preserved on `Job.source_text`, marketing-copy rule in the prompt,
category allowlist enforced in code after the model.

### 4. Retrieval + Reranking — 7/10

| Item | Status |
|---|---|
| Lexical, vector, skill/entity matching, metadata filtering, candidate fusion, semantic reranking, Strong/Partial/Gap | Done — two-stage `hybrid_search` (rewritten this session after the benchmark found the indexes unused; 80× faster), `rerank_v1`, `match_label.py`; 12 retrieval tests against real Postgres |
| Human-labelled retrieval benchmark, Recall@K measured, MRR/nDCG measured | **Open** — needs the labelled dataset. `packages/evals/retrieval_metrics.py` computes them; never run on real labels |

### 5. Grounded Generation — 11/11

Positioning planner, evidence selector (matches → evidence set), resume and
cover-letter writers, structured outputs, conservative + full modes,
immutable profile facts, metrics require evidence (fact guard), skills only
from evidence (writer prompt rule + verifier), prompt versioning, generation
metadata persisted (`generation_runs`).

### 6. Claim-Level Verification — 10/10

`claim_verify_v1`, `fact_guard.py` (deterministic numeric / employer / date /
title), `claim_finalizer.py` (guard authoritative), contradiction status,
`MAX_REPAIR_ATTEMPTS = 2`, unresolved claims removed. Adversarial tests
including a verifier LLM that was talked into "supported" being overridden.

### 7. Multi-Model Architecture — 11/11

Provider abstraction, OpenAI + Anthropic adapters, mock provider, **models
configurable per task** (`model_selection.py`, `LLM_MODEL_<TASK>`),
structured-output validation with schema repair, **retry and rate-limit
handling** (`retry.py`, exponential backoff + jitter, honours Retry-After),
token/latency/cost accounting per call, no vendor SDK outside `providers/`.

### 8. Evaluation Framework — 2/16

| Item | Status |
|---|---|
| CLI computing F1, Recall@K, MRR, nDCG, unsupported-claim rate, contradiction rate, latency, tokens, cost — with strict gates that refuse to fabricate a missing measurement | Done — `packages/evals/cli.py`; smoke run in CI on a synthetic fixture *labelled as synthetic* |
| Strong/Partial classification accuracy, citation precision | Computed by the CLI when input exists |
| 100+ JDs across role families, manually labelled requirements and matches, hallucination traps, **any real measured number** | **Open** — 1 fixture JD. This is the checklist's own "non-negotiable" AI gate and it is not met |

## Track B — Full-Stack / SWE

### 9. Production Frontend — 13/13

Next.js/React/TS; server/client boundaries (hydration bug class found and
fixed); TanStack Query; **generated typed API client** (`api-client.ts` from
`docs/api/openapi.json`, CI drift checks); responsive; dark/light with
persistence; loading/error/empty states and skeletons; **optimistic UI** on
application stage changes; URL-addressable jobs; keyboard nav + command
palette; accessible forms; WCAG AA workflows (axe in Playwright, Lighthouse
a11y 100 on every route); reduced-motion.

### 10. Signature Frontend — 13/13

Constellation, zoom/pan/search, JD overlay, animated matching, graph →
coverage transition, provenance rail, **live preview** (real renderer via
`/documents/{id}/preview`, sandboxed iframe), **diff viewer**
(`document-diff.tsx`, LCS), interactive matrix, SSE status, skeletons +
microinteractions, **virtualized rendering** (`onlyRenderVisibleElements`,
proven: 39 DOM nodes at 1,000 graph nodes), accessible non-graph equivalent.

### 11. Backend Engineering — 14/15

Everything except **object storage** (local disk; excluded). Adds this
session: systematic pagination, rate limiting, embedding cache, `/ready`
checking both dependencies, generated TS client.

### 12. Asynchronous Architecture — 9/9

Dramatiq + Redis, durable, retries with exponential backoff (Retries
middleware), idempotent sync and capture, SSE status events, failure recovery
(status transitions + retry from failed/cancelled), **cancellation**
(cooperative flag, tested), concurrency control (per-queue processes,
per-user rate limits), separate ingest / ai / render queues.

### 13. Database Engineering — 11/11

Normalized model, migrations 0001–0008 with FKs and unique constraints,
GIN + IVFFlat + btree indexes, graph edges, cascade strategy, **deletion
policy** (ADR-0016), timestamps, content hashes, concurrency handling
(unique constraints + idempotent upserts), **EXPLAIN ANALYZE** and
**before/after index benchmark** (`docs/product/metrics/`; found and fixed
a real 1.0× → 35× index-effect gap).

### 14. Authentication + Authorization — 9/9

Real auth, GitHub OAuth, protected endpoints, per-user ownership on every
query, private-repo authorization via the user's own token, secure sessions
(bearer, short-lived access), **token rotation/revocation** (`jti` +
Redis denylist, refresh rotation revokes the spent token), encrypted GitHub
credentials, **logout / account deletion / GitHub disconnect** — all four
added this session with end-to-end tests.

### 15. Browser Extension — 9/9

MV3, context menu, selection extraction, active-page metadata, session
handoff, exact-origin messaging, minimal permissions, failure/loading/
success states, Open Analysis deep link. 9 service-worker tests. *Live
installed-Chrome walkthrough not performed here* (see BUILD_STATUS).

### 16. Document Engineering — 10/10

Structured content, HTML + PDF, three templates, **A4 + Letter**,
**deterministic page breaking**, selectable text (parse-back proves it),
plain-text export, parse-back, **overflow detection**, **rendering
regression tests** through real Chromium (10).

### 17. Security — 10/11

Secret scanning, `.env`/keys excluded, tokens encrypted, bounded snippets to
LLMs, no raw code in logs (error-monitoring scrubber tested), **CSP** +
headers, **CSRF reviewed** (ADR-0017: inapplicable by construction, stated),
input validation + **rate limiting**, secure extension messaging,
**dependency + container scanning** (0 findings), **prompt-injection tests**
(13). Open: signed object-storage URLs (excluded).

### 18. Testing — 13/14

Backend unit, DB integration, API contract (via generated OpenAPI + real
routes), worker, retrieval/eval, extension, accessibility (axe), **visual
regression** (Windows and Linux baselines both committed; CI compares on
both), Playwright E2E, **PDF regression**, mocked-LLM, adversarial, CI
reports. Open: **frontend component tests** (dropped by decision).

## Track C — Production / Systems — 9/12 + load 0/8

Done: Dockerized (multi-stage, scanned), GitHub Actions, automated migrations
in CI, health/readiness, OpenTelemetry (opt-in, every stage), structured logs,
error monitoring (opt-in), API → worker → LLM tracing (span per stage + shared
trace id), dashboards as code, rollback/backup strategy, environment
separation, **frontend + database deployed live on free tiers** (Vercel,
Supabase). Open: **backend hosting** — the Hugging Face Space image and
deploy script are ready and CI-scanned, but the one step they can't perform,
a human's `hf auth login`, hasn't happened in this environment, so nothing
serves the API yet. Load testing: all eight items open (excluded).

## Track D — Metrics

| | Status |
|---|---|
| AI: JDs evaluated, labelled requirements, F1, Recall@5, nDCG@5, unsupported-claim rate, verifier catch rate | **Open** — needs the benchmark |
| Systems: repos/files processed | 1 repo / 120 files (dev DB) |
| Systems: evidence nodes generated | **0** on this DB (extraction never completed before the worker fix; not re-run) |
| Systems: incremental-sync reduction | Instrumented; no re-sync has run |
| Systems: API p95 | Measured per-request: 13–46 ms |
| Systems: generation p95, concurrent users, failure rate, queue throughput | Open (provider spend / load test) |
| Cost: tokens and cost per repo/application, cache savings | Instrumented end to end; **not quoted** (mock provider = 0 by construction) |
| Frontend: Lighthouse, initial JS, graph FPS, LCP, CLS | Measured, committed |
| Frontend: INP | Field metric; TBT (lab) recorded instead |

## Final gates

**AI Engineering flagship:** real ingestion, persistent graph, hybrid
retrieval + reranking, claim-level provenance, independent verification,
hallucination guard — all done and tested. Quantitative dataset, measured
retrieval, measured grounding, production deployment — **open**.

**Full-Stack flagship:** every item done except full production deployment
(frontend and database are live; backend hosting needs a human's Hugging
Face login), object storage, and measured load. Observability, security
controls, CI/CD, substantial automated tests, generated client, extension,
SSE — done.

**End-to-end flow:** every stage exists and is tested in isolation and in
integration against real Postgres/Redis/Chromium. The single continuous run
from a real GitHub OAuth through the installed extension to an exported PDF
on live provider calls has **not** been performed in this environment.
