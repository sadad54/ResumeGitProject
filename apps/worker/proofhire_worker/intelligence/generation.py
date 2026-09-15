"""Generation pipeline (PRD §19): positioning -> writer -> claim verification
(deterministic fact guard authoritative for guarded types) -> repair loop
(max 2 passes) -> persistence. Runs on the `ai` queue.

Verification/repair operates at bullet (resume) or paragraph (cover letter)
granularity — a documented V1 simplification from full sub-sentence atomic
decomposition (see schemas.ClaimOutput docstring) that keeps "strip an
unsupported claim" unambiguous: drop the whole unit, never a fragment of one.
"""

import logging
import uuid

import dramatiq
from proofhire_contracts import (
    ClaimVerificationStatus,
    DocumentType,
    GenerationRunStatus,
    RunEventName,
    TailoringMode,
)
from proofhire_prompts.claim_verify_v1 import (
    PROMPT_VERSION as CLAIM_VERIFY_VERSION,
    SYSTEM_PROMPT as CLAIM_VERIFY_SYSTEM,
    build_user_message as build_claim_verify_message,
)
from proofhire_prompts.cover_letter_write_v1 import (
    PROMPT_VERSION as COVER_LETTER_WRITE_VERSION,
    SYSTEM_PROMPT as COVER_LETTER_WRITE_SYSTEM,
    build_repair_message as build_cover_letter_repair_message,
    build_user_message as build_cover_letter_write_message,
)
from proofhire_prompts.resume_write_v1 import (
    CONSERVATIVE_INSTRUCTIONS,
    FULL_INSTRUCTIONS,
    PROMPT_VERSION as RESUME_WRITE_VERSION,
    SYSTEM_PROMPT as RESUME_WRITE_SYSTEM,
    build_repair_message as build_resume_repair_message,
    build_user_message as build_resume_write_message,
)
from sqlalchemy import select

from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence import Evidence
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.generated_claim import ClaimEvidence, GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.profile_fact import ProfileFact
from proofhire_api.models.requirement import Requirement
from proofhire_worker.events import publish_event
from proofhire_worker.intelligence.claim_finalizer import finalize_claim_status
from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
from proofhire_worker.intelligence.positioning import compute_positioning
from proofhire_worker.intelligence.provider_factory import get_provider
from proofhire_worker.intelligence.schemas import (
    ClaimVerificationOutput,
    CoverLetterContentOutput,
    ResumeContentOutput,
)

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 2
PIPELINE_VERSION = "generation:v1"


def _format_profile_facts(facts: list[ProfileFact]) -> str:
    if not facts:
        return "(none confirmed)"
    return "\n".join(f"{f.id}: {f.type} = {f.value_json}" for f in facts)


def _format_evidence(items: list[Evidence]) -> str:
    if not items:
        return "(none available)"
    return "\n".join(f"{e.id}: {e.title} — {e.normalized_claim} — {e.description}" for e in items)


def _flatten_bullets(content: ResumeContentOutput) -> list[tuple[int, str]]:
    items = [(0, content.summary)]
    idx = 1
    for entry in content.experience:
        for bullet in entry.bullets:
            items.append((idx, bullet))
            idx += 1
    return items


def _location_for_index(content: ResumeContentOutput, flat_index: int) -> tuple[str, int, int]:
    if flat_index == 0:
        return ("summary", -1, -1)
    idx = 1
    for e_i, entry in enumerate(content.experience):
        for b_i in range(len(entry.bullets)):
            if idx == flat_index:
                return ("bullet", e_i, b_i)
            idx += 1
    return ("unknown", -1, -1)


def _flatten_paragraphs(content: CoverLetterContentOutput) -> list[tuple[int, str]]:
    return list(enumerate(content.body_paragraphs))


def _apply_paragraph_removals(
    content: CoverLetterContentOutput, failed_indices: set[int]
) -> CoverLetterContentOutput:
    kept = [p for i, p in enumerate(content.body_paragraphs) if i not in failed_indices]
    return content.model_copy(update={"body_paragraphs": kept})


