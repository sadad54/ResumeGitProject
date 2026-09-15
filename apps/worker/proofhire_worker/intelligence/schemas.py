"""Pydantic schemas for LLM structured outputs (PRD §25: "all AI outputs validated
by Pydantic schemas"). These are the `schema` argument to
LLMProvider.structured_generate — never a raw dict.
"""

from pydantic import BaseModel, Field


class EvidenceItemOutput(BaseModel):
    evidence_type: str = Field(
        description=(
            "One of: skill_usage, architecture, implementation, integration, "
            "deployment, testing, ml_model, data_pipeline, performance_metric, "
            "ownership, contribution, feature"
        )
    )
    title: str = Field(description="Short human-readable title, e.g. 'Async FastAPI backend'")
    normalized_claim: str = Field(
        description="One-sentence factual claim this evidence supports, stated plainly"
    )
    description: str = Field(description="1-3 sentences of supporting detail")
    confidence: float = Field(ge=0.0, le=1.0, description="Semantic extraction confidence")
    source_paths: list[str] = Field(
        description="File paths (from the provided list) this evidence is drawn from"
    )
    skills: list[str] = Field(default_factory=list, description="Skill/technology names this demonstrates")


class EvidenceExtractionOutput(BaseModel):
    evidence: list[EvidenceItemOutput] = Field(default_factory=list)
