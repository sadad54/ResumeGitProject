import uuid

import pytest
from fastapi import HTTPException

from proofhire_api.models.user import User
from proofhire_api.models.job import Job
from proofhire_api.routers.events import stream_run_events
from proofhire_worker.render.templates import render_resume_html
from proofhire_worker.render.pdf_renderer import render_html_to_pdf
from proofhire_worker.render.parse_back import validate_parse_back


@pytest.mark.asyncio
@pytest.mark.parametrize("template", ["ats_minimal", "technical_dense", "modern_editorial"])
async def test_templates_preserve_sections_and_claims(template):
    content = {"summary": "Engineer building reliable APIs.", "skills": ["Python", "SQL"], "experience": [{"employer": "Fixture & Co", "title": "Engineer", "start_date": "2023", "end_date": "2025", "bullets": ["Built APIs with Python.", "Reduced latency by 30%."]}]}
    markup = render_resume_html(content, "fixture@example.com", template)
    pdf = await render_html_to_pdf(markup)
    passed, missing = validate_parse_back(pdf, ["Summary", "Skills", "Experience", "Fixture & Co", "2023", "2025", *content["experience"][0]["bullets"]])
    assert passed, missing


@pytest.mark.asyncio
async def test_progress_stream_requires_run_ownership(db):
    owner = User(id=uuid.uuid4(), email="owner@example.com", hashed_password="unused")
    stranger = User(id=uuid.uuid4(), email="stranger@example.com", hashed_password="unused")
    db.add_all([owner, stranger]); await db.flush()
    job = Job(user_id=owner.id, source_text="fixture")
    db.add(job); await db.commit()
    with pytest.raises(HTTPException) as exc:
        await stream_run_events(job.id, current_user=stranger, db=db)
    assert exc.value.status_code == 404
    # Constructing the response performs no Redis IO until the stream is consumed.
    response = await stream_run_events(job.id, current_user=owner, db=db)
    assert response.media_type == "text/event-stream"
