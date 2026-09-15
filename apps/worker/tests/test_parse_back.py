import pytest

from proofhire_worker.render.parse_back import validate_parse_back
from proofhire_worker.render.pdf_renderer import render_html_to_pdf
from proofhire_worker.render.templates import render_resume_html

SAMPLE_CONTENT = {
    "summary": "Backend engineer with a track record of measurable performance improvements.",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "experience": [
        {
            "employer": "Google",
            "title": "SWE",
            "start_date": "2020",
            "end_date": "2022",
            "bullets": ["Improved throughput by 30% via caching."],
        }
    ],
}


@pytest.mark.asyncio
async def test_rendered_resume_passes_parse_back_for_real_content():
    html = render_resume_html(SAMPLE_CONTENT, "jane@example.com")
    pdf_bytes = await render_html_to_pdf(html)

    required = [
        "Summary",
        "Skills",
        "Experience",
        "Backend engineer with a track record of measurable performance improvements.",
        "Improved throughput by 30% via caching.",
        "jane@example.com",
    ]
    success, missing = validate_parse_back(pdf_bytes, required)
    assert success, f"unexpectedly missing: {missing}"


@pytest.mark.asyncio
async def test_parse_back_correctly_flags_content_that_was_never_rendered():
    """A negative control — proves the validator would actually catch a
    rendering bug, not just always pass."""
    html = render_resume_html(SAMPLE_CONTENT, "jane@example.com")
    pdf_bytes = await render_html_to_pdf(html)

    success, missing = validate_parse_back(
        pdf_bytes, ["This sentence was never in the content and must be flagged missing."]
    )
    assert success is False
    assert len(missing) == 1
