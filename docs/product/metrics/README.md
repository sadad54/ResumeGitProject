# Retrieval index: 384-d embeddings, HNSW, and how far ANN drifts from exact

Current state (2026-09-27, ADR-0018). `query-benchmark.json` / `.md` come from
`apps/api/scripts/benchmark_queries.py --embeddings real`: 20,000 synthetic
evidence rows embedded with the production model (bge-small-en-v1.5, 384-d),
HNSW index, `hnsw.ef_search = 100` + iterative scan as `hybrid_search` sets
them. `query-benchmark-random-vectors.*` is the same run with random unit
vectors, the unstructured worst case for any approximate index.

| Query (real embeddings) | With indexes p50 | Without p50 | Speedup | Hybrid top-10 vs exact |
|---|---|---|---|---|
| lexical+skills | 5.08 ms | 14.61 ms | 2.9× | n/a (no matches) |
| lexical only | 14.25 ms | 17.16 ms | 1.2× | 1.0 |
| vector+lexical | 11.5 ms | 89.64 ms | 7.8× | **1.0** |

Vector branch alone, HNSW vs exact scan (20 queries, top-50):

| hnsw.ef_search | iterative scan | Recall@50 | Rows returned (of 50) | p50 |
|---|---|---|---|---|
| 40 (pgvector default) | off | 0.800 | **40** | 3.19 ms |
| 100 (production) | relaxed_order | **0.967** | 50 | 4.78 ms |
| 200 | relaxed_order | 0.994 | 50 | 6.51 ms |

**What this found.** pgvector's `hnsw.ef_search` (default 40) is also the most
rows one index scan returns. `hybrid_search` asks each signal for 50
candidates, so the vector branch had been silently truncated to 40, and every
missing row was a recall loss (0.800). At 100 with iterative scan it returns
all 50 at 0.967 recall for ~1.6 ms more; iterative scan also keeps one user's
rows from being starved by other users' nearer vectors under the per-user
filter. On random vectors recall is 0.2–0.56 at any setting: no neighbourhood
structure to exploit, which is why the random run is a stress test rather
than the headline.

**Not comparable with the IVFFlat numbers below.** Those used 1536-d random
vectors and IVFFlat probing 1 of 100 lists; its 5.01 ms vector+lexical p50 was
fast partly because it looked at 1% of the data, and nobody measured its
recall. The exact scan here is also cheaper (384-d), so the speedup ratio is
smaller while recall is known.

The exploratory probe that led to this (scratch, not committed) measured 0.982
at the production setting on a different 20-query sample; the committed file
above is the number to quote.

---

# Retrieval query: bottleneck found, fixed, re-measured (IVFFlat, 1536-d)

Checklist 13.10 (EXPLAIN ANALYZE), 13.11 (benchmark before/after indexing),
and the "identify bottleneck -> optimize -> rerun -> document improvement" loop.
All numbers are from `apps/api/scripts/benchmark_queries.py` on a **synthetic
20,000-row evidence corpus** (1536-dim random unit embeddings, technical
vocabulary), PostgreSQL 18.6 on WSL2, single user. This measures query plans
and index effect at scale, not retrieval quality, which needs the labelled
benchmark that is out of scope.

Raw data: `query-benchmark-before-rewrite.json` (original query) and
`query-benchmark-ivfflat-1536d.json` (after), each with full `EXPLAIN (ANALYZE, BUFFERS)` plans.

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

**Initial JS after the TanStack Query / session migration (2026-09-27)**
(`js-payload.json`, re-measured by `tests/js-payload.spec.ts`): 626 KiB on
most routes (was 564), 630 on `/jobs`, 660 on `/settings`, and `/evidence`
626 (was 475 — it now loads the same shared chunks as every other page).
The +62 KiB uncompressed is TanStack Query and the session / typed-client
layer, both shared chunks: the price of a real client cache, one-flight
session renewal and compile-time API contracts on every call. The Lighthouse
table above predates this change and is re-measured in the final pass.

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

Retrieval query at 20k evidence rows: see the top of this file (vector+lexical p50 11.5 ms with real 384-d embeddings and HNSW; hybrid top-10 identical to the exact scan).

Repositories / source files processed (dev database, real GitHub sync of one repository): 1 repository, 120 source artifacts. Evidence nodes generated: **0** — extraction never completed on this database before the worker bug fixed earlier in this session, and has not been re-run against a paid provider since. Incremental-sync reduction: instrumented (`extraction_skipped_no_changes`, see `infra/observability`) but no re-sync has run to produce a number.

## Not measured, and why

- **Generation p95, tokens/application, cost/application, cost/repository, cache savings**: require real provider runs. The instrumentation exists (`generation_runs` columns, `llm_call_completed` events, `infra/observability/queries.sql`) and the mock provider reports zero cost by construction, so quoting it would be fabrication.
- **Concurrent users, failure rate under load, queue throughput**: load testing is out of scope by the user's decision.
- **All AI-quality metrics** (extraction F1, Recall@5, nDCG@5, unsupported-claim rate, verifier catch rate): require the labelled JD benchmark, out of scope. `packages/evals` can compute them once a dataset exists.
