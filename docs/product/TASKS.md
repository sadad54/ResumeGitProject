# Deployment-readiness push — task tracker

Started 2026-09-27 on branch `claude/deployment-readiness` (local commits
only; the user pushes). Goal, in the user's order: backend fully functioning →
frontend and backend in sync → deployment ready, while strengthening the
project for both AI/ML-engineer and full-stack roles.

"Done" means the artifact named was run and its output read — not that code
exists. Anything cut goes in **Known gaps** with the reason.

## Findings that shaped this plan (audit, 2026-09-27)

| # | Finding | How it was found |
|---|---|---|
| F1 | CI red on master: `/api/v1/demo/session` added without regenerating `docs/api/openapi.json` / TS types | `gh run view 35962047935 --log-failed` |
| F2 | Live Vercel build points the browser at `http://localhost:8000` (CSP `connect-src`), no Vercel env vars | `curl -I https://proofhire-beta.vercel.app`, `vercel env ls` |
| F3 | Production Supabase DB paused (`INACTIVE`, free-tier 7-day idle pause) | Supabase MCP `get_project` |
| F4 | Deploy default model `llama-3.3-70b-versatile` no longer served by Groq → every LLM call would 404 | `GET https://api.groq.com/openai/v1/models` |
| F5 | Without an OpenAI key, embeddings silently fall back to SHA-256 bytes (no semantics) — the planned Groq deployment has no real vector retrieval | `provider_factory.get_embedding_provider`, `mock_provider.embed` |
| F6 | No production guard: API boots with the public default `AUTH_SECRET_KEY` (forgeable JWTs) | `config.py` defaults; no validation anywhere |
| F7 | Frontend never refreshes tokens and never handles 401 — UI breaks silently 30 min after login | grep: `refresh` unused, no `401` handling |
| F8 | No sign-out, account deletion, GitHub disconnect or demo entry in the UI although the API has them | route-vs-call diff of `openapi.json` and `apps/web/src` |
| F9 | TanStack Query listed as done in CHECKLIST_STATUS but has zero usages; typed client used by 2 of ~30 call sites | grep `useQuery` → 0 |
| F10 | PDFs served from absolute local paths; API responses leak server filesystem paths (`pdf_ref`); stale refs 500 after a restart wipes the Space disk | `routers/generation.py`, `render/storage.py` |
| F11 | `GET /documents` ordered by random UUID; `/documents/{id}/claims` issues 4 queries per claim | `routers/generation.py` |
| F12 | Home page still shows placeholder copy ("land here starting Phase 2+") | `app/page.tsx` |
| F13 | GitHub OAuth callback redirects to `/settings?github=connected`, but Settings has no GitHub panel | `routers/github.py:101` vs `app/settings/page.tsx` |
| F14 | C: drive at 0 bytes free mid-session (WSL disk + caches); cleared npm/pip caches with the user's OK (+5.7 GB) | `Get-PSDrive` |

## Phase A — green CI, contract sync
- [x] A1 Regenerate OpenAPI + TS types (F1) — `591de7a`
- [x] A2 Pytest guard for a stale `openapi.json` — `test_openapi_current.py`, verified failing on master's doc and passing after; it then caught my own B2 contract change before commit

## Phase B — backend fully functioning
- [x] B1 Production config validation (F6) — `dceaa88`, 16 tests; real `.env.production` validated as the deploy script assembles it: 0 errors
- [x] B2 Object storage (F10) — `9258292`: local + S3 (moto-tested), owner-scoped keys, signed URLs, 410 self-healing, purge-on-delete, no path leakage; ADR-0016 gap closed
- [ ] B3 Real embeddings without an API key: ONNX bge-small (384-d) default, OpenAI `dimensions=384` optional; migration to vector(384) + HNSW + per-row `embedding_model`; backfill command (F5)
- [ ] B4 Groq model defaults that exist; startup model-availability check (F4)
- [ ] B5 SSE: verify the late-subscriber race; if real, replay via Redis Streams
- [ ] B6 ~~documents ordering~~ ~~claims N+1~~ (done in `9258292`: migration 0010, one DISTINCT ON query); `is_demo` on `/auth/me`; overview stats endpoint (F11)
- [ ] B7 Real end-to-end run on Groq: sync a real repo → evidence → JD → coverage → generate → verify → export → download

