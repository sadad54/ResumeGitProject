"""Query benchmark for the hybrid-retrieval path (checklist §13.10, §13.11).

Loads a synthetic evidence corpus at a stated scale, runs EXPLAIN (ANALYZE,
BUFFERS) on the exact SQL `SQLAlchemyEvidenceRepository.hybrid_search` issues,
then drops the ADR-0006 indexes (GIN on search_vector, IVFFlat on embedding),
re-runs, and recreates them. Writes a JSON report and a Markdown summary that
every number in docs/product/metrics traces back to.

Synthetic, and says so: this measures the *query plan and indexes* at scale,
which is the question EXPLAIN answers. It does not measure retrieval quality —
that needs the labelled benchmark, which is out of scope here. Row text is
drawn from a small technical vocabulary so tsvector/GIN behave like real
evidence text (varied terms, realistic posting-list sizes), and embeddings are
random unit vectors, which is the worst case for IVFFlat recall but a fair
case for its latency.

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
from proofhire_api.repositories.evidence import EvidenceQuery, SQLAlchemyEvidenceRepository
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


def _claim() -> str:
    return " ".join(random.sample(VOCAB, k=random.randint(6, 12))).capitalize() + "."


def _unit_vector() -> str:
    v = [random.gauss(0, 1) for _ in range(EMBEDDING_DIMENSION)]
    n = sum(x * x for x in v) ** 0.5
    return "[" + ",".join(f"{x / n:.6f}" for x in v) + "]"


async def _load_corpus(session, user_id: uuid.UUID, rows: int) -> None:
    repo_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, hashed_password) VALUES (:id, :email, 'x')"
        ),
        {"id": str(user_id), "email": f"bench-{user_id.hex[:8]}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO repositories (id, user_id, provider_repo_id, owner, name, url) "
            "VALUES (:id, :uid, :prid, 'bench', 'bench', 'https://example.com')"
        ),
        {"id": str(repo_id), "uid": str(user_id), "prid": random.randint(1, 2_000_000_000)},
    )
    await session.execute(
        text(
            "INSERT INTO source_artifacts (id, repository_id, type, path, commit_sha, content_hash, "
            "priority) VALUES (:id, :rid, 'source_file', 'bench.py', :sha, :h, 'p1')"
        ),
        {"id": str(artifact_id), "rid": str(repo_id), "sha": "a" * 40, "h": "b" * 64},
    )
    await session.commit()

    batch = 1000
    for start in range(0, rows, batch):
        params = [
            {
                "id": str(uuid.uuid4()),
                "uid": str(user_id),
                "rid": str(repo_id),
                "title": " ".join(random.sample(VOCAB, k=3)),
                "claim": _claim(),
                "desc": _claim(),
                "emb": _unit_vector(),
            }
            for _ in range(min(batch, rows - start))
        ]
        await session.execute(
            text(
                "INSERT INTO evidence (id, user_id, repository_id, evidence_type, title, "
                "normalized_claim, description, confidence, extraction_method, status, embedding) "
                "VALUES (:id, :uid, :rid, 'skill_usage', :title, :claim, :desc, 0.8, 'bench', "
                "'confirmed', CAST(:emb AS vector))"
            ),
            params,
        )
        await session.commit()
    await session.execute(text("ANALYZE evidence"))
    await session.commit()


async def _timed_search(session, query: EvidenceQuery, runs: int) -> dict:
    repo = SQLAlchemyEvidenceRepository(session)
    await repo.hybrid_search(query)  # warm
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        await repo.hybrid_search(query)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return {
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 2),
        "min_ms": round(samples[0], 2),
        "runs": runs,
    }


async def _explain(session, query: EvidenceQuery) -> str:
    """EXPLAIN the same SQL hybrid_search builds, by monkeypatching execute."""
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
    return "\n".join(r[0] for r in result.fetchall())


async def main(rows: int, runs: int, out: Path) -> None:
    random.seed(20260919)
    user_id = uuid.uuid4()
    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "synthetic": True,
        "rows": rows,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "queries": {},
    }

    async with async_session_factory() as session:
        pg = (await session.execute(text("SELECT version()"))).scalar()
        report["environment"]["postgres"] = pg
        t0 = time.perf_counter()
        await _load_corpus(session, user_id, rows)
        report["load_seconds"] = round(time.perf_counter() - t0, 1)

        try:
            embedding = [float(x) for x in _unit_vector().strip("[]").split(",")]
            for name, text_q, skills in QUERIES:
                q = EvidenceQuery(
                    user_id=user_id,
                    text=text_q,
                    embedding=embedding if "vector" in name else None,
                    skill_keywords=skills,
                    limit=10,
                )
                entry: dict = {"text": text_q, "skill_keywords": skills}
                entry["with_indexes"] = await _timed_search(session, q, runs)
                entry["plan_with_indexes"] = await _explain(session, q)

                await session.execute(text("DROP INDEX IF EXISTS ix_evidence_search_vector"))
                await session.execute(text("DROP INDEX IF EXISTS ix_evidence_embedding_ivfflat"))
                await session.commit()
                try:
                    entry["without_indexes"] = await _timed_search(session, q, runs)
                    entry["plan_without_indexes"] = await _explain(session, q)
                finally:
                    # Found by this script: building IVFFlat over 1536-dim vectors
                    # needs > the 64 MB default maintenance_work_mem even at 2k
                    # rows. Migration 0004 never hit it because it indexed an
                    # empty table; a production rebuild would. Recorded in
                    # infra/deployment/OPERATIONS.md.
                    await session.execute(text("SET maintenance_work_mem = '512MB'"))
                    await session.execute(
                        text("CREATE INDEX ix_evidence_search_vector ON evidence USING GIN (search_vector)")
                    )
                    await session.execute(
                        text(
                            "CREATE INDEX ix_evidence_embedding_ivfflat ON evidence "
                            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
                        )
                    )
                    await session.commit()
                report["queries"][name] = entry
        finally:
            await session.rollback()
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
            await session.commit()

    out.mkdir(parents=True, exist_ok=True)
    (out / "query-benchmark.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# Query benchmark: hybrid retrieval",
        "",
        f"Generated {report['generated_at']} by `apps/api/scripts/benchmark_queries.py`.",
        "",
        f"**Synthetic corpus**: {rows:,} evidence rows ({EMBEDDING_DIMENSION}-dim random unit "
        "embeddings, technical-vocabulary claims), one user. Measures the query plan and index "
        "effect at scale — not retrieval quality, which needs the labelled benchmark.",
        "",
        f"Environment: {pg.split(',')[0]}; Python {report['environment']['python']}; "
        f"{report['environment']['platform']}. Corpus load: {report['load_seconds']}s.",
        "",
        "| Query | With indexes p50 / p95 | Without indexes p50 / p95 | Speedup (p50) |",
        "|---|---|---|---|",
    ]
    for name, e in report["queries"].items():
        w, wo = e["with_indexes"], e["without_indexes"]
        speed = wo["p50_ms"] / w["p50_ms"] if w["p50_ms"] else float("nan")
        lines.append(
            f"| {name} | {w['p50_ms']} / {w['p95_ms']} ms | {wo['p50_ms']} / {wo['p95_ms']} ms | {speed:.1f}× |"
        )
    lines += ["", "Full EXPLAIN (ANALYZE, BUFFERS) plans are in `query-benchmark.json`.", ""]
    for name, e in report["queries"].items():
        lines += [f"## {name} — with indexes", "```", e["plan_with_indexes"], "```", ""]
    (out / "query-benchmark.md").write_text("\n".join(lines))
    print((out / "query-benchmark.md").read_text().split("Full EXPLAIN")[0])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20_000)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--out", type=Path, default=Path("../../docs/product/metrics"))
    a = ap.parse_args()
    asyncio.run(main(a.rows, a.runs, a.out))
