import uuid
from datetime import datetime

from proofhire_contracts import ClaimVerificationStatus, DocumentType, GenerationRunStatus, TailoringMode
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
    html_ref: str | None = None
    pdf_ref: str | None = None
    plaintext_ref: str | None = None

    model_config = {"from_attributes": True}


class ExportResponse(BaseModel):
    document_id: uuid.UUID
    pdf_available: bool


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
