import uuid
from datetime import datetime

from proofhire_contracts import RequirementCategory
from pydantic import BaseModel, Field, model_validator


class JobCreateRequest(BaseModel):
    source_text: str | None = None
    source_url: str | None = None

    @model_validator(mode="after")
    def require_text_or_url(self) -> "JobCreateRequest":
        if not self.source_text and not self.source_url:
            raise ValueError("Provide source_text or source_url")
        return self


class JobPublic(BaseModel):
    id: uuid.UUID
    source_url: str | None
    company: str | None
    role: str | None
    seniority: str | None
    location: str | None
    captured_at: datetime
    status: str

    model_config = {"from_attributes": True}


class RequirementPublic(BaseModel):
    id: uuid.UUID
    category: RequirementCategory
    text: str
    normalized: list[str]
    importance: float
    required: bool
    confidence: float

    model_config = {"from_attributes": True}


class AnalyzeResponse(BaseModel):
    job_id: uuid.UUID
    status: str = "queued"
