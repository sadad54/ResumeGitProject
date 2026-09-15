"""Resume file -> raw text extraction (PRD §13 ProfileFact upload). Supports
PDF and DOCX only for V1 — matches the two formats PRD §8.1 lists ("Optional
PDF/DOCX resume upload")."""

import io

from docx import Document
from pypdf import PdfReader


class ResumeParseError(Exception):
    pass


def _extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text_from_docx(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def extract_resume_text(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _extract_text_from_pdf(data)
    elif lower.endswith(".docx"):
        text = _extract_text_from_docx(data)
    else:
        raise ResumeParseError("Unsupported file type — upload a .pdf or .docx resume")

    text = text.strip()
    if len(text) < 50:
        raise ResumeParseError(
            "Could not extract meaningful text from this file — it may be a "
            "scanned image without a text layer, which V1 doesn't OCR."
        )
    return text
