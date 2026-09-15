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


class RequirementOutput(BaseModel):
    text: str = Field(description="Original wording from the JD, unparaphrased")
    category: str = Field(
        description="One of: skill, experience, responsibility, domain, education, tooling, soft_skill, seniority"
    )
    required: bool = Field(description="True if must-have, False if preferred/nice-to-have")
    importance: float = Field(ge=0.0, le=1.0)
    normalized: list[str] = Field(default_factory=list, description="Lowercase canonical keywords")


class JDAnalysisOutput(BaseModel):
    role: str = ""
    company: str = ""
    seniority: str = ""
    requirements: list[RequirementOutput] = Field(default_factory=list)


class RerankOutput(BaseModel):
    best_evidence_index: int | None = Field(
        description="Index of the best-supporting candidate, or null if none adequately support the requirement"
    )
    label: str = Field(description="One of: strong, partial, gap, unknown")
    directness: float = Field(ge=0.0, le=1.0)
    depth: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    source_quality: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class EmploymentFactOutput(BaseModel):
    employer: str
    title: str
    start_date: str = Field(description="As written in the resume, e.g. '2020' or 'Jan 2020'")
    end_date: str = Field(description="As written in the resume, or 'Present'")


class EducationFactOutput(BaseModel):
    institution: str
    degree: str
    field: str = ""
    start_date: str = ""
    end_date: str = ""


class CredentialFactOutput(BaseModel):
    name: str
    issuer: str = ""
    date: str = ""


class ResumeExtractionOutput(BaseModel):
    employment: list[EmploymentFactOutput] = Field(default_factory=list)
    education: list[EducationFactOutput] = Field(default_factory=list)
    certifications: list[CredentialFactOutput] = Field(default_factory=list)
    awards: list[CredentialFactOutput] = Field(default_factory=list)


class PositioningOutput(BaseModel):
    target_identity: str = Field(description="One-sentence professional identity framing for this role")
    themes: list[str] = Field(default_factory=list, description="3-5 strongest positioning themes")
    project_priority: list[str] = Field(default_factory=list, description="Evidence titles, most relevant first")
    skills_priority: list[str] = Field(default_factory=list)
    gaps_to_avoid: list[str] = Field(
        default_factory=list, description="Requirements with weak/no evidence — do not overstate these"
    )


class ExperienceEntryOutput(BaseModel):
    employer: str
    title: str
    start_date: str
    end_date: str
    bullets: list[str] = Field(default_factory=list)


class ResumeContentOutput(BaseModel):
    summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntryOutput] = Field(default_factory=list)


class CoverLetterContentOutput(BaseModel):
    body_paragraphs: list[str] = Field(default_factory=list)


class ClaimOutput(BaseModel):
    """One call (prompt claim_verify:v1) both decomposes the document into
    atomic claims AND semantically judges each one (PRD §19.3's four steps are
    one stage, not two prompts). For employment/education/certification/award/
    metric claims, `status`/`reason` are advisory only — the deterministic fact
    guard's exact-match check is authoritative and overrides them.

    Verification runs at bullet granularity (V1 simplification, documented):
    each input bullet/summary line is one claim-checkable unit rather than
    further-decomposed sub-sentence propositions, so a failed claim maps back
    to exactly one removable unit with no ambiguous partial-bullet editing.
    """

    bullet_index: int = Field(description="Index into the bullets list this claim was extracted from")
    claim_text: str = Field(description="The atomic factual claim, as it appears in the document")
    claim_type: str = Field(
        description="One of: employment, education, certification, award, metric, skill, other"
    )
    asserted_value: str = Field(
        default="",
        description="For employment/education/certification/award/metric claims: the exact value being "
        "asserted (e.g. employer name, date, percentage). Empty for skill/other claims.",
    )
    referenced_profile_fact_id: str | None = None
    referenced_evidence_id: str | None = None
    status: str = Field(description="One of: supported, partially_supported, unsupported, contradictory")
    reason: str = ""


class ClaimVerificationOutput(BaseModel):
    claims: list[ClaimOutput] = Field(default_factory=list)
