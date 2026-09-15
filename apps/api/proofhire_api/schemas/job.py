import uuid
from datetime import datetime

from proofhire_contracts import MatchLabel, RequirementCategory
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


_ACTION_BY_LABEL: dict[MatchLabel, str] = {
    MatchLabel.STRONG: "Include in resume",
    MatchLabel.PARTIAL: "Review before including — evidence is related but not conclusive",
    MatchLabel.GAP: "No supporting evidence — do not claim this",
    MatchLabel.UNKNOWN: "Sync more repositories or review manually",
}


class CoverageRow(BaseModel):
    requirement_id: uuid.UUID
    requirement_text: str
    category: RequirementCategory
    required: bool
    importance: float
    match_label: MatchLabel
    evidence_id: uuid.UUID | None
    evidence_title: str | None
    evidence_repository: str | None
    confidence: float | None
    explanation: str
    action: str

    @classmethod
    def build(
        cls,
        *,
        requirement_id: uuid.UUID,
        requirement_text: str,
        category: RequirementCategory,
        required: bool,
        importance: float,
        match_label: MatchLabel,
        evidence_id: uuid.UUID | None,
        evidence_title: str | None,
        evidence_repository: str | None,
        confidence: float | None,
        explanation: str,
    ) -> "CoverageRow":
        return cls(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            category=category,
            required=required,
            importance=importance,
            match_label=match_label,
            evidence_id=evidence_id,
            evidence_title=evidence_title,
            evidence_repository=evidence_repository,
            confidence=confidence,
            explanation=explanation,
            action=_ACTION_BY_LABEL[match_label],
        )
