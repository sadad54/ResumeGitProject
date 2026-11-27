# ADR-0018: Local ONNX embeddings, per-row model identity, HNSW

## Status
Accepted (2026-09-27). Supersedes the embedding and index choices in ADR-0006
(the fusion strategy itself stands until the labelled evaluation says otherwise).

## Context
Hybrid retrieval (ADR-0006) fuses lexical, vector and skill signals. The
vector signal came from OpenAI `text-embedding-3-small` (1536-d). When no
`OPENAI_API_KEY` was set, `get_embedding_provider()` silently fell back to the
mock provider, whose "embeddings" are SHA-256 bytes cycled to 1536 floats —
vectors with no semantic content, all positive, so any two scored ~0.75
cosine. The planned free deployment runs generation on Groq, which has no
embeddings endpoint, so in production the vector half of retrieval would have
been a near-constant noise term.

Separately, the IVFFlat index (migration 0004) was created on an empty table.
IVFFlat learns cluster centroids at build time, so it never had meaningful
lists, and rebuilding it on populated data exceeded the default
`maintenance_work_mem` (docs/product/metrics, OPERATIONS.md).

## Decision
1. **Embeddings are their own provider interface** (`intelligence/embeddings.py`),
   chosen by `EMBEDDING_PROVIDER` independently of the LLM provider:
   - `local` (default): `BAAI/bge-small-en-v1.5` through ONNX Runtime via
     fastembed. CPU only, no key, no per-call cost; 8.7 ms/text in a warm
     batch of 256 on a laptop CPU, ~65 MB of model files baked into the
     Space image (`docs/product/metrics/embedding-model.json`).
   - `openai`: `text-embedding-3-small` requested at 384 dims (Matryoshka
     truncation), so it fills the same column.
   - `mock`: tests only; now centred and L2-normalised so it at least behaves
     geometrically like an embedding.
2. **384 dimensions** (`packages/contracts` `EMBEDDING_DIMENSION`), the local
   model's native size and a size OpenAI can serve.
3. **Every vector records its model** (`evidence.embedding_model`). Retrieval
   only scores vectors whose model matches the query vector's; a query with no
   model id skips the vector signal rather than guessing. The OpenAI identity
   includes the dimension (`text-embedding-3-small@384`) because the same
   model at another size is another vector space.
4. **HNSW instead of IVFFlat** (migration 0011): no training step, accurate
   under incremental inserts, which is how evidence arrives.
5. **`hnsw.ef_search = 100` with iterative scan** for the vector branch, set
   per transaction in `hybrid_search`.
6. A **backfill** (`python -m proofhire_worker.intelligence.reembed`) re-embeds
   rows whose vector is missing or from another model; the container runs it
   in the background at start, so changing provider needs no manual step.

## Evidence
From `docs/product/metrics/query-benchmark.md` (20k rows, real bge-small
embeddings):

- pgvector's default `ef_search = 40` is also the most rows one HNSW scan
  returns; the vector branch asks for 50, so it returned 40 and recall@50 vs
  the exact scan was 0.800. At 100 with iterative scan: 50 rows, 0.967, 4.78 ms.
- The full hybrid query's top-10 matched the exact scan exactly (1.0) at
  11.5 ms p50 vs 89.6 ms without indexes.
- On random vectors (`query-benchmark-random-vectors.md`) recall is 0.2–0.56
  at any setting: the worst case, reported rather than hidden.

The model choice itself (bge-small vs alternatives, query instruction on/off,
fusion weights) is evaluated against human labels in `packages/evals`, not
decided here.

## Consequences
- A deployment without any paid API key still has real semantic retrieval.
- Migration 0011 clears existing vectors (no meaningful 1536→384 projection
  exists); the backfill restores them from the stored evidence text.
- The worker process holds the model in memory: +251 MB resident after load,
  +313 MB at peak while embedding a batch, 1.4 s to load from the local cache
  (`embedding-model.json`, from `apps/worker/scripts/measure_embedding_model.py`).
  The API process never loads it (its search endpoint is lexical).
- Requires pgvector ≥ 0.8.0 for `hnsw.iterative_scan` (Supabase: 0.8.2; CI
  image: pgvector/pgvector:pg16).
