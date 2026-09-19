"""Live-preview endpoint (checklist §10.7). Calls the route function directly
against the real DB, like the coverage-endpoint test."""

import uuid

import pytest
from fastapi import HTTPException
from proofhire_contracts import DocumentType, GenerationRunStatus

from proofhire_api.db import async_session_factory
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.user import User
from proofhire_api.routers.generation import preview_document_html
from proofhire_api.security.password import hash_password

CONTENT = {
    "summary": "Backend engineer with an unusual marker: ZQX-PREVIEW-42.",
    "skills": ["Python"],
    "experience": [
        {"title": "Engineer", "employer": "Acme", "start_date": "2021", "end_date": "2024",
         "bullets": ["Shipped the <thing> & measured it."]}
    ],
}


@pytest.fixture
async def env():
    async with async_session_factory() as session:
        user = User(email=f"preview-{uuid.uuid4().hex[:8]}@example.com",
                    hashed_password=hash_password("x"))
        session.add(user)
        await session.flush()
        job = Job(user_id=user.id, source_text="jd")
        session.add(job)
        await session.flush()
        run = GenerationRun(user_id=user.id, job_id=job.id, pipeline_version="test",
                            status=GenerationRunStatus.SUCCEEDED)
        session.add(run)
        await session.flush()
        doc = GeneratedDocument(job_id=job.id, generation_run_id=run.id, type=DocumentType.RESUME,
                                content_json=CONTENT)
        session.add(doc)
        await session.commit()

        other = User(email=f"preview-other-{uuid.uuid4().hex[:8]}@example.com",
                     hashed_password=hash_password("x"))
        session.add(other)
        await session.commit()

        yield session, user, other, doc

        await session.delete(await session.get(User, user.id))
        await session.delete(await session.get(User, other.id))
        await session.commit()


async def test_preview_renders_the_document_with_the_requested_template(env):
    session, user, _other, doc = env

    response = await preview_document_html(doc.id, "modern_editorial", user, session)

    body = response.body.decode()
    assert "ZQX-PREVIEW-42" in body
    assert "#165b61" in body  # modern_editorial's accent colour, proving the template applied
    assert "&lt;thing&gt; &amp;" in body  # content is escaped, not injected


async def test_preview_sets_a_no_script_csp(env):
    session, user, _other, doc = env
    response = await preview_document_html(doc.id, None, user, session)
    assert response.headers["content-security-policy"].startswith("default-src 'none'")


async def test_preview_is_ownership_scoped(env):
    session, _user, other, doc = env
    with pytest.raises(HTTPException) as exc:
        await preview_document_html(doc.id, None, other, session)
    assert exc.value.status_code == 404
