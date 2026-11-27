"""Typography from real model output survives export.

The second live end-to-end run failed at export: gpt-oss wrote U+2011
NON-BREAKING HYPHEN ("test‑driven"), Chromium drew it with the U+2010
glyph, the PDF's text layer returned U+2010, and parse-back's exact comparison
refused every such resume. These are the live run's own strings.
"""

import pytest

from proofhire_worker.intelligence.generation import _ats_safe
from proofhire_worker.intelligence.schemas import ProjectEntryOutput, ResumeContentOutput
from proofhire_worker.render.parse_back import validate_parse_back
from proofhire_worker.render.pdf_renderer import render_html_to_pdf
from proofhire_worker.render.templates import render_resume_html

LIVE_BULLETS = [
    "Developed unit tests covering schema validation, attribution screening, and retrieval "
    "utilities, demonstrating a test‑driven approach to pipeline reliability.",
    "Integrated the Groq LLM client to generate evaluation responses, with test patches "
    "confirming invocation of the client’s chat.completions.create method.",
    "Specified Python ≥ 3.11 environment setup with instructions for virtual environment "
    "creation and dependency installation.",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("template", ["ats_minimal", "technical_dense", "modern_editorial"])
async def test_non_breaking_hyphens_and_ligatures_pass_parse_back(template):
    content = {
        "summary": "Engineer who writes ﬁne-grained tests.",  # a literal fi ligature
        "skills": ["Python"],
        "experience": [],
        "projects": [{"name": "sadad54/SAFE-RAG", "bullets": LIVE_BULLETS}],
    }
    pdf = await render_html_to_pdf(render_resume_html(content, "a@b.com", template))
    ok, missing = validate_parse_back(pdf, LIVE_BULLETS + ["Engineer who writes fine-grained tests."])
    assert ok, missing


@pytest.mark.asyncio
async def test_parse_back_still_catches_genuinely_missing_text():
    content = {"summary": "s", "skills": [], "projects": [{"name": "r", "bullets": ["one‑two"]}]}
    pdf = await render_html_to_pdf(render_resume_html(content, "a@b.com"))
    ok, missing = validate_parse_back(pdf, ["one‑three"])
    assert not ok and missing == ["one‑three"]


def test_writer_output_is_made_ats_safe_before_verification():
    written = ResumeContentOutput(
        summary="Test‑driven engineer",
        skills=["sentence‑transformers"],
        projects=[ProjectEntryOutput(name="o/r", bullets=["CPU‑only pipeline"])],
    )
    safe = _ats_safe(written)
    assert safe.summary == "Test-driven engineer"
    assert safe.skills == ["sentence-transformers"]
    assert safe.projects[0].bullets == ["CPU-only pipeline"]
    # Curly quotes and mathematical signs are searchable as-is and stay.
    assert _ats_safe(ResumeContentOutput(summary="client’s ≥ 3.11")).summary == (
        "client’s ≥ 3.11"
    )
