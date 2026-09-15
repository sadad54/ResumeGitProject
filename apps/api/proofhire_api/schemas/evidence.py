import uuid
from datetime import datetime

from proofhire_contracts import EvidenceStatus, EvidenceType
from pydantic import BaseModel


class EvidenceSourcePublic(BaseModel):
    id: uuid.UUID
    source_artifact_id: uuid.UUID
    locator: str
    line_start: int | None
    line_end: int | None
    commit_sha: str
    relevance: float

    model_config = {"from_attributes": True}


class EvidencePublic(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    evidence_type: EvidenceType
    title: str
    normalized_claim: str
    description: str
    confidence: float
    extraction_method: str
    status: EvidenceStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceDetail(EvidencePublic):
    sources: list[EvidenceSourcePublic]
    skills: list[str]


class EvidencePatch(BaseModel):
    status: EvidenceStatus


class EvidenceSearchRequest(BaseModel):
    text: str
    limit: int = 10


class EvidenceSearchHit(BaseModel):
    id: uuid.UUID
    title: str
    normalized_claim: str
    evidence_type: EvidenceType
    confidence: float
    score: float
