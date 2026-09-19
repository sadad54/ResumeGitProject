# Retrieval query: bottleneck found, fixed, re-measured

Checklist 13.10 (EXPLAIN ANALYZE), 13.11 (benchmark before/after indexing),
and the "identify bottleneck -> optimize -> rerun -> document improvement" loop.
All numbers are from `apps/api/scripts/benchmark_queries.py` on a **synthetic
20,000-row evidence corpus** (1536-dim random unit embeddings, technical
vocabulary), PostgreSQL 18.6 on WSL2, single user. This measures query plans
and index effect at scale, not retrieval quality, which needs the labelled
benchmark that is out of scope.

Raw data: `query-benchmark-before-rewrite.json` (original query) and
`query-benchmark.json` (after), each with full `EXPLAIN (ANALYZE, BUFFERS)` plans.

## What the first run found

The original `hybrid_search` ordered the whole table by the fused score
expression. Result: **1.0x speedup with the ADR-0006 indexes vs. without**:
they were never used. The plan showed why: an Index Scan on `user_id` reading
all 20,000 rows, `ts_rank_cd` and the vector distance computed for every one,
then a top-N heapsort. Postgres cannot push `0.35*ts_rank_cd(...) + 0.45*(1 -
(embedding <=> v))` into a GIN or IVFFlat index. Migration 0004's retrieval
indexes were dead weight.

A second finding from the same run: rebuilding the IVFFlat index over 1536-dim
vectors exceeds the 64 MB default `maintenance_work_mem` even at 2,000 rows
(`memory required is 65 MB`). Migration 0004 never hit this because it
indexed an empty table; a production rebuild or reindex would. Recorded in
`infra/deployment/OPERATIONS.md`.

## The fix

Two-stage retrieval, which is what ADR-0006 described and the code had not
actually implemented: each signal generates its own top-50 candidates in a
form its index can serve (`search_vector @@ tsquery` for GIN; a bare `ORDER BY
embedding <=> v LIMIT 50` for IVFFlat; the skill join), the candidate ids are
UNIONed, and fusion scores only that union. All 12 existing retrieval tests
pass unchanged.

## Measured result (p50, with indexes)

| Query | Before rewrite | After rewrite | Improvement | Index effect after (without -> with) |
|---|---|---|---|---|
| lexical+skills | 183.3 ms | 2.84 ms | 65x | 5.1x |
| lexical only | 95.19 ms | 15.22 ms | 6x | 1.1x |
| vector+lexical | 399.34 ms | 5.01 ms | 80x | 35.3x |

The `lexical only` index effect is small on *this* corpus: a 40-word
vocabulary means a three-term AND query matches a large fraction of rows, so
the GIN scan is not much cheaper than a sequential one. Real evidence text has
a far larger vocabulary and sparser matches; the 6x overall gain there comes
from scoring 50 candidates instead of 20,000.

IVFFlat is built with `lists = 100`; pgvector's guidance is `rows / 1000`
lists, so at 20k rows this is over-partitioned and probes only 1 list by
default. That favours latency and costs recall on random vectors. Retuning
`lists` and `ivfflat.probes` is a quality question for the labelled benchmark.

---

# Track D: measured metrics

Every number below is read from a committed JSON file in this directory, produced by a script or test in the repo. Machine: Windows 11 / WSL2, single dev laptop; not a production environment.

## Frontend (`lighthouse.json`, `js-payload.json`, `graph-fps.json`)

Lighthouse 13, desktop preset, production build via `next start`. INP is a field metric and cannot come from a lab run; TBT is the lab proxy.

| Route | Perf | A11y | Best practices | SEO | LCP | TBT | CLS | Initial JS (uncompressed) |
|---|---|---|---|---|---|---|---|---|
| `/applications` | 100 | 100 | 100 | 100 | 492 ms | 0 ms | 0 | 564 KiB / 11 scripts |
| `/documents` | 100 | 100 | 100 | 100 | 411 ms | 7 ms | 0 | 564 KiB / 11 scripts |
| `/evidence` | 100 | 100 | 100 | 100 | 518 ms | 0 ms | 0.025 | 475 KiB / 7 scripts |
| `/` | 100 | 100 | 100 | 100 | 518 ms | 0 ms | 0 | 564 KiB / 11 scripts |
| `/jobs` | 98 | 100 | 100 | 100 | 756 ms | 115 ms | 0 | 574 KiB / 12 scripts |
| `/settings` | 100 | 100 | 100 | 100 | 407 ms | 0 ms | 0 | 564 KiB / 11 scripts |

PRD targets (Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 95) are met on every route.

Graph FPS: synthetic graph through the real React Flow canvas, rAF frames counted during ~2 s of scripted wheel panning (`tests/graph-performance.spec.ts`). `rendered` is the number of node elements in the DOM, which stays ~39 at every size because the canvas uses React Flow's `onlyRenderVisibleElements` viewport virtualization — that is the checklist's "virtualized rendering" item, confirmed by measurement rather than by reading the prop.

| Graph nodes | Edges | DOM nodes rendered | Time to first node | Pan FPS |
|---|---|---|---|---|
| 100 | 197 | 39 | 810 ms | 60 |
| 500 | 997 | 39 | 941 ms | 60 |
| 1,000 | 1,997 | 39 | 1415 ms | 57 |

## Systems (`api-latency.json`, `query-benchmark.json`)

API latency: 200 sequential requests per route from one warm client to the local uvicorn (1 worker). This is per-request cost, **not** a concurrency test — load testing at 10/50/100/250 users is out of scope and unmeasured. Authenticated routes include the Redis revocation lookup.

| Route | p50 | p95 | p99 |
|---|---|---|---|
| `/ready` | 5.56 ms | 12.97 ms | 15.56 ms |
| `/api/v1/auth/me` | 7.34 ms | 17.02 ms | 19.33 ms |
| `/api/v1/jobs` | 8.44 ms | 19.06 ms | 23.54 ms |
| `/api/v1/documents` | 8.2 ms | 17.11 ms | 19.71 ms |
| `/api/v1/evidence` | 11.13 ms | 46.2 ms | 120.64 ms |
| `/api/v1/evidence/graph` | 10.91 ms | 23.64 ms | 33.74 ms |

Retrieval query at 20k evidence rows: see the top of this file (p50 5 ms vector+lexical after the rewrite).

Repositories / source files processed (dev database, real GitHub sync of one repository): 1 repository, 120 source artifacts. Evidence nodes generated: **0** — extraction never completed on this database before the worker bug fixed earlier in this session, and has not been re-run against a paid provider since. Incremental-sync reduction: instrumented (`extraction_skipped_no_changes`, see `infra/observability`) but no re-sync has run to produce a number.

## Not measured, and why

- **Generation p95, tokens/application, cost/application, cost/repository, cache savings**: require real provider runs. The instrumentation exists (`generation_runs` columns, `llm_call_completed` events, `infra/observability/queries.sql`) and the mock provider reports zero cost by construction, so quoting it would be fabrication.
- **Concurrent users, failure rate under load, queue throughput**: load testing is out of scope by the user's decision.
- **All AI-quality metrics** (extraction F1, Recall@5, nDCG@5, unsupported-claim rate, verifier catch rate): require the labelled JD benchmark, out of scope. `packages/evals` can compute them once a dataset exists.
