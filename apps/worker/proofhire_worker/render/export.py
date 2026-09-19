"""Document export: template -> PDF render -> parse-back validation -> storage
(PRD §21). Synchronous within the API request, same rationale as resume
upload (Phase 5) — one bounded render/validate cycle, not a multi-stage
pipeline that benefits from queueing.
"""

from proofhire_api.models.generated_claim import GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.telemetry import traced_stage
from proofhire_contracts import ClaimVerificationStatus, DocumentType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_worker.render.parse_back import (
    count_pdf_pages,
    extract_pdf_text,
    validate_parse_back,
)
from proofhire_worker.render.pdf_renderer import DEFAULT_PAGE_SIZE, PageSize, render_html_to_pdf
from proofhire_worker.render.storage import save_bytes
from proofhire_worker.render.templates import render_cover_letter_html, render_resume_html

RESUME_REQUIRED_SECTIONS = ["Summary", "Skills", "Experience"]


class ParseBackValidationError(Exception):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Parse-back validation failed — missing: {missing}")


@traced_stage("document_export")
async def export_document(
    session: AsyncSession,
    document: GeneratedDocument,
    contact_email: str,
    template_id: str | None = None,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> GeneratedDocument:
    chosen_template = (
        (template_id or document.template_id)
        if document.type == DocumentType.RESUME
        else document.template_id
    )
    if document.type == DocumentType.RESUME:
        html_content = render_resume_html(document.content_json, contact_email, chosen_template)
        required_texts = list(RESUME_REQUIRED_SECTIONS)
    else:
        html_content = render_cover_letter_html(document.content_json, contact_email)
        required_texts = []

    supported_claims = list(
        await session.scalars(
            select(GeneratedClaim).where(
                GeneratedClaim.document_id == document.id,
                GeneratedClaim.verification_status == ClaimVerificationStatus.SUPPORTED,
            )
        )
    )
    required_texts += [c.claim_text for c in supported_claims]

    pdf_bytes = await render_html_to_pdf(html_content, page_size)

    success, missing = validate_parse_back(pdf_bytes, required_texts)
    if not success:
        # Fail closed: an export that can't be verified to contain what it
        # was supposed to contain is not returned to the user (PRD §21).
        raise ParseBackValidationError(missing)

    # Overflow is recorded rather than raised: unlike missing content, a
    # multi-page resume is a legitimate document the user may well want. They
    # just need to be told, so the UI can surface it instead of shipping a
    # silently-three-page resume.
    document.page_count = count_pdf_pages(pdf_bytes)

    plaintext = extract_pdf_text(pdf_bytes)

    document.template_id = chosen_template
    document.html_ref = save_bytes("html", "html", html_content)
    document.pdf_ref = save_bytes("pdf", "pdf", pdf_bytes)
    document.plaintext_ref = save_bytes("plaintext", "txt", plaintext)

    await session.commit()
    await session.refresh(document)
    return document
