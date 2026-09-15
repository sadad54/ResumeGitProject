import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from proofhire_contracts import ProfileFactType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.profile_fact import ProfileFact
from proofhire_api.models.user import User
from proofhire_api.schemas.profile import ProfileFactPatch, ProfileFactPublic
from proofhire_api.services.resume_parse import ResumeParseError, extract_resume_text
from proofhire_prompts.resume_extract_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
from proofhire_worker.intelligence.provider_factory import get_provider
from proofhire_worker.intelligence.schemas import ResumeExtractionOutput

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


@router.post("/resume", response_model=list[ProfileFactPublic], status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProfileFact]:
    """Synchronous (not queued): a single resume is one bounded LLM call, unlike
    repository ingestion or JD analysis which can involve many files/requirements.
    Immediate feedback is worth more here than the async/SSE pattern used
    elsewhere in the pipeline."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Resume file too large (max 10MB)")

    try:
        resume_text = extract_resume_text(file.filename or "", data)
    except ResumeParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    provider = get_provider()
    result = await provider.structured_generate(
        task="resume_extract",
        messages=[
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=build_user_message(resume_text)),
        ],
        schema=ResumeExtractionOutput,
        model_config=ModelConfig(model="claude-sonnet-5"),
    )

    output = result.value
    facts: list[ProfileFact] = []

    for job in output.employment:
        facts.append(
            ProfileFact(
                user_id=current_user.id,
                type=ProfileFactType.EMPLOYMENT,
                value_json=job.model_dump(),
                source="resume_upload",
                immutable=True,
                confirmed=False,
            )
        )
    for edu in output.education:
        facts.append(
            ProfileFact(
                user_id=current_user.id,
                type=ProfileFactType.EDUCATION,
                value_json=edu.model_dump(),
                source="resume_upload",
                immutable=True,
                confirmed=False,
            )
        )
    for cert in output.certifications:
        facts.append(
            ProfileFact(
                user_id=current_user.id,
                type=ProfileFactType.CERTIFICATION,
                value_json=cert.model_dump(),
                source="resume_upload",
                immutable=True,
                confirmed=False,
            )
        )
    for award in output.awards:
        facts.append(
            ProfileFact(
                user_id=current_user.id,
                type=ProfileFactType.AWARD,
                value_json=award.model_dump(),
                source="resume_upload",
                immutable=True,
                confirmed=False,
            )
        )

    db.add_all(facts)
    await db.commit()
    for fact in facts:
        await db.refresh(fact)

    return facts


@router.get("/facts", response_model=list[ProfileFactPublic])
async def list_profile_facts(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ProfileFact]:
    result = await db.scalars(select(ProfileFact).where(ProfileFact.user_id == current_user.id))
    return list(result.all())


@router.patch("/facts/{fact_id}", response_model=ProfileFactPublic)
async def patch_profile_fact(
    fact_id: uuid.UUID,
    body: ProfileFactPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileFact:
    """A user can correct a misextracted value before confirming it — the fact
    guard only ever checks against *confirmed* data going forward (Phase 5
    generation reads confirmed=True facts), so an unconfirmed fact with a typo
    is safe to fix here rather than re-uploading the whole resume."""
    fact = await db.get(ProfileFact, fact_id)
    if fact is None or fact.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile fact not found")

    if body.confirmed is not None:
        fact.confirmed = body.confirmed
    if body.value_json is not None:
        fact.value_json = body.value_json

    await db.commit()
    await db.refresh(fact)
    return fact
