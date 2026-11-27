import uuid

from proofhire_contracts import SyncStatus
from pydantic import BaseModel


class ConnectResponse(BaseModel):
    authorize_url: str


class RepositoryPublic(BaseModel):
    id: uuid.UUID
    owner: str
    name: str
    url: str
    visibility: str
    default_branch: str
    language_summary: dict
    stars: int
    selected: bool
    last_commit_sha: str | None
    last_analyzed_sha: str | None
    sync_status: SyncStatus

    model_config = {"from_attributes": True}


class RepositoryPatch(BaseModel):
    selected: bool


class SyncTriggerRequest(BaseModel):
    repository_ids: list[uuid.UUID]


class SyncTriggerResponse(BaseModel):
    run_id: uuid.UUID
    status: SyncStatus
    # Stream position before this work was queued: pass it as `after` to
    # GET /api/v1/events/runs/{id} to receive every event of this run and
    # none from earlier ones (routers/events.py).
    events_after: str = "0-0"


class SyncStatusResponse(BaseModel):
    run_id: uuid.UUID
    status: SyncStatus
    repository_ids: list[str]
    error: str | None
