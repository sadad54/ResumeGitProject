import uuid
from datetime import datetime

from proofhire_contracts import (
    ClaimVerificationStatus,
    DocumentType,
    GenerationRunStatus,
    TailoringMode,
)
from pydantic import BaseModel


class PositioningResponse(BaseModel):
    target_identity: str
    themes: list[str]
    project_priority: list[str]
    skills_priority: list[str]
    gaps_to_avoid: list[str]


class GenerateRequest(BaseModel):
    mode: TailoringMode = TailoringMode.CONSERVATIVE
    document_type: DocumentType = DocumentType.RESUME


class GenerateResponse(BaseModel):
    generation_run_id: uuid.UUID | None = None
    status: str = "queued"
    # Stream position before this work was queued: pass it as `after` to
    # GET /api/v1/events/runs/{id} to receive every event of this run and
    # none from earlier ones (routers/events.py).
    events_after: str = "0-0"


class GenerationRunPublic(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    pipeline_version: str
    status: GenerationRunStatus
    prompt_versions: list[str]
    token_usage: dict
    latency_ms: float
    estimated_cost: float
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedDocumentPublic(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    generation_run_id: uuid.UUID
    type: DocumentType
    template_id: str
    version: int
    content_json: dict
    # Availability, not storage keys: where an export lives is the server's
    # business (see services/object_storage.py). Download via /download.
    pdf_available: bool = False
    plaintext_available: bool = False
    page_count: int | None = None
    created_at: datetime
    exported_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExportResponse(BaseModel):
    document_id: uuid.UUID
    pdf_available: bool
    page_count: int | None = None
    overflowed: bool = False


class DownloadLink(BaseModel):
    """A short-lived signed URL the browser navigates to directly. Carries no
    bearer token, so it can be a plain link; it stops working at expires_at."""

    url: str
    filename: str
    expires_at: int


class GeneratedClaimPublic(BaseModel):
    id: uuid.UUID
    claim_text: str
    claim_type: str
    verification_status: ClaimVerificationStatus
    confidence: float
    evidence_id: uuid.UUID | None = None
    evidence_title: str | None = None
    evidence_repository: str | None = None
    source_locator: str | None = None
