"""Read-only graph contract. IDs are namespaced; no graph tables are stored."""

from typing import Literal

from proofhire_contracts import MatchLabel
from pydantic import BaseModel, Field


class GraphSource(BaseModel):
    locator: str
    url: str
    commit_sha: str
    line_start: int | None = None
    line_end: int | None = None


class GraphNode(BaseModel):
    id: str
    kind: Literal["project", "skill", "architecture", "evidence", "requirement"]
    label: str
    description: str = ""
    status: str | None = None
    confidence: float | None = None
    repository_id: str | None = None
    evidence_id: str | None = None
    required: bool | None = None
    sources: list[GraphSource] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: Literal["contains", "demonstrates", "matches"]
    weight: float = Field(ge=0, le=1)
    status: MatchLabel | None = None
    explanation: str = ""


class EvidenceGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    job_id: str | None = None
    job_status: str | None = None
    truncated: bool = False
    evidence_limit: int
