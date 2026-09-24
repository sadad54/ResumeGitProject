# Build status

Honest state of ProofHire V1 as of 2026-09-20 (deployment section updated
same day after Vercel/Supabase went live). Supersedes the phase-7
continuation notes. Every "done" below names the artifact that proves it;
every gap says what would close it and why it is open.

The checklist this is measured against is
`ProofHire_Flagship_AI_FullStack_Checklist.md`; the item-by-item result is in
`CHECKLIST_STATUS.md` next to this file.

## Verified working

**Pipeline.** GitHub OAuth → repository sync (tree, P0/P1/P2 classification,
vendor/generated/secret exclusion, deterministic tech + ML-infrastructure
extraction, incremental re-sync with per-path change detection and stale
marking) → LLM evidence extraction over changed artifacts only → evidence
graph with provenance → JD requirement extraction → two-stage hybrid
retrieval (GIN + IVFFlat candidate generation, weighted fusion) → LLM rerank
→ Strong/Partial/Gap/Unknown coverage → positioning → resume / cover-letter
writer (conservative + full) → claim verification with the deterministic fact
guard authoritative for employer/date/degree/metric claims → bounded repair
→ HTML/PDF render (three templates, A4/Letter, deterministic page breaks) →
parse-back validation → overflow detection → export. Cooperative
cancellation between LLM calls.

**Security.** Bearer JWTs with per-token `jti`; logout revokes both tokens;
refresh rotation revokes the spent token; revocation fails closed. Account
deletion and GitHub disconnect. Fernet-encrypted OAuth tokens. Secret
scanning before persistence and before capture. Rate limiting on every
endpoint that spends money or third-party quota. CSP + security headers on
web and API. Prompt inputs from third parties fenced as data, with the
deterministic guards behind them tested against a model that complied with
an injection. Dependency, secret and container scanning in CI; both images
scan at zero CRITICAL/HIGH after moving to multi-stage builds that ship no
package manager. CSRF posture reviewed and recorded (ADR-0017).

**Frontend.** Next.js 16 / React 19 / TypeScript, TanStack Query, generated
typed API client from the OpenAPI document (CI fails on drift), dark/light,
command palette, responsive, reduced-motion, WCAG-targeted forms and
non-colour-only status. Evidence Constellation with JD overlay, viewport
virtualization (`onlyRenderVisibleElements`, confirmed by measurement),
accessible table equivalent, provenance rail, live export preview through
the real renderer, before/after diff viewer, overflow warning, optimistic
stage updates, content-shaped skeletons.

**Operations.** Health and readiness (Postgres + Redis) endpoints. Structured
JSON logs with trace ids. OpenTelemetry spans on every pipeline stage
(opt-in). Sentry error monitoring (opt-in) with a scrubber that strips locals,
bodies and credential headers. Dashboard-as-code with backing SQL executed
against the real schema. Environment separation, backup/restore and rollback
procedures documented; migrations verified additive-first.

**Measured.** Lighthouse 100/100/100/100 on five routes (jobs 98 perf),
475–574 KiB initial JS, 57–60 fps panning at 100–1,000 graph nodes, API p95
13–46 ms per request locally, retrieval query p50 5 ms at 20k rows after an
80× fix found by the benchmark. All in `docs/product/metrics/` with the
scripts that produced them.

**Tests.** 46 API, 124 worker, 18 root (phase 7) Python tests against real
Postgres and Redis; 9 extension tests driving the real service worker; 8
Playwright E2E + axe WCAG checks; PDF rendering regression through real
Chromium; graph FPS and JS payload measurements (desktop-only Playwright
project — the constellation renders the accessible table on mobile, so
there are no graph nodes to measure there); 6 visual regression comparisons
with both Windows and Linux baselines committed, so CI compares rather than
warns on either platform. CI: lint, typecheck, build, OpenAPI freshness,
generated-types freshness, all of the above, dependency/secret/container
scanning.

## Bugs found and fixed while verifying (not hidden)

- Worker registered every real actor on a phantom broker after an import
  reorder; jobs sat in Redis unconsumed while the process reported healthy.
  Regression test imports the module fresh and asserts broker registration.
- Worker tasks reused API connection-pool connections across event loops
  (`attached to a different loop`). Fixed with a NullPool engine; the API's
  own engine and Redis client made loop-aware for the same reason.
- Hybrid retrieval ordered the whole table by the fused score, so the
  GIN/IVFFlat indexes were never used (1.0× with vs without). Rewritten as
  two-stage candidate generation; 80× faster at 20k rows.
- IVFFlat index rebuild exceeds default `maintenance_work_mem` on a populated
  table; migration 0004 only ever indexed an empty one. Documented with the
  fix in `infra/deployment/OPERATIONS.md`.
