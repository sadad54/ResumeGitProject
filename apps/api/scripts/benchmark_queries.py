"""Query benchmark for the hybrid-retrieval path (checklist §13.10, §13.11).

Loads a synthetic evidence corpus at a stated scale, runs EXPLAIN (ANALYZE,
BUFFERS) on the exact SQL `SQLAlchemyEvidenceRepository.hybrid_search` issues,
then drops the retrieval indexes (GIN on search_vector, HNSW on embedding),
re-runs, and recreates them. Writes a JSON report and a Markdown summary that
every number in docs/product/metrics traces back to.

Synthetic, and says so: this measures the *query plan and indexes* at scale,
which is the question EXPLAIN answers — not retrieval quality, which is what
packages/evals measures against human labels. Row text is drawn from a small
technical vocabulary so tsvector/GIN behave like real evidence text.

Embeddings (--embeddings):
- ``real`` (default): the production local model (bge-small, ADR-0018) embeds
  each row's text, so the vectors have the neighbourhood structure an
  approximate index relies on. Slow to load (~30 ms/row on a laptop CPU).
- ``random``: random unit vectors, the unstructured worst case for an ANN
  index's recall. Fast; useful as a stress test.

Besides latency with/without indexes, it reports how far approximate results
drift from the exact scan: `recall_at_10_vs_exact` for each hybrid query, and
an `ann_sweep` of the vector branch alone across hnsw.ef_search and iterative
scan settings — the measurement behind repositories/evidence.HNSW_EF_SEARCH.
The first version of this benchmark ran against the 1536-d IVFFlat index;
those results are kept in query-benchmark-ivfflat-1536d.*.

Run from apps/api with DATABASE_URL set:
    python scripts/benchmark_queries.py --rows 20000 --out ../../docs/product/metrics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import random
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from proofhire_api.db import async_session_factory
from proofhire_api.repositories.evidence import (
    HNSW_EF_SEARCH,
    EvidenceQuery,
    SQLAlchemyEvidenceRepository,
)
from proofhire_contracts.embedding import EMBEDDING_DIMENSION

VOCAB = (
    "python fastapi sqlalchemy postgres pgvector redis dramatiq kafka grpc react nextjs "
    "typescript docker kubernetes terraform ci github-actions pytest playwright opentelemetry "
    "embedding retrieval reranker prompt evaluation latency throughput cache migration schema "
    "async worker queue streaming sse oauth jwt encryption secret-scanning ingestion parser"
).split()

QUERIES = [
    ("lexical+skills", "kafka streaming ingestion pipeline", ["kafka", "python"]),
    ("lexical only", "postgres migration schema", []),
    ("vector+lexical", "evaluation harness for retrieval latency", ["pytest"]),
]

SWEEP_QUERIES = 20
SWEEP_K = 50
VECTOR_BRANCH_SQL = """
SELECT e.id FROM evidence e
WHERE e.user_id = :uid AND e.embedding IS NOT NULL AND e.embedding_model = :model
ORDER BY e.embedding <=> CAST(:v AS vector) LIMIT :k
"""


def _claim() -> str:
    return " ".join(random.sample(VOCAB, k=random.randint(6, 12))).capitalize() + "."


def _random_unit() -> list[float]:
    v = [random.gauss(0, 1) for _ in range(EMBEDDING_DIMENSION)]
    n = sum(x * x for x in v) ** 0.5
    return [x / n for x in v]


def _literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


class Embedder:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        if mode == "real":
            from proofhire_worker.intelligence.embeddings import LocalEmbeddingProvider

            self._provider = LocalEmbeddingProvider()
            self.model_id = self._provider.model_id
        else:
            self.model_id = "bench-random-unit"

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        if self.mode == "real":
            return await self._provider.embed(texts, input_type=input_type)
        return [_random_unit() for _ in texts]


async def _load_corpus(session, user_id: uuid.UUID, rows: int, embedder: Embedder) -> None:
    repo_id = uuid.uuid4()
    await session.execute(
        text("INSERT INTO users (id, email, hashed_password) VALUES (:id, :email, 'x')"),
        {"id": str(user_id), "email": f"bench-{user_id.hex[:8]}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO repositories (id, user_id, provider_repo_id, owner, name, url) "
            "VALUES (:id, :uid, :prid, 'bench', 'bench', 'https://example.com')"
        ),
        {"id": str(repo_id), "uid": str(user_id), "prid": random.randint(1, 2_000_000_000)},
    )
    await session.commit()

    batch = 500
    for start in range(0, rows, batch):
        items = [
            {"title": " ".join(random.sample(VOCAB, k=3)), "claim": _claim(), "desc": _claim()}
            for _ in range(min(batch, rows - start))
        ]
        vectors = await embedder.embed([f"{i['title']}. {i['claim']} {i['desc']}" for i in items])
        await session.execute(
            text(
                "INSERT INTO evidence (id, user_id, repository_id, evidence_type, title, "
                "normalized_claim, description, confidence, extraction_method, status, embedding, "
                "embedding_model) "
                "VALUES (:id, :uid, :rid, 'skill_usage', :title, :claim, :desc, 0.8, 'bench', "
                "'confirmed', CAST(:emb AS vector), :model)"
            ),
            [
                {**i, "id": str(uuid.uuid4()), "uid": str(user_id), "rid": str(repo_id),
                 "emb": _literal(v), "model": embedder.model_id}
                for i, v in zip(items, vectors, strict=True)
            ],
        )
        await session.commit()
    await session.execute(text("ANALYZE evidence"))
    await session.commit()


async def _timed_search(session, query: EvidenceQuery, runs: int) -> dict:
    repo = SQLAlchemyEvidenceRepository(session)
    top = [str(h.id) for h in await repo.hybrid_search(query)]  # also warms
    await session.commit()
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        await repo.hybrid_search(query)
        samples.append((time.perf_counter() - t0) * 1000)
        await session.commit()  # hybrid_search's SET LOCAL is per transaction, like a request
    samples.sort()
    return {
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 2),
        "min_ms": round(samples[0], 2),
        "runs": runs,
        "top_ids": top,
    }


async def _explain(session, query: EvidenceQuery) -> str:
    """EXPLAIN the same SQL hybrid_search builds, by capturing its final statement."""
    captured: dict = {}
    original = session.execute

    async def spy(stmt, params=None, *a, **kw):
        captured["sql"] = str(stmt.text if hasattr(stmt, "text") else stmt)
        captured["params"] = params
        return await original(stmt, params, *a, **kw)

    session.execute = spy  # type: ignore[method-assign]
    try:
        await SQLAlchemyEvidenceRepository(session).hybrid_search(query)
    finally:
        session.execute = original  # type: ignore[method-assign]

    result = await session.execute(
        text("EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + captured["sql"]), captured["params"]
    )
    plan = "\n".join(r[0] for r in result.fetchall())
    await session.commit()
    return plan


async def _ann_sweep(session, user_id: uuid.UUID, embedder: Embedder) -> list[dict]:
    """Vector branch alone: HNSW results vs the exact scan, per setting."""
    texts = [_claim() for _ in range(SWEEP_QUERIES)]
    qvecs = await embedder.embed(texts, input_type="query")
    params = [{"uid": str(user_id), "v": _literal(q), "k": SWEEP_K, "model": embedder.model_id}
              for q in qvecs]

    exact = []
    async with session.begin():
        await session.execute(text("SET LOCAL enable_indexscan = off"))
        for p in params:
            exact.append([r[0] for r in (await session.execute(text(VECTOR_BRANCH_SQL), p)).all()])

    results = []
    for ef in (40, HNSW_EF_SEARCH, 200):
        for iterative in ("off", "relaxed_order"):
            recalls, returned, latencies = [], [], []
            async with session.begin():
                await session.execute(text(f"SET LOCAL hnsw.ef_search = {ef}"))
                await session.execute(text(f"SET LOCAL hnsw.iterative_scan = {iterative}"))
                for p, ex in zip(params, exact, strict=True):
                    t0 = time.perf_counter()
                    ids = [r[0] for r in (await session.execute(text(VECTOR_BRANCH_SQL), p)).all()]
                    latencies.append((time.perf_counter() - t0) * 1000)
                    returned.append(len(ids))
                    recalls.append(len(set(ids) & set(ex)) / len(ex) if ex else 1.0)
            results.append({
                "ef_search": ef,
                "iterative_scan": iterative,
                "recall_at_50_vs_exact": round(statistics.mean(recalls), 3),
                "rows_returned_mean": round(statistics.mean(returned), 1),
                "p50_ms": round(statistics.median(latencies), 2),
                "production_setting": ef == HNSW_EF_SEARCH and iterative == "relaxed_order",
            })
    return results


async def main(rows: int, runs: int, out: Path, embeddings: str) -> None:
    random.seed(20260919)
    user_id = uuid.uuid4()
    embedder = Embedder(embeddings)
    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "synthetic": True,
        "rows": rows,
        "embeddings": embeddings,
        "embedding_model": embedder.model_id,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "hnsw_ef_search": HNSW_EF_SEARCH,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "queries": {},
    }

    async with async_session_factory() as session:
        pg = (await session.execute(text("SELECT version()"))).scalar()
        pgvector = (await session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))).scalar()
        report["environment"].update(postgres=pg, pgvector=pgvector)
        await session.commit()
        t0 = time.perf_counter()
        await _load_corpus(session, user_id, rows, embedder)
        report["load_seconds"] = round(time.perf_counter() - t0, 1)

        try:
            [query_vector] = await embedder.embed([QUERIES[2][1]], input_type="query")
            for name, text_q, skills in QUERIES:
                q = EvidenceQuery(
                    user_id=user_id,
                    text=text_q,
                    embedding=query_vector if "vector" in name else None,
                    embedding_model=embedder.model_id if "vector" in name else None,
                    skill_keywords=skills,
                    limit=10,
                )
                entry: dict = {"text": text_q, "skill_keywords": skills}
                entry["with_indexes"] = await _timed_search(session, q, runs)
                entry["plan_with_indexes"] = await _explain(session, q)

                await session.execute(text("DROP INDEX IF EXISTS ix_evidence_search_vector"))
                await session.execute(text("DROP INDEX IF EXISTS ix_evidence_embedding_hnsw"))
                await session.commit()
                try:
                    entry["without_indexes"] = await _timed_search(session, q, runs)
                    entry["plan_without_indexes"] = await _explain(session, q)
                finally:
                    # The first (IVFFlat) version of this script found that a
                    # bulk index build over 1536-d vectors needs more than the
                    # 64 MB default maintenance_work_mem (OPERATIONS.md).
                    await session.execute(text("SET maintenance_work_mem = '512MB'"))
                    await session.execute(text(
                        "CREATE INDEX ix_evidence_search_vector ON evidence USING GIN (search_vector)"
                    ))
                    t_build = time.perf_counter()
                    await session.execute(text(
                        "CREATE INDEX ix_evidence_embedding_hnsw ON evidence "
                        "USING hnsw (embedding vector_cosine_ops)"
                    ))
                    entry["hnsw_rebuild_seconds"] = round(time.perf_counter() - t_build, 1)
                    await session.commit()
                exact = entry["without_indexes"]["top_ids"]
                entry["recall_at_10_vs_exact"] = (
                    round(len(set(entry["with_indexes"]["top_ids"]) & set(exact)) / len(exact), 3)
                    if exact else None
                )
                report["queries"][name] = entry

            report["ann_sweep"] = await _ann_sweep(session, user_id, embedder)
        finally:
            await session.rollback()
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
            await session.commit()

    out.mkdir(parents=True, exist_ok=True)
    stem = "query-benchmark" if embeddings == "real" else "query-benchmark-random-vectors"
    (out / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# Query benchmark: hybrid retrieval",
        "",
        f"Generated {report['generated_at']} by `apps/api/scripts/benchmark_queries.py "
        f"--embeddings {embeddings}`.",
        "",
        f"**Synthetic corpus**: {rows:,} evidence rows, technical-vocabulary claims, one user; "
        f"{EMBEDDING_DIMENSION}-d vectors from `{embedder.model_id}`. Measures query plans, index "
        "effect and approximate-vs-exact drift at scale — not retrieval quality against human "
        "labels (that is packages/evals).",
        "",
        f"Environment: {pg.split(',')[0]}; pgvector {pgvector}; Python "
        f"{report['environment']['python']}; {report['environment']['platform']}. "
        f"Corpus load (including embedding): {report['load_seconds']}s.",
        "",
        "| Query | With indexes p50 / p95 | Without indexes p50 / p95 | Speedup (p50) "
        "| Top-10 recall vs exact |",
        "|---|---|---|---|---|",
    ]
    for name, e in report["queries"].items():
        w, wo = e["with_indexes"], e["without_indexes"]
        speed = wo["p50_ms"] / w["p50_ms"] if w["p50_ms"] else float("nan")
        recall = e["recall_at_10_vs_exact"]
        lines.append(
            f"| {name} | {w['p50_ms']} / {w['p95_ms']} ms | {wo['p50_ms']} / {wo['p95_ms']} ms "
            f"| {speed:.1f}× | {'n/a (no results)' if recall is None else recall} |"
        )
    lines += [
        "",
        f"## Vector branch: HNSW vs exact ({SWEEP_QUERIES} queries, top-{SWEEP_K})",
        "",
        "| hnsw.ef_search | iterative scan | Recall@50 vs exact | Rows returned (of 50) | p50 |",
        "|---|---|---|---|---|",
    ]
    for s in report["ann_sweep"]:
        mark = " **(production)**" if s["production_setting"] else ""
        lines.append(
            f"| {s['ef_search']}{mark} | {s['iterative_scan']} | {s['recall_at_50_vs_exact']} "
            f"| {s['rows_returned_mean']} | {s['p50_ms']} ms |"
        )
    lines += ["", "Full EXPLAIN (ANALYZE, BUFFERS) plans are in the JSON report.", ""]
    for name, e in report["queries"].items():
        lines += [f"## {name} — with indexes", "```", e["plan_with_indexes"], "```", ""]
    (out / f"{stem}.md").write_text("\n".join(lines))
    print((out / f"{stem}.md").read_text().split("Full EXPLAIN")[0])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20_000)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--embeddings", choices=("real", "random"), default="real")
    ap.add_argument("--out", type=Path, default=Path("../../docs/product/metrics"))
    a = ap.parse_args()
    asyncio.run(main(a.rows, a.runs, a.out, a.embeddings))
