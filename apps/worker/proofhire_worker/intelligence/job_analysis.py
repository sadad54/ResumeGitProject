"""JD Requirement Graph extraction (PRD §16, §34 B4).

Runs on the `ai` queue. Unlike evidence extraction, a JD is short enough to
analyze in a single structured_generate call — no chunking needed.
"""

import logging
import uuid

import dramatiq
from proofhire_api.models.job import Job
from proofhire_api.repositories.job import (
    JobAnalysisResult,
    RequirementCandidate,
    SQLAlchemyJobRepository,
)
from proofhire_api.telemetry import traced_stage
from proofhire_contracts import RequirementCategory, RunEventName
from proofhire_prompts.jd_extract_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message

from proofhire_worker.db import async_session_factory
from proofhire_worker.events import publish_event
from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
from proofhire_worker.intelligence.provider_factory import get_provider
from proofhire_worker.intelligence.schemas import JDAnalysisOutput

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {c.value for c in RequirementCategory}


@traced_stage("job_analysis")
async def _analyze(job_id_str: str) -> None:
    job_id = uuid.UUID(job_id_str)
    provider = get_provider()
    model_config = ModelConfig(model="claude-sonnet-5")

    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if job is None:
            logger.error("job_not_found", extra={"job_id": job_id_str})
            return

        job.status = "analyzing"
        await session.commit()
        await publish_event(job_id_str, RunEventName.JOB_ANALYSIS_STARTED, {"job_id": job_id_str})

        try:
            result = await provider.structured_generate(
                task="jd_extract",
                messages=[
                    Message(role="system", content=SYSTEM_PROMPT),
                    Message(role="user", content=build_user_message(job.source_text)),
                ],
                schema=JDAnalysisOutput,
                model_config=model_config,
            )
        except Exception:
            job.status = "failed"
            await session.commit()
            logger.exception("job_analysis_failed", extra={"job_id": job_id_str})
            await publish_event(job_id_str, RunEventName.JOB_ANALYSIS_COMPLETED, {"status": "failed"})
            return

        logger.info(
            "llm_call_completed",
            extra={
                "task": "jd_extract",
                "prompt_version": PROMPT_VERSION,
                "provider": result.usage.provider,
                "model": result.usage.model,
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "latency_ms": result.usage.latency_ms,
                "estimated_cost_usd": result.usage.estimated_cost_usd,
                "job_id": job_id_str,
            },
        )

        candidates: list[RequirementCandidate] = []
        for item in result.value.requirements:
            if item.category not in VALID_CATEGORIES:
                continue  # LLM returned a category outside our enum — drop, don't guess
            if not item.text.strip():
                continue
            candidates.append(
                RequirementCandidate(
                    category=RequirementCategory(item.category),
                    text=item.text,
                    normalized=item.normalized,
                    importance=item.importance,
                    required=item.required,
                )
            )

        job_repo = SQLAlchemyJobRepository(session)
        saved = await job_repo.save_analysis(
            job_id,
            JobAnalysisResult(
                role=result.value.role or None,
                company=result.value.company or None,
                seniority=result.value.seniority or None,
                requirements=candidates,
            ),
        )

        await publish_event(
            job_id_str,
            RunEventName.JOB_ANALYSIS_COMPLETED,
            {"job_id": job_id_str, "requirements_created": len(saved)},
        )

        # Chained rather than inline (same pattern as sync -> extract_evidence in
        # Phase 1/2): coverage computation runs multiple sequential LLM calls
        # (one rerank per requirement) and shouldn't block this task's completion
        # or retry semantics.
        from proofhire_worker.intelligence.coverage import compute_coverage

        job.status = "matching"
        await session.commit()
        compute_coverage.send(job_id_str)


@dramatiq.actor(max_retries=1, queue_name="ai", time_limit=120_000)
def analyze_job(job_id: str) -> None:
    import asyncio

    asyncio.run(_analyze(job_id))

