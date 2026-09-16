"""Coverage engine (PRD §17-18, §34 B5): for every Requirement on a Job, retrieve
candidate Evidence via hybrid_search, rerank with an LLM judge, and persist the
result as an EvidenceMatch — or nothing, if no candidates were even retrieved,
which the API layer treats as an implicit Gap (PRD §17: Gap = "no defensible
evidence").

Runs on the `ai` queue, chained after analyze_job completes (mirrors how sync
chains into extract_evidence in Phase 1/2) — no separate "compute coverage"
button is needed once both a job's requirements and the user's evidence exist.
"""

import logging
import uuid

import dramatiq
from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.job import Job
from proofhire_api.models.requirement import Requirement
from proofhire_api.repositories.evidence import EvidenceQuery, SQLAlchemyEvidenceRepository
from proofhire_prompts.rerank_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from sqlalchemy import delete, select

from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
from proofhire_worker.intelligence.match_label import resolve_match_label
from proofhire_worker.intelligence.provider_factory import get_embedding_provider, get_provider
from proofhire_worker.intelligence.schemas import RerankOutput

logger = logging.getLogger(__name__)

CANDIDATES_PER_REQUIREMENT = 5


@dramatiq.actor(max_retries=1, queue_name="ai", time_limit=300_000)
def compute_coverage(job_id: str) -> None:
    import asyncio

    asyncio.run(_compute_coverage(job_id))


async def _compute_coverage(job_id_str: str) -> None:
    job_id = uuid.UUID(job_id_str)
    provider = get_provider()
    embedding_provider = get_embedding_provider()
    model_config = ModelConfig(model="claude-sonnet-5")

    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if job is None:
            logger.error("job_not_found", extra={"job_id": job_id_str})
            return

        requirements = list(
            await session.scalars(select(Requirement).where(Requirement.job_id == job_id))
        )
        if not requirements:
            job.status = "ready"
            await session.commit()
            return

        # Recompute atomically; old matches cannot survive a changed ranking.
        await session.execute(delete(EvidenceMatch).where(
            EvidenceMatch.requirement_id.in_([r.id for r in requirements])
        ))

        evidence_repo = SQLAlchemyEvidenceRepository(session)
        strong = partial = gap = unknown = 0

        for requirement in requirements:
            try:
                [embedding] = await embedding_provider.embed(
                    [requirement.text], model="text-embedding-3-small"
                )
            except Exception:
                embedding = None
                logger.warning(
                    "requirement_embedding_failed", extra={"requirement_id": str(requirement.id)}
                )

            hits = await evidence_repo.hybrid_search(
                EvidenceQuery(
                    user_id=job.user_id,
                    text=requirement.text,
                    embedding=embedding,
                    skill_keywords=requirement.normalized,
                    limit=CANDIDATES_PER_REQUIREMENT,
                )
            )

            if not hits:
                gap += 1  # no EvidenceMatch row persisted — implicit Gap (PRD §17)
                continue

            candidates = [
                (i, h.title, h.normalized_claim, "") for i, h in enumerate(hits)
            ]
            try:
                result = await provider.structured_generate(
                    task="rerank",
                    messages=[
                        Message(role="system", content=SYSTEM_PROMPT),
                        Message(
                            role="user",
                            content=build_user_message(requirement.text, candidates),
                        ),
                    ],
                    schema=RerankOutput,
                    model_config=model_config,
                )
            except Exception:
                logger.exception(
                    "rerank_failed", extra={"requirement_id": str(requirement.id)}
                )
                unknown += 1
                continue

            logger.info(
                "llm_call_completed",
                extra={
                    "task": "rerank",
                    "prompt_version": PROMPT_VERSION,
                    "provider": result.usage.provider,
                    "model": result.usage.model,
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "latency_ms": result.usage.latency_ms,
                    "estimated_cost_usd": result.usage.estimated_cost_usd,
                    "requirement_id": str(requirement.id),
                },
            )

            output = result.value
            label = resolve_match_label(output.label)

            if output.best_evidence_index is None or not (
                0 <= output.best_evidence_index < len(hits)
            ):
                gap += 1
                continue

            best_hit = hits[output.best_evidence_index]
            rerank_score = (
                output.directness + output.depth + output.recency + output.source_quality
            ) / 4.0

            existing = await session.scalar(
                select(EvidenceMatch).where(
                    EvidenceMatch.requirement_id == requirement.id,
                    EvidenceMatch.evidence_id == best_hit.id,
                )
            )
            if existing is not None:
                existing.retrieval_score = best_hit.score
                existing.rerank_score = rerank_score
                existing.match_reason = output.reason
                existing.status = label
            else:
                session.add(
                    EvidenceMatch(
                        requirement_id=requirement.id,
                        evidence_id=best_hit.id,
                        retrieval_score=best_hit.score,
                        rerank_score=rerank_score,
                        match_reason=output.reason,
                        status=label,
                    )
                )

            if label.value == "strong":
                strong += 1
            elif label.value == "partial":
                partial += 1
            elif label.value == "gap":
                gap += 1
            else:
                unknown += 1

        job.status = "coverage_failed" if unknown else "ready"
        await session.commit()

        # Not re-publishing job.analysis.completed here: job_analysis.py already
        # fires it once requirements are ready, and the frontend's EventSource
        # closes on that first occurrence (PRD's canonical event list has no
        # separate "coverage ready" event, and adding one needs an ADR per the
        # Contract Freeze Rule — PRD §35). The coverage UI fetches/refreshes
        # GET /jobs/{id}/coverage directly instead of listening for a second event.
        logger.info(
            "coverage_computation_completed",
            extra={
                "job_id": job_id_str,
                "strong": strong,
                "partial": partial,
                "gap": gap,
                "unknown": unknown,
            },
        )

