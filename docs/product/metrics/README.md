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