def _apply_removals(content: ResumeContentOutput, failed_locations: set[tuple[str, int, int]]) -> ResumeContentOutput:
    new_summary = "" if ("summary", -1, -1) in failed_locations else content.summary
    new_experience = []
    for e_i, entry in enumerate(content.experience):
        kept = [b for b_i, b in enumerate(entry.bullets) if ("bullet", e_i, b_i) not in failed_locations]
        new_experience.append(entry.model_copy(update={"bullets": kept}))
    return content.model_copy(update={"summary": new_summary, "experience": new_experience})


def _log_llm_usage(task: str, prompt_version: str, result, job_id_str: str) -> None:
    logger.info(
        "llm_call_completed",
        extra={
            "task": task,
            "prompt_version": prompt_version,
            "provider": result.usage.provider,
            "model": result.usage.model,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "latency_ms": result.usage.latency_ms,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
            "job_id": job_id_str,
        },
    )


async def _run_claim_verification(
    provider,
    document_units: list[tuple[int, str]],
    profile_facts: list[ProfileFact],
    evidence_items: list[Evidence],
    job_id_str: str,
    usages: list,
):
    profile_facts_by_id = {str(f.id): f.value_json for f in profile_facts}
    evidence_by_id = {str(e.id): e for e in evidence_items}

    result = await provider.structured_generate(
        task="claim_verify",
        messages=[
            Message(role="system", content=CLAIM_VERIFY_SYSTEM),
            Message(
                role="user",
                content=build_claim_verify_message(
                    document_units, _format_profile_facts(profile_facts), _format_evidence(evidence_items)
                ),
            ),
        ],
        schema=ClaimVerificationOutput,
        model_config=ModelConfig(model="claude-sonnet-5"),
    )
    usages.append(result.usage)
    _log_llm_usage("claim_verify", CLAIM_VERIFY_VERSION, result, job_id_str)

    finalized = []
    for claim in result.value.claims:
        evidence_ref = evidence_by_id.get(claim.referenced_evidence_id or "")
        evidence_texts = (
            [f"{evidence_ref.title}. {evidence_ref.normalized_claim} {evidence_ref.description}"]
            if evidence_ref
            else None
        )
        status = finalize_claim_status(
            claim_type=claim.claim_type,
            asserted_value=claim.asserted_value,
            llm_status=claim.status,
            profile_fact_value=profile_facts_by_id.get(claim.referenced_profile_fact_id or ""),
            evidence_texts=evidence_texts,
        )
        finalized.append((claim, status, evidence_ref))
    return finalized, result


async def _generate_resume(
    provider, mode: TailoringMode, positioning, profile_facts, evidence_items, job_id_str: str, usages: list
) -> tuple[ResumeContentOutput, list[tuple]]:
    mode_instructions = CONSERVATIVE_INSTRUCTIONS if mode == TailoringMode.CONSERVATIVE else FULL_INSTRUCTIONS
    positioning_summary = (
        f"Identity: {positioning.target_identity}\nThemes: {', '.join(positioning.themes)}\n"
        f"Priority: {', '.join(positioning.project_priority)}\nAvoid: {', '.join(positioning.gaps_to_avoid)}"
    )

    writer_result = await provider.structured_generate(
        task="resume_write",
        messages=[
            Message(role="system", content=RESUME_WRITE_SYSTEM),
            Message(
                role="user",
                content=build_resume_write_message(
                    mode_instructions,
                    positioning_summary,
                    _format_profile_facts(profile_facts),
                    _format_evidence(evidence_items),
                ),
            ),
        ],
        schema=ResumeContentOutput,
        model_config=ModelConfig(model="claude-sonnet-5"),
    )
    usages.append(writer_result.usage)
    _log_llm_usage("resume_write", RESUME_WRITE_VERSION, writer_result, job_id_str)
    content = writer_result.value

    all_finalized: list[tuple] = []
    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        units = _flatten_bullets(content)
        finalized, _verify_result = await _run_claim_verification(
            provider, units, profile_facts, evidence_items, job_id_str, usages
        )
        all_finalized = finalized

        failed_locations = {
            _location_for_index(content, claim.bullet_index)
            for claim, status, _ in finalized
            if status in (ClaimVerificationStatus.UNSUPPORTED, ClaimVerificationStatus.CONTRADICTORY)
        }

        if not failed_locations or attempt == MAX_REPAIR_ATTEMPTS:
            content = _apply_removals(content, failed_locations)
            break

        failed_texts = "\n".join(
            f"- \"{claim.claim_text}\" ({status.value}: {claim.reason})"
            for claim, status, _ in finalized
            if status in (ClaimVerificationStatus.UNSUPPORTED, ClaimVerificationStatus.CONTRADICTORY)
        )
        writer_result = await provider.structured_generate(
            task="resume_write",
            messages=[
                Message(role="system", content=RESUME_WRITE_SYSTEM),
                Message(
                    role="user",
                    content=build_resume_write_message(
                        mode_instructions,
                        positioning_summary,
                        _format_profile_facts(profile_facts),
                        _format_evidence(evidence_items),
                    ),
                ),
                Message(role="assistant", content=content.model_dump_json()),
                Message(role="user", content=build_resume_repair_message(failed_texts)),
            ],
            schema=ResumeContentOutput,
            model_config=ModelConfig(model="claude-sonnet-5"),
        )
        usages.append(writer_result.usage)
        _log_llm_usage("resume_write", RESUME_WRITE_VERSION, writer_result, job_id_str)
        content = writer_result.value

    return content, all_finalized