- `X-Api-Key` slipped past the error-monitoring scrubber's substring match;
  caught by its test, matcher fixed rather than test weakened.
- Container images carried 13 CRITICAL/HIGH CVEs, all in base-image
  toolchains (pip's vendored msgpack, npm's bundled tar/pacote/sigstore),
  invisible to dependency scanning. Fixed by not shipping the toolchains.
- First Playwright measurement runs hit the dev server and reported 3.5 MB
  of JS; discarded and re-run against `next start`.
- Graph FPS spec timed out under the mobile Playwright project: the
  constellation deliberately renders the accessible table instead of the
  graph on mobile, so no graph nodes ever appear to measure. Scoped both
  measurement specs to desktop.

## Open, and why

**Requires infrastructure, spend or human labour the builder cannot supply**
(excluded by decision):

- **Production / staging / preview deployment.** Frontend and database are
  live on free tiers: Vercel (`https://proofhire-beta.vercel.app`, verified
  serving with the strict CSP and security headers) and Supabase Postgres
  (`proofhire`, ap-southeast-1, pgvector 0.8.2, migrations 0001–0008
  applied, $0/month confirmed through the cost API). The API/worker/Redis
  image (`infra/docker/Dockerfile.space`) builds and scans clean in CI and
  `infra/deployment/deploy_space.py` will create and populate the Hugging
  Face Space, but the one step the script cannot do — `hf auth login` with a
  human's token — has not happened in this environment, so the backend
  itself is not hosted and the frontend has no live API to call yet.
  `infra/deployment/README.md` has the exact remaining steps. The export
  store is still local disk (ephemeral on a free Space), so stateless
  replicas are not yet safe.
- **Object storage and signed URLs.** Exports are written to the local
  filesystem. Account deletion therefore does not purge rendered PDFs
  (ADR-0016 records this).
- **100+ labelled JD benchmark** and everything downstream of it: extraction
  F1, Recall@5, nDCG@5, Strong/Partial accuracy, unsupported-claim rate,
  contradiction rate, verifier catch rate, citation precision. One fixture JD
  exists. `packages/evals` computes every metric and refuses to fabricate a
  missing measurement; it has never been run on a real dataset.
- **Load testing** at 10/50/100/250 users, bottleneck identification under
  concurrency, queue throughput, failure rate under load. API latency is
  measured per-request only.
- **Real provider cost and token telemetry** (cost/repository,
  cost/application, tokens/run, cache savings, generation p95). The
  instrumentation exists end to end; the mock provider reports zero cost by
  construction, so no number is quoted.
- **Live extension walkthrough** in an installed Chrome. Service-worker tests
  cover the logic; the human right-click → PDF journey has not been done in
  this environment (Chrome blocks automation on `chrome://extensions`).

**Not done, could be:**

- Frontend component unit tests (vitest). Attempted; the workspace install
  did not land and it was dropped by decision. Playwright E2E, axe and visual
  regression are the frontend coverage.
- Full manual WCAG 2.2 AA walkthrough beyond the automated axe checks and the
  Evidence page's keyboard/focus tests. Lighthouse accessibility is 100 on
  every route, which is necessary but not the same thing.
- CSP `'unsafe-inline'` for scripts (Next.js bootstrap). Nonce support would
  remove it.
- Retuning IVFFlat `lists` / `probes` once real evidence volumes exist.
- Hard-delete path for a single evidence item (soft rejection is the
  default; ADR-0016 notes the one case where that is arguably wrong).

## Run it

1. `npm ci` at the root. Install Python packages together:
   `pip install -e packages/contracts -e packages/prompts -e packages/evals -e 'apps/api[dev]' -e 'apps/worker[dev]'`.
2. Postgres 16+ with pgvector and Redis (`infra/docker/docker-compose.yml`).
   Copy `.env.example` to `.env`; generate the two secrets as described in
   `infra/deployment/OPERATIONS.md`.
3. `alembic upgrade head` from `apps/api` (migrations 0001–0008).
4. API: `uvicorn proofhire_api.main:app` from `apps/api`. Worker:
   `python -m dramatiq proofhire_worker.tasks` from `apps/worker`. Web:
   `npm run dev --workspace apps/web`.
5. Tests: `python -m pytest -c pytest.ini tests/phase7 apps/api/tests apps/worker/tests`
   from the root with `DATABASE_URL`/`REDIS_URL` set;
   `node --test apps/extension/tests/*.test.mjs`;
   `npm exec --workspace apps/web -- playwright test` after `npm run build`.
6. Measurements: `apps/api/scripts/benchmark_queries.py`,
   `apps/web/tests/graph-performance.spec.ts`, `apps/web/tests/js-payload.spec.ts`,
   `npx lighthouse` against `next start`.
