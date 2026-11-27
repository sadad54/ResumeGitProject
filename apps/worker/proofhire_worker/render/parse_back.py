"""Parse-back validation (PRD §21, ADR-0009): confirms the rendered PDF's
actual extracted text contains the content it was supposed to contain, so a
rendering bug (overflow, encoding corruption, a layout change silently
dropping a section) can't silently produce a broken export.
"""

import io
import unicodedata

from pypdf import PdfReader


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def count_pdf_pages(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


def detect_overflow(pdf_bytes: bytes, max_pages: int) -> tuple[bool, int]:
    """Returns (overflowed, actual_page_count).

    Overflow is a real export defect rather than a cosmetic one: a resume that
    spills a single orphaned line onto page two reads as careless, and many ATS
    parsers weight first-page content differently.
    """
    pages = count_pdf_pages(pdf_bytes)
    return (pages > max_pages, pages)


# Every dash-like character compares as "-". Chromium draws U+2011
# NON-BREAKING HYPHEN with the U+2010 glyph and the PDF's text layer returns
# U+2010, so an exact comparison failed every export whose text contained one;
# gpt-oss writes them routinely (found by the second live end-to-end run).
_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")


def _normalize(text: str) -> str:
    """Text as a reader sees it: NFKC (ligatures, compatibility forms), dashes
    unified, whitespace collapsed, case folded. The check is for missing or
    garbled content, not for which of two identical-looking glyphs was used."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES)
    return " ".join(text.split()).casefold()


def validate_parse_back(pdf_bytes: bytes, required_texts: list[str]) -> tuple[bool, list[str]]:
    """Returns (success, missing_texts). required_texts should be every
    section header and every SUPPORTED claim's text — content that must
    survive rendering intact for the export to be trustworthy."""
    extracted = _normalize(extract_pdf_text(pdf_bytes))
    missing = [text for text in required_texts if _normalize(text) not in extracted]
    return (len(missing) == 0, missing)
