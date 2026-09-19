"""Positioning Planner (PRD §19.1). Reused by both the standalone
POST /jobs/{id}/positioning endpoint (lets a user review positioning before
generating) and the generation pipeline itself, since generation needs the
same positioning context internally.
"""

from proofhire_api.models.evidence import Evidence
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.job import Job
from proofhire_api.models.requirement import Requirement
from proofhire_prompts.position_v1 import SYSTEM_PROMPT, build_user_message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_worker.intelligence.llm_provider import Message, ModelConfig, StructuredResult
from proofhire_worker.intelligence.provider_factory import get_provider
from proofhire_worker.intelligence.schemas import PositioningOutput


async def _build_coverage_summary(session: AsyncSession, job_id) -> str:
    requirements = list(
        await session.scalars(select(Requirement).where(Requirement.job_id == job_id))
    )
    lines = []
    for requirement in requirements:
        match = await session.scalar(
            select(EvidenceMatch).where(EvidenceMatch.requirement_id == requirement.id)
        )
        if match is None:
            lines.append(f"- [{requirement.text}] -> GAP (no evidence found)")
            continue
        evidence = await session.get(Evidence, match.evidence_id)
        title = evidence.title if evidence else "unknown"
        lines.append(f"- [{requirement.text}] -> {match.status.upper()} (evidence: {title})")
    return "\n".join(lines) if lines else "(no requirements analyzed yet)"


async def compute_positioning(session: AsyncSession, job: Job) -> tuple[PositioningOutput, StructuredResult]:
    coverage_summary = await _build_coverage_summary(session, job.id)
    provider = get_provider()

    result = await provider.structured_generate(
        task="position",
        messages=[
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=build_user_message(job.role or "Unknown role", coverage_summary)),
        ],
        schema=PositioningOutput,
        model_config=ModelConfig(model="claude-sonnet-5"),
    )
    return result.value, result
