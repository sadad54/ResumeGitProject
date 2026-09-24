"""One-time population of the read-only guest/demo account (checklist:
recruiter-facing live demo without a GitHub OAuth dance — see routers/demo.py
and dependencies.get_current_user's is_demo enforcement).

Runs the real pipeline end to end against a real public repository — real
GitHub sync, real LLM evidence extraction, real JD analysis, real retrieval +
rerank, real resume generation with the real fact guard — so the seeded demo
account is exactly what a real user's account looks like, not a hand-written
fixture. Idempotent: safe to re-run (e.g. after a schema change) since every
stage below reuses/updates existing rows rather than duplicating them.

Deliberately calls the pipeline's internal async functions directly instead of
going through Dramatiq (`sync_repositories.send(...)` etc.) — this script is
meant to run once, synchronously, to completion, with clear failures, not to
depend on a separately-running worker process consuming a queue.

Usage (from the repo root, with DATABASE_URL/REDIS_URL/GROQ_API_KEY or
ANTHROPIC_API_KEY/OPENAI_API_KEY set in the environment — see .env.example):

    python apps/api/scripts/seed_demo.py --github-token <PAT with public_repo read> \\
        --repo-owner sadad54 --repo-name ResumeGitProject
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLE_JD = """\
Backend / AI Engineer — ProofHire-style role (sample JD for the live demo)

We're hiring a backend engineer to build evidence-grounded LLM features on
top of a FastAPI + async Postgres stack. You'll work across ingestion,
retrieval and generation.

Required:
- Python, FastAPI, async SQLAlchemy or equivalent async ORM experience
- PostgreSQL, including indexing and query performance work
- Experience integrating LLM APIs (OpenAI, Anthropic, or similar) into a
  production backend, including structured output and schema validation
- Automated testing against a real database, not just mocks
- Docker and CI/CD (GitHub Actions or equivalent)

Preferred:
- pgvector or another vector search engine, and hybrid (lexical + vector)
  retrieval
- Background job processing (Celery, Dramatiq, or similar) with Redis
- Experience with retrieval-augmented generation (RAG) and grounding
  generated text in verifiable sources
- Next.js/React on the frontend
"""


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--github-token", required=True, help="PAT with public_repo read, owned by --repo-owner")
    ap.add_argument("--repo-owner", default="sadad54")
    ap.add_argument("--repo-name", default="ResumeGitProject")
    args = ap.parse_args()

    # Imported here, not at module level: pythonpath for proofhire_api/
    # proofhire_worker is only set up once sys.path is patched above.
    from sqlalchemy import select

    from proofhire_api.db import async_session_factory
    from proofhire_api.models.github_connection import GitHubConnection
    from proofhire_api.models.job import Job
    from proofhire_api.models.repository import Repository
    from proofhire_api.models.sync_run import SyncRun
    from proofhire_api.models.user import User
    from proofhire_api.security.password import hash_password
    from proofhire_api.security.token_crypto import encrypt_token
    from proofhire_api.services.github_client import GitHubClient
    from proofhire_contracts import SyncStatus
    from proofhire_worker.intelligence import coverage, generation, job_analysis
    from proofhire_worker.intelligence.evidence_extraction import (
        _extract_for_repository,
        extract_evidence,
    )
    from proofhire_worker.ingestion import sync as sync_module

    async with async_session_factory() as session:
        # --- demo user -----------------------------------------------------
        user = await session.scalar(select(User).where(User.email == "demo@proofhire.app"))
        if user is None:
            user = User(
                email="demo@proofhire.app",
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                display_name="Demo Guest",
                is_demo=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        print(f"demo user: {user.id}")

        # --- GitHub connection (bypasses the OAuth browser flow: this is a
        # trusted admin script, not a public endpoint) ----------------------
        connection = await session.scalar(
            select(GitHubConnection).where(GitHubConnection.user_id == user.id)
        )
        client = GitHubClient(args.github_token)
        remote_repos = await client.list_user_repositories()
        remote = next(
            (
                r
                for r in remote_repos
                if r["owner"]["login"].lower() == args.repo_owner.lower()
                and r["name"].lower() == args.repo_name.lower()
            ),
            None,
        )
        if remote is None:
            raise SystemExit(
                f"{args.repo_owner}/{args.repo_name} not visible to this token's "
                "account — the token must belong to the repo owner (or a collaborator)."
            )

        if connection is None:
            connection = GitHubConnection(
                user_id=user.id,
                github_user_id=remote["owner"]["id"],
                login=remote["owner"]["login"],
                token_ref=encrypt_token(args.github_token),
                scopes=["read:user", "public_repo"],
            )
            session.add(connection)
        else:
            connection.token_ref = encrypt_token(args.github_token)
        await session.commit()
        print(f"github connection: {connection.login}")

        # --- repository row --------------------------------------------------
        repository = await session.scalar(
            select(Repository).where(
                Repository.user_id == user.id, Repository.provider_repo_id == remote["id"]
            )
        )
        if repository is None:
            repository = Repository(
                user_id=user.id,
                provider_repo_id=remote["id"],
                owner=remote["owner"]["login"],
                name=remote["name"],
                url=remote["html_url"],
                visibility="private" if remote.get("private") else "public",
                default_branch=remote.get("default_branch", "main"),
                stars=remote.get("stargazers_count", 0),
                selected=True,
            )
            session.add(repository)
        else:
            repository.selected = True
        await session.commit()
        await session.refresh(repository)
        print(f"repository: {repository.owner}/{repository.name} ({repository.id})")

        # --- sync + evidence extraction, run inline (see module docstring) --
        sync_run = SyncRun(
            user_id=user.id, repository_ids=[str(repository.id)], status=SyncStatus.QUEUED
        )
        session.add(sync_run)
        await session.commit()
        await session.refresh(sync_run)

        extraction_calls: list[tuple[str, str, list[str]]] = []
        original_send = extract_evidence.send
        extract_evidence.send = lambda repo_id, run_id, artifact_ids: extraction_calls.append(
            (repo_id, run_id, artifact_ids)
        )
        try:
            await sync_module._run(str(sync_run.id), [str(repository.id)])
        finally:
            extract_evidence.send = original_send
        print(f"sync run: {sync_run.status}")

        for repo_id_str, run_id_str, artifact_ids in extraction_calls:
            print(f"extracting evidence for {len(artifact_ids)} changed artifacts...")
            await _extract_for_repository(repo_id_str, run_id_str, artifact_ids)
        if not extraction_calls:
            print("no changed artifacts — evidence graph already up to date")

        # --- JD + retrieval + generation -------------------------------------
        job = await session.scalar(
            select(Job).where(Job.user_id == user.id, Job.source_text == SAMPLE_JD)
        )
        if job is None:
            job = Job(id=uuid.uuid4(), user_id=user.id, source_text=SAMPLE_JD)
            session.add(job)
            await session.commit()
            await session.refresh(job)
        print(f"job: {job.id}")

        await job_analysis._analyze(str(job.id))
        print("job analysis: done")

        await coverage._compute_coverage(str(job.id))
        print("coverage: done")

        await generation._generate(str(job.id), "conservative", "resume")
        print("resume generation: done")

    print("\nSeed complete. Point the frontend's 'View live demo' button at "
          "POST /api/v1/demo/session — it will resolve to this account.")


if __name__ == "__main__":
    asyncio.run(main())
