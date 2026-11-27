"""Load test of the API's read path (F1): 10 / 50 / 100 / 250 concurrent users.

Each virtual user is signed in (a token minted with the API's own signing
function, so bcrypt login cost doesn't blur the read path) and cycles the
requests the web app makes while someone uses it — session, overview,
evidence list, evidence graph, jobs, documents — with 0-500 ms of think time.
25 seeded accounts carry realistic data (40 evidence items with sources and
skills, a job with 8 requirements and matches, a generated document with
claims); users share accounts the way several open tabs would.

Measures, per concurrency level: throughput, error rate, and p50/p95/p99
latency overall and per endpoint. Client and server share one machine, which
the report states; the numbers describe the application on a single uvicorn
worker (the Space's configuration), not the Space's hardware.

    python apps/api/scripts/load_test.py --api http://localhost:8000 --out ../../docs/product/metrics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import statistics
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from proofhire_contracts import DocumentType, EvidenceType, GenerationRunStatus, RequirementCategory
from sqlalchemy import delete

from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.generated_claim import GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.repositories.evidence import (
    EvidenceCandidate,
    EvidenceSourceCandidate,
    SQLAlchemyEvidenceRepository,
)
from proofhire_api.security.jwt import create_access_token

ACCOUNTS = 25
EVIDENCE_PER_ACCOUNT = 40
LEVELS = (10, 50, 100, 250)
SKILLS = ["python", "fastapi", "postgresql", "redis", "docker", "react", "typescript",
          "pytest", "kubernetes", "pgvector", "llm", "rag", "sqlalchemy", "celery"]
ENDPOINTS = [  # (name, path, weight)
    ("auth_me", "/api/v1/auth/me", 20),
    ("overview", "/api/v1/me/overview", 20),
    ("evidence", "/api/v1/evidence", 20),
    ("evidence_graph", "/api/v1/evidence/graph", 15),
    ("jobs", "/api/v1/jobs", 15),
    ("documents", "/api/v1/documents", 10),
]


async def seed_account(tag: str) -> uuid.UUID:
    rng = random.Random(tag)
    async with async_session_factory() as session:
        user = User(email=f"load-{tag}@example.com", hashed_password="unused")
        session.add(user)
        await session.flush()
        repo = Repository(user_id=user.id, provider_repo_id=rng.randint(1, 2_000_000_000),
                          owner="load", name=f"svc-{tag}", url="https://github.com/load/svc",
                          selected=True, last_analyzed_sha="a" * 40, sync_status="completed")
        session.add(repo)
        await session.flush()
        artifact = SourceArtifact(repository_id=repo.id, type="source_file", path="app/main.py",
                                  commit_sha="a" * 40, content_hash="b" * 64, priority="p1")
        session.add(artifact)
        await session.flush()
        saved = await SQLAlchemyEvidenceRepository(session).save_candidates([
            EvidenceCandidate(
                user_id=user.id, repository_id=repo.id, evidence_type=EvidenceType.IMPLEMENTATION,
                title=f"Implementation {i}: {' '.join(rng.sample(SKILLS, 2))}",
                normalized_claim=f"Built component {i} with {', '.join(rng.sample(SKILLS, 3))}.",
                description="Synthetic evidence for load testing. " * 3,
                confidence=round(rng.uniform(0.5, 0.95), 2), extraction_method="load-test",
                sources=[EvidenceSourceCandidate(source_artifact_id=artifact.id,
                                                 locator="app/main.py", snippet_hash="c" * 64,
                                                 commit_sha="a" * 40)],
                skill_names=rng.sample(SKILLS, 3),
            )
            for i in range(EVIDENCE_PER_ACCOUNT)
        ])
        for evidence in saved:
            evidence.status = "confirmed"
        job = Job(user_id=user.id, source_text="Backend engineer, Python and FastAPI.",
                  role="Backend Engineer", status="ready")
        session.add(job)
        await session.flush()
        for r in range(8):
            requirement = Requirement(job_id=job.id, category=RequirementCategory.SKILL,
                                      text=f"Requirement {r}: {rng.choice(SKILLS)}",
                                      normalized=[rng.choice(SKILLS)], importance=0.7,
                                      required=r < 5)
            session.add(requirement)
            await session.flush()
            for evidence in rng.sample(saved, 3):
                session.add(EvidenceMatch(requirement_id=requirement.id, evidence_id=evidence.id,
                                          retrieval_score=0.8, rerank_score=0.8,
                                          match_reason="Load test.", status="strong"))
        run = GenerationRun(user_id=user.id, job_id=job.id, pipeline_version="load",
                            status=GenerationRunStatus.SUCCEEDED)
        session.add(run)
        await session.flush()
        document = GeneratedDocument(job_id=job.id, generation_run_id=run.id,
                                     type=DocumentType.RESUME,
                                     content_json={"summary": "s", "skills": SKILLS[:5],
                                                   "experience": [], "projects": []})
        session.add(document)
        await session.flush()
        for c in range(6):
            session.add(GeneratedClaim(document_id=document.id, claim_text=f"Claim {c}",
                                       claim_type="skill", verification_status="supported",
                                       confidence=1.0))
        await session.commit()
        return user.id


async def cleanup(user_ids: list[uuid.UUID]) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * p))], 1)


async def run_level(api: str, tokens: list[str], users: int, seconds: float) -> dict:
    samples: dict[str, list[float]] = defaultdict(list)
    failures: dict[str, int] = defaultdict(int)
    names = [e[0] for e in ENDPOINTS]
    weights = [e[2] for e in ENDPOINTS]
    paths = {e[0]: e[1] for e in ENDPOINTS}
    limits = httpx.Limits(max_connections=users, max_keepalive_connections=users)
    async with httpx.AsyncClient(base_url=api, timeout=60, limits=limits) as client:
        start = time.perf_counter()
        warm_until = start + 5
        deadline = warm_until + seconds

        async def user(i: int) -> None:
            rng = random.Random(i)
            headers = {"Authorization": f"Bearer {tokens[i % len(tokens)]}"}
            while (now := time.perf_counter()) < deadline:
                name = rng.choices(names, weights)[0]
                t0 = time.perf_counter()
                try:
                    response = await client.get(paths[name], headers=headers)
                    ok = response.status_code == 200
                except httpx.HTTPError:
                    ok = False
                elapsed = (time.perf_counter() - t0) * 1000
                if now >= warm_until:
                    samples[name].append(elapsed)
                    if not ok:
                        failures[name] += 1
                await asyncio.sleep(rng.uniform(0, 0.5))

        await asyncio.gather(*(user(i) for i in range(users)))
    all_ms = [v for vs in samples.values() for v in vs]
    total = len(all_ms)
    return {
        "users": users,
        "requests": total,
        "throughput_rps": round(total / seconds, 1),
        "error_rate": round(sum(failures.values()) / total, 4) if total else None,
        "p50_ms": pct(all_ms, 0.50), "p95_ms": pct(all_ms, 0.95), "p99_ms": pct(all_ms, 0.99),
        "per_endpoint": {
            name: {"requests": len(vs), "errors": failures[name], "p50_ms": pct(vs, 0.5),
                   "p95_ms": pct(vs, 0.95), "mean_ms": round(statistics.mean(vs), 1)}
            for name, vs in samples.items() if vs
        },
    }


async def main(api: str, out_dir: Path, seconds: float, label: str) -> None:
    tag = uuid.uuid4().hex[:6]
    t0 = time.perf_counter()
    user_ids = [await seed_account(f"{tag}-{i}") for i in range(ACCOUNTS)]
    print(f"seeded {ACCOUNTS} accounts in {time.perf_counter() - t0:.0f}s", flush=True)
    tokens = [create_access_token(uid) for uid in user_ids for _ in range(10)]
    levels = []
    try:
        for users in LEVELS:
            result = await run_level(api, tokens, users, seconds)
            levels.append(result)
            print(f"{users:4} users: {result['throughput_rps']:7} req/s  "
                  f"p50 {result['p50_ms']:7} ms  p95 {result['p95_ms']:7} ms  "
                  f"p99 {result['p99_ms']:7} ms  errors {result['error_rate']:.2%}", flush=True)
    finally:
        await cleanup(user_ids)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "label": label,
        "api": api,
        "seconds_per_level": seconds,
        "accounts": ACCOUNTS, "evidence_per_account": EVIDENCE_PER_ACCOUNT,
        "think_time_ms": [0, 500],
        "endpoint_mix": {name: weight for name, _path, weight in ENDPOINTS},
        "server": "uvicorn, 1 worker (as on the Space); client on the same machine",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpus": os.cpu_count()},
        "levels": levels,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"load-test-{label}.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--seconds", type=float, default=45)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--out", type=Path, default=Path("../../docs/product/metrics"))
    args = ap.parse_args()
    asyncio.run(main(args.api, args.out, args.seconds, args.label))
