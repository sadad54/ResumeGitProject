"""PDF rendering regression tests (checklist §16, §18).

These drive the real Chromium renderer rather than asserting on the HTML
string, because every property worth protecting here — page count, page
dimensions, whether text is selectable, whether content survives the render —
only exists after rasterization. A test that checked the HTML would pass
happily while the PDF came out broken.
"""

import io

import pytest
from pypdf import PdfReader

from proofhire_worker.render.parse_back import (
    count_pdf_pages,
    detect_overflow,
    extract_pdf_text,
    validate_parse_back,
)
from proofhire_worker.render.pdf_renderer import render_html_to_pdf
from proofhire_worker.render.templates import (
    TEMPLATE_STYLES,
    render_cover_letter_html,
    render_resume_html,
)

pytestmark = pytest.mark.asyncio

# Points, at 72pt/inch, as reported by the PDF page box.
LETTER_SIZE = (612, 792)
A4_SIZE = (595, 842)
SIZE_TOLERANCE = 2


def _resume_content(bullet_count: int = 3) -> dict:
    return {
        "summary": "Backend engineer focused on evidence-grounded systems.",
        "skills": ["Python", "PostgreSQL", "FastAPI"],
        "experience": [
            {
                "title": "Senior Engineer",
                "employer": "Acme Corp",
                "start_date": "2021",
                "end_date": "2024",
                "bullets": [f"Shipped measurable improvement number {i}." for i in range(bullet_count)],
            }
        ],
    }


def _page_size(pdf_bytes: bytes) -> tuple[float, float]:
    box = PdfReader(io.BytesIO(pdf_bytes)).pages[0].mediabox
    return (round(float(box.width)), round(float(box.height)))


async def test_letter_render_has_letter_page_dimensions():
    pdf = await render_html_to_pdf(render_resume_html(_resume_content(), "a@b.com"), "Letter")
    width, height = _page_size(pdf)
    assert abs(width - LETTER_SIZE[0]) <= SIZE_TOLERANCE
    assert abs(height - LETTER_SIZE[1]) <= SIZE_TOLERANCE


async def test_a4_render_has_a4_page_dimensions():
    pdf = await render_html_to_pdf(render_resume_html(_resume_content(), "a@b.com"), "A4")
    width, height = _page_size(pdf)
    assert abs(width - A4_SIZE[0]) <= SIZE_TOLERANCE
    assert abs(height - A4_SIZE[1]) <= SIZE_TOLERANCE


async def test_a4_and_letter_are_actually_different_renders():
    """Guards against the page-size argument being silently ignored, which
    would otherwise make the A4 assertion above pass for the wrong reason."""
    content = _resume_content()
    letter = _page_size(await render_html_to_pdf(render_resume_html(content, "a@b.com"), "Letter"))
    a4 = _page_size(await render_html_to_pdf(render_resume_html(content, "a@b.com"), "A4"))
    assert letter != a4


@pytest.mark.parametrize("template_id", sorted(TEMPLATE_STYLES))
async def test_every_template_renders_selectable_text_that_survives_parse_back(template_id):
    """Selectable (not rasterized) text is what makes a PDF ATS-readable, and
    parse-back is how we know the content actually made it through."""
    content = _resume_content()
    html = render_resume_html(content, "candidate@example.com", template_id)
    pdf = await render_html_to_pdf(html)

    extracted = extract_pdf_text(pdf)
    assert extracted.strip(), f"{template_id} produced no extractable text"

    ok, missing = validate_parse_back(
        pdf, ["Summary", "Skills", "Experience", content["summary"], "Acme Corp"]
    )
    assert ok, f"{template_id} lost content in rendering: {missing}"


async def test_short_resume_fits_on_a_single_page():
    pdf = await render_html_to_pdf(render_resume_html(_resume_content(3), "a@b.com"))
    overflowed, pages = detect_overflow(pdf, max_pages=1)
    assert not overflowed, f"a three-bullet resume should fit one page, got {pages}"


async def test_overflow_is_detected_rather_than_silently_exported():
    """The failure this guards against is a resume quietly becoming three pages
    long. Deliberately oversized input must be *reported* as overflowing."""
    pdf = await render_html_to_pdf(render_resume_html(_resume_content(160), "a@b.com"))
    overflowed, pages = detect_overflow(pdf, max_pages=1)
    assert overflowed
    assert pages > 1


async def test_job_entry_is_not_split_across_a_page_boundary():
    """Deterministic page breaking: with break-inside:avoid, a role's heading
    must not be stranded at the foot of a page away from its bullets."""
    content = {
        "summary": "Summary line.",
        "skills": ["Python"],
        # Enough entries to guarantee a page boundary falls inside the list.
        "experience": [
            {
                "title": f"Role {i}",
                "employer": f"Employer {i}",
                "start_date": "2020",
                "end_date": "2024",
                "bullets": [f"Entry {i} bullet {j} describing work done." for j in range(6)],
            }
            for i in range(9)
        ],
    }
    pdf = await render_html_to_pdf(render_resume_html(content, "a@b.com"))
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) > 1, "fixture should span multiple pages to be meaningful"

    for index, page in enumerate(reader.pages):
        text = " ".join((page.extract_text() or "").split())
        for i in range(9):
            header = f"Role {i} — Employer {i}"
            if header in text:
                # If a heading appears on a page, at least one of its bullets
                # must appear on that same page.
                assert any(
                    f"Entry {i} bullet {j}" in text for j in range(6)
                ), f"'{header}' was stranded without its bullets on page {index + 1}"


async def test_cover_letter_renders_its_paragraphs():
    content = {
        "body_paragraphs": [
            "I am writing about the backend engineering role.",
            "My evidence graph work is directly relevant.",
        ]
    }
    pdf = await render_html_to_pdf(render_cover_letter_html(content, "a@b.com"))
    assert count_pdf_pages(pdf) >= 1
    ok, missing = validate_parse_back(pdf, content["body_paragraphs"])
    assert ok, f"cover letter lost paragraphs: {missing}"
