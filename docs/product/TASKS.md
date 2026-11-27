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
- [x] B3 Real embeddings without an API key (F5) — `f859603`, `f3d3968`; ADR-0018
- [x] B4 Groq model defaults + `check_models --probe` (F4) — `f859603`, `1058b40` (verifier moved off qwen after Groq capped it at 1K output tokens/min mid-session; probe verified live against that config)
- [x] B5 SSE late-subscriber race: real; events moved to per-run Redis streams with replay from `events_after` / `Last-Event-ID` — `0768c07`, `test_run_events.py`
- [x] B6 Documents ordering, claims N+1 (`9258292`); `is_demo`, overview endpoint (`2aefb77`) (F11)
- [x] B7 Real end-to-end run on Groq — `scripts/e2e_live.py`, `docs/product/metrics/e2e-live.json`. First attempt found 8 bugs (`1058b40`); second found 0 resume bullets without an uploaded resume (Projects section, `resume_write:v2`) and an export failure on U+2011 hyphens (parse-back normalization + ATS-safe text)

## Phase C — frontend ↔ backend in sync
- [x] C1 Session layer (F7, F8) — `ce441c5`
- [x] C2 TanStack Query + generated typed client everywhere (F9) — `ce441c5`
- [x] C3 Landing, overview, settings (F8, F12) — `ce441c5`
- [x] C4 Demo read-only, humanized sync progress, signed-URL download — `ce441c5`; repository statuses poll until evidence is ready — `1058b40`
- [ ] C5 Playwright E2E for the new flows against the real API

## Phase D — deployment ready
- [x] D1 CI `space-image` job + `infra/docker/smoke_space.py` — `1058b40` (API checks 8/8 against the local stack; in-container snippets verified outside Docker; the job itself first runs on push)
- [x] D2 `deploy_space.py`: preflight (config + live model probe), `--dry-run`, stale-variable cleanup, `--vercel` — `1058b40`; dry run passes with `--provider groq`
- [x] D3 Model baked into the image, build fails if it stops producing 384-d vectors; smoke test loads it offline
- [x] D4 `.github/workflows/keepalive.yml`, opt-in via `vars.PROOFHIRE_API_URL`
- [x] D5 `infra/deployment/README.md` rewritten as the runbook

## Phase E — AI evaluation with real labels
- [x] E1 `apps/worker/scripts/eval_skill_retrieval.py` on 926 human-labelled job-ad sentences (TechWolf/SkillSpan, ESCO): found the AND lexical query dead (908/926 no results); OR semantics shipped (ΔMRR +0.022 [+0.007, +0.037]); RRF rejected (−0.061); ADR-0006 updated
- [ ] E2 JD requirement extraction vs human skill annotations (strict + relaxed P/R/F1) on 100+ postings via Groq
- [~] E3 Verifier catch rate on planted traps — v1 measured (`verifier-eval-v1.json`, 160 bullets, Groq gpt-oss-120b): trap catch 33.8% [24.3, 44.6], false positives 23.7% [15.8, 34.1]; technology traps 0/20, scope traps 1/20, and 19/20 *true* employment claims wrongly flagged. `cdeb354` adds the technology exact-match guard and `claim_verify:v2`. **Still to do:** re-run `eval_verifier.py` on v2, fix the employment false positives, commit `verifier-eval-v2.json`

## Phase F — load testing
- [~] F1 `apps/api/scripts/load_test.py` written (`233846d`), query benchmark refreshed. **Not run yet** — no results file. Needs the local Postgres + Redis stack, which is gone from this machine (WSL distro and Docker both absent as of 2026-11-28)

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