async def _generate_cover_letter(
    provider, positioning, profile_facts, evidence_items, job_id_str: str, usages: list
) -> tuple[CoverLetterContentOutput, list[tuple]]:
    positioning_summary = (
        f"Identity: {positioning.target_identity}\nThemes: {', '.join(positioning.themes)}\n"
        f"Priority: {', '.join(positioning.project_priority)}\nAvoid: {', '.join(positioning.gaps_to_avoid)}"
    )

    writer_result = await provider.structured_generate(
        task="cover_letter_write",
        messages=[
            Message(role="system", content=COVER_LETTER_WRITE_SYSTEM),
            Message(
                role="user",
                content=build_cover_letter_write_message(
                    positioning_summary, _format_profile_facts(profile_facts), _format_evidence(evidence_items)
                ),
            ),
        ],
        schema=CoverLetterContentOutput,
        model_config=ModelConfig(model="claude-sonnet-5"),
    )
    usages.append(writer_result.usage)
    _log_llm_usage("cover_letter_write", COVER_LETTER_WRITE_VERSION, writer_result, job_id_str)
    content = writer_result.value

    all_finalized: list[tuple] = []
    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        units = _flatten_paragraphs(content)
        finalized, _verify_result = await _run_claim_verification(
            provider, units, profile_facts, evidence_items, job_id_str, usages
        )
        all_finalized = finalized

        failed_indices = {
            claim.bullet_index
            for claim, status, _ in finalized
            if status in (ClaimVerificationStatus.UNSUPPORTED, ClaimVerificationStatus.CONTRADICTORY)
        }

        if not failed_indices or attempt == MAX_REPAIR_ATTEMPTS:
            content = _apply_paragraph_removals(content, failed_indices)
            break

        failed_texts = "\n".join(
            f"- \"{claim.claim_text}\" ({status.value}: {claim.reason})"
            for claim, status, _ in finalized
            if status in (ClaimVerificationStatus.UNSUPPORTED, ClaimVerificationStatus.CONTRADICTORY)
        )
        writer_result = await provider.structured_generate(
            task="cover_letter_write",
            messages=[
                Message(role="system", content=COVER_LETTER_WRITE_SYSTEM),
                Message(
                    role="user",
                    content=build_cover_letter_write_message(
                        positioning_summary, _format_profile_facts(profile_facts), _format_evidence(evidence_items)
                    ),
                ),
                Message(role="assistant", content=content.model_dump_json()),
                Message(role="user", content=build_cover_letter_repair_message(failed_texts)),
            ],
            schema=CoverLetterContentOutput,
            model_config=ModelConfig(model="claude-sonnet-5"),
        )
        usages.append(writer_result.usage)
        _log_llm_usage("cover_letter_write", COVER_LETTER_WRITE_VERSION, writer_result, job_id_str)
        content = writer_result.value

    return content, all_finalized


