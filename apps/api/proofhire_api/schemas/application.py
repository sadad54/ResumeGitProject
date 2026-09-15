import uuid
from datetime import datetime

from proofhire_contracts import ApplicationStage
from pydantic import BaseModel


class ApplicationCreateRequest(BaseModel):
    job_id: uuid.UUID


class ApplicationPatch(BaseModel):
    stage: ApplicationStage


class ApplicationPublic(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    stage: ApplicationStage
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
