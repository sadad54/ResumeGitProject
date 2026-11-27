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


GITHUB_ONLY_CONTENT = {
    "summary": "Engineer building LLM agents and retrieval systems.",
    "skills": ["Python", "FastAPI"],
    "experience": [],
    "projects": [
        {"name": "octo/planner", "bullets": ["Built a tool-calling agent that plans multi-step tasks."]},
        {"name": "octo/empty", "bullets": []},
    ],
}


def test_sections_follow_the_content():
    from proofhire_worker.render.templates import resume_sections

    assert resume_sections(SAMPLE_CONTENT) == ["Summary", "Skills", "Experience"]
    # A GitHub-only candidate: no empty Experience heading, and a project
    # with no bullets is not a section's worth of content.
    assert resume_sections(GITHUB_ONLY_CONTENT) == ["Summary", "Skills", "Projects"]
    assert resume_sections({"summary": "s", "skills": []}) == ["Summary", "Skills"]


@pytest.mark.asyncio
async def test_projects_render_and_parse_back():
    html = render_resume_html(GITHUB_ONLY_CONTENT, "jane@example.com")
    assert "<h2>Experience</h2>" not in html
    assert "octo/empty" not in html
    pdf_bytes = await render_html_to_pdf(html)
    success, missing = validate_parse_back(
        pdf_bytes,
        ["Projects", "octo/planner", "Built a tool-calling agent that plans multi-step tasks."],
    )
    assert success, f"unexpectedly missing: {missing}"