## Phase C — frontend ↔ backend in sync
- [ ] C1 Session layer: single-flight refresh on 401, session-expired state, `/auth/me`, sign-out with server-side revocation (F7, F8)
- [ ] C2 TanStack Query + generated typed client for every call; delete hand-written response types (F9)
- [ ] C3 Real Overview page (signed-out landing + demo entry; signed-in stats), Settings (disconnect GitHub, delete account) (F8, F12)
- [ ] C4 Demo mode is visibly read-only; GitHub sync progress humanized; download via signed URL
- [ ] C5 Playwright E2E for the new flows against the real API

## Phase D — deployment ready
- [ ] D1 CI job boots the exact Space image against Postgres and smoke-tests the API
- [ ] D2 Deploy script: config validation, storage/embedding settings, Vercel env + redeploy step
- [ ] D3 Embedding model baked into the image (no cold-start download)
- [ ] D4 Opt-in keep-alive workflow (Space sleep + Supabase pause, F3)
- [ ] D5 Runbook: the few steps only the user can do, in order

## Phase E — AI evaluation with real labels
- [ ] E1 Retrieval component benchmark on public human-annotated data: lexical vs hash-fallback vs dense vs hybrid (Recall@5, MRR, nDCG@5)
- [ ] E2 JD requirement extraction vs human skill annotations (strict + relaxed P/R/F1) on 100+ postings via Groq
- [ ] E3 Verifier catch rate on injected hallucination traps; unsupported-claim rate; latency/tokens per run

## Phase F — load testing
- [ ] F1 10/50/100/250 concurrent users; p95, failure rate; bottleneck found, fixed, re-measured

## Phase G — consolidate
- [ ] G1 BUILD_STATUS + CHECKLIST_STATUS corrected (incl. the false TanStack claim)
- [ ] G2 README leads with what it is, live topology, measured results
- [ ] G3 Resume bullets (AI/ML + full-stack) with every number traceable to a committed results file

## Known gaps
(filled in as items are cut, with the reason)

## Handoff — 2026-09-27 (session paused at usage limit)

Committed and verified: A1, A2, B1, B2, B3 (local bge-small embeddings, 384-d + HNSW,
ef_search=100 + iterative scan after measuring recall@50 0.800 → 0.982 on real vectors),
B4 (per-provider model defaults + live `check_models`; all 7 Groq task models verified).

Uncommitted, written but NOT yet run/typechecked:
- F15 OAuth callback always redirects back (`routers/github.py`, `tests/test_github_callback.py`)
- F16 run-level `github.sync.completed/failed` events (contracts enums.py/.ts, `ingestion/sync.py`, `routers/events.py`)
- `GET /api/v1/me/overview` + `is_demo` on `/auth/me` (`routers/overview.py`, `schemas/overview.py`, `tests/test_overview.py`); regenerated openapi.json/TS types
- Frontend C1–C3 partly migrated: `lib/api.ts` (single-flight refresh on 401, parsed errors), `api-client.ts`,
  `session.tsx`, `queries.ts`, `providers.tsx`, layout, app-shell, `session-ui.tsx`, auth-panel, home, settings,
  github-panel, account-settings, resume-upload, evidence-explorer. STILL TO MIGRATE: job-workspace,
  resume-workspace, evidence-constellation, applications-board, command-palette, capture-handoff,
  document-preview, events.ts (→ authFetch). New CSS classes (ph-banner*, ph-hero, ph-stat*, ph-steps,
  ph-auth*, ph-user, ph-button-primary/danger, ph-danger, ph-settings, ph-progress, ph-repo-list, ph-facts, ph-ok)
  are referenced but not yet added to globals.css. Visual/Playwright mocks need /auth/me + /me/overview shapes.
- `Dockerfile.space` (bakes model) + `space-entrypoint.sh` (check_models, reembed) — needs CI Docker build
- `benchmark_queries.py` rewrite (`--embeddings real|random`, ANN sweep) — a run was in progress; old
  IVFFlat results renamed to `query-benchmark-ivfflat-1536d.*` (staged rename)
- `scripts/dev-backend.sh`, `.gitignore` (.dev/)
Next: finish C, then D (CI container smoke test, deploy script + Vercel env), E (SkillSpan/ESCO eval), F, G.