async def _generate(job_id_str: str, mode_str: str, document_type_str: str) -> None:
    job_id = uuid.UUID(job_id_str)
    mode = TailoringMode(mode_str)
    document_type = DocumentType(document_type_str)
    provider = get_provider()

    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if job is None:
            logger.error("job_not_found", extra={"job_id": job_id_str})
            return

        generation_run = GenerationRun(
            user_id=job.user_id,
            job_id=job.id,
            pipeline_version=PIPELINE_VERSION,
            status=GenerationRunStatus.RUNNING,
        )
        session.add(generation_run)
        await session.commit()
        await publish_event(job_id_str, RunEventName.GENERATION_STARTED, {"generation_run_id": str(generation_run.id)})

        usages: list = []
        try:
            positioning, positioning_result = await compute_positioning(session, job)
            usages.append(positioning_result.usage)
            _log_llm_usage("position", "position:v1", positioning_result, job_id_str)

            profile_facts = list(
                await session.scalars(
                    select(ProfileFact).where(ProfileFact.user_id == job.user_id, ProfileFact.confirmed.is_(True))
                )
            )

            matches = list(
                await session.scalars(
                    select(EvidenceMatch)
                    .join(Requirement, Requirement.id == EvidenceMatch.requirement_id)
                    .where(Requirement.job_id == job_id, EvidenceMatch.status.in_(["strong", "partial"]))
                )
            )
            evidence_ids = {m.evidence_id for m in matches}
            evidence_items = [
                e for e in [await session.get(Evidence, eid) for eid in evidence_ids] if e is not None
            ]

            await publish_event(job_id_str, RunEventName.GENERATION_VERIFYING, {})

            if document_type == DocumentType.RESUME:
                content, finalized_claims = await _generate_resume(
                    provider, mode, positioning, profile_facts, evidence_items, job_id_str, usages
                )
                content_json = content.model_dump()
                prompt_versions = ["position:v1", RESUME_WRITE_VERSION, CLAIM_VERIFY_VERSION]
            else:
                content, finalized_claims = await _generate_cover_letter(
                    provider, positioning, profile_facts, evidence_items, job_id_str, usages
                )
                content_json = content.model_dump()
                prompt_versions = ["position:v1", COVER_LETTER_WRITE_VERSION, CLAIM_VERIFY_VERSION]

            document = GeneratedDocument(
                job_id=job.id,
                generation_run_id=generation_run.id,
                type=document_type,
                template_id="ats_minimal" if document_type == DocumentType.RESUME else "standard_cover_letter",
                content_json=content_json,
            )
            session.add(document)
            await session.flush()

            for claim, status, evidence_ref in finalized_claims:
                generated_claim = GeneratedClaim(
                    document_id=document.id,
                    claim_text=claim.claim_text,
                    claim_type=claim.claim_type,
                    verification_status=status,
                    confidence=1.0 if status == ClaimVerificationStatus.SUPPORTED else 0.0,
                )
                session.add(generated_claim)
                await session.flush()
                if evidence_ref is not None:
                    session.add(
                        ClaimEvidence(
                            claim_id=generated_claim.id,
                            evidence_id=evidence_ref.id,
                            support_score=1.0 if status == ClaimVerificationStatus.SUPPORTED else 0.0,
                            verifier_reason=claim.reason,
                        )
                    )

            generation_run.status = GenerationRunStatus.SUCCEEDED
            generation_run.prompt_versions = prompt_versions
            generation_run.token_usage = {
                "input_tokens": sum(u.input_tokens for u in usages),
                "output_tokens": sum(u.output_tokens for u in usages),
                "call_count": len(usages),
            }
            generation_run.latency_ms = sum(u.latency_ms for u in usages)
            generation_run.estimated_cost = sum(u.estimated_cost_usd for u in usages)
            await session.commit()

            await publish_event(
                job_id_str,
                RunEventName.GENERATION_COMPLETED,
                {"document_id": str(document.id), "generation_run_id": str(generation_run.id)},
            )

        except Exception:
            generation_run.status = GenerationRunStatus.FAILED
            await session.commit()
            logger.exception("generation_failed", extra={"job_id": job_id_str})
            await publish_event(job_id_str, RunEventName.GENERATION_FAILED, {"job_id": job_id_str})


@dramatiq.actor(max_retries=0, queue_name="ai", time_limit=600_000)
def generate_document(job_id: str, mode: str = "conservative", document_type: str = "resume") -> None:
    import asyncio

    asyncio.run(_generate(job_id, mode, document_type))
