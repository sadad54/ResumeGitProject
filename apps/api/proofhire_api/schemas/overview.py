from datetime import datetime

from pydantic import BaseModel


class GitHubStatus(BaseModel):
    connected: bool
    login: str | None = None
    connected_at: datetime | None = None
    last_sync_at: datetime | None = None


class RepositoryCounts(BaseModel):
    total: int
    selected: int
    synced: int


class EvidenceCounts(BaseModel):
    total: int
    confirmed: int
    candidate: int
    stale: int


class JobCounts(BaseModel):
    total: int
    ready: int


class DocumentCounts(BaseModel):
    total: int
    exported: int


class ApplicationCounts(BaseModel):
    total: int
    # applied / screen / interview / offer: still in play.
    active: int


class OverviewResponse(BaseModel):
    github: GitHubStatus
    repositories: RepositoryCounts
    evidence: EvidenceCounts
    jobs: JobCounts
    documents: DocumentCounts
    applications: ApplicationCounts
