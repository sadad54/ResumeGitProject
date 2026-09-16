# Continuation from phase 7

This increment starts from phase 6 commit `c38a9ce`, incorporates the subsequent CORS fix and regression test in `c64160c`, and follows the single-builder sequential plan. It is not a declaration that the full V1 is finished.

## Implemented

- **Phase 7:** tenant-scoped graph projection; project/skill/architecture/evidence nodes, source links and weighted edges; saved-job requirement overlays; preserved Strong/Partial/Gap/Unknown labels; accessible node/relationship table and coverage matrix; mobile table default; reduced-motion support; responsive shell; command palette with navigation, repository sync and theme toggle; incremental shared UI primitives.
- **Integration:** reopen captured jobs, poll extraction/coverage separately, suppress stale matches during reanalysis, remove obsolete matches on recomputation, reopen saved documents, select among three single-column resume export styles. Existing standard cover-letter rendering is retained.
- **Phase 8:** unpacked MV3 extension, selection context menu, page/popup paste fallback, expiring session handoff, existing web-session authentication, idempotent capture endpoint, migration 0007 for page title, saved-job deep link.
- **Phase 9 foundations:** offline scoring CLI with JSON output and strict missing-measurement gates; F1, retrieval metrics, unsupported-claim/fact/parse-back rates and cost/latency summaries; measured dual-provider budget proposal command; explicitly synthetic smoke fixture.
- **Phase 10 foundations:** bearer headers instead of URL tokens for SSE; run ownership checks; validation errors omit raw input; accessibility/keyboard/mobile/reduced-motion browser tests; CI definitions for Python/Postgres tests, frontend lint/type/build/browser checks, extension checks, dependency/secret checks and on-master Docker builds; API/web Dockerfiles and deployment notes.

## Verification performed locally

- 80 Python tests passed: new graph/capture/ownership/CORS tests, evaluation scoring tests and existing fact-guard, matching, secret-scanner and parse-back tests.
- Five extension service-worker/permission tests passed.
- Eight Playwright tests passed across desktop and mobile with fixture API responses, including keyboard focus, source inspection, error recovery, reduced motion and automated WCAG A/AA checks on the evidence table page. Screenshots were inspected; a mobile height bug and contrast issues were corrected.
- TypeScript, ESLint and the production Next.js build passed. Production npm audit reported zero known vulnerabilities at verification time.
- Three resume templates were rendered by Chromium and their sections, dates, employer and bullet claims were extracted and checked from real PDFs. This is a small regression fixture, not the full ≥99% corpus target.

Local relational tests used an ephemeral SQLite database with the production SQLAlchemy models. The host offers Python 3.12; CI is configured for the project's required Python 3.13 and PostgreSQL+pgvector. The full PostgreSQL migration/integration suite, Docker images and hosted CI must still pass. No live provider credentials or deployed staging environment were used. Browser tests use synthetic fixtures; they are not evidence of a complete real GitHub-to-PDF journey.

## Remaining acceptance gates (requirements retained)

### Phase 7/8 live acceptance

- Run graph overlay against the real fixture repository/JD in the user's configured environment, including sync → review → analyze → coverage → provenance.
- Confirm the exact §11.3 capture/condense/overlay/matrix choreography on real pipeline timing; the current transitions do not delay actions.
- Load the extension in Chrome and complete right-click capture → analysis → generate → verify → PDF. Service-worker tests do not substitute for installed-extension testing.
- Finish the full §33 design-system inventory as remaining screens need it. Review screens beyond Evidence still need the final accessibility/polish pass.
- Automatic page extraction is not implemented; no-selection capture uses paste fallback to preserve the exact minimal permission set.

### Phase 9

- Curate 100+ distinct real JDs across all seven role families, with genuine human-reviewed requirement/evidence labels and source attribution. No generated labels are represented as human-reviewed.
- Produce actual OpenAI and Anthropic pipeline runs with independent claim/fact grading and semantic requirement alignment. Publish the benchmark report only after measuring the retained quality targets.
- Populate accurate nonzero provider cost telemetry, derive and document a dollar spend cap, then implement/enable the full nightly dual-provider runner with pre-call reservations, retry accounting and cap enforcement. The budget command only proposes a cap; no nightly spending job is enabled.

### Phase 10 / release

- Full pipeline OpenTelemetry and operational dashboards, security audit logs, complete CSRF/CSP review, production configuration validation, container scanning and proof of no secrets in logs.
- Full WCAG 2.2 AA manual and automated review on primary pages, Lighthouse ≥90/95/95 budgets, committed visual regression baselines and CI comparison. Current screenshots are verification artifacts, not a visual-regression gate.
- Full real-service E2E journey, mobile/tablet coverage, deployment to staging/preview, demo recording and final portfolio report.
- The phase 6 exporter still uses its existing local filesystem storage. S3-compatible persistence/signed URLs and the before/after tailoring diff viewer remain inherited plan gaps; they are not silently treated as finished here.

## Run this increment

1. Update dependencies from the repository root with `npm ci`. Install all local Python packages together (`packages/contracts`, `packages/prompts`, `packages/evals`, `apps/api[dev]`, `apps/worker[dev]`) and `aiosqlite` for the local new tests.
2. With the existing database configuration, run `alembic upgrade head` from `apps/api` to apply migration 0007.
3. Start API, worker and web as usual. Open Evidence for the constellation, Jobs to reopen an analysis, and Documents for saved exports. `Cmd/Ctrl+K` opens the palette.
4. Follow `apps/extension/README.md` to load the extension. Production origins must be configured in both its manifest and config.
5. Run `python -m pytest -c pytest.ini ...` from the repo root (the root config supplies monorepo import paths), `node --test apps/extension/tests/*.test.mjs`, and `npm exec --workspace apps/web -- playwright test` after a production build. Install Chromium with Playwright first. A custom local browser executable can be supplied with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`.
