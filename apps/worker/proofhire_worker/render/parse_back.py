"""Parse-back validation (PRD §21, ADR-0009): confirms the rendered PDF's
actual extracted text contains the content it was supposed to contain, so a
rendering bug (overflow, encoding corruption, a layout change silently
dropping a section) can't silently produce a broken export.
"""

import io

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def validate_parse_back(pdf_bytes: bytes, required_texts: list[str]) -> tuple[bool, list[str]]:
    """Returns (success, missing_texts). required_texts should be every
    section header and every SUPPORTED claim's text — content that must
    survive rendering intact for the export to be trustworthy."""
    extracted = _normalize(extract_pdf_text(pdf_bytes))
    missing = [text for text in required_texts if _normalize(text) not in extracted]
    return (len(missing) == 0, missing)
