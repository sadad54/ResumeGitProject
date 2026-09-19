"""Canonical enums shared across ProofHire's API, worker, and (via codegen) web app.

This is the single source of truth for these value sets (PRD §24 "Shared Contracts").
Changing a member here is a breaking contract change and requires an ADR per the
Contract Freeze Rule (PRD §35).
"""

from enum import StrEnum


class EvidenceStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    PRIVATE = "private"
    STALE = "stale"


class EvidenceType(StrEnum):
    SKILL_USAGE = "skill_usage"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    INTEGRATION = "integration"
    DEPLOYMENT = "deployment"
    TESTING = "testing"
    ML_MODEL = "ml_model"
    DATA_PIPELINE = "data_pipeline"
    PERFORMANCE_METRIC = "performance_metric"
    OWNERSHIP = "ownership"
    CONTRIBUTION = "contribution"
    FEATURE = "feature"


class SourceArtifactType(StrEnum):
    README = "readme"
    SOURCE_FILE = "source_file"
    DEPENDENCY_MANIFEST = "dependency_manifest"
    CI_CONFIG = "ci_config"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    TERRAFORM = "terraform"
    NOTEBOOK = "notebook"
    BENCHMARK = "benchmark"
    TEST = "test"
    DOCS = "docs"
    COMMIT_METADATA = "commit_metadata"


class ArtifactPriority(StrEnum):
    P0 = "p0"  # README, manifests, Dockerfiles, CI, K8s, Terraform, ML configs, benchmarks
    P1 = "p1"  # entry points, service boundaries, API defs, model/training/eval code, schemas
    P2 = "p2"  # representative implementation files
    P3 = "p3"  # low-information/generated/vendor — excluded from semantic extraction


class ProfileFactType(StrEnum):
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    AWARD = "award"
    CERTIFICATION = "certification"
    CONTACT = "contact"
    SUMMARY_FACT = "summary_fact"


class RequirementCategory(StrEnum):
    SKILL = "skill"
    EXPERIENCE = "experience"
    RESPONSIBILITY = "responsibility"
    DOMAIN = "domain"
    EDUCATION = "education"
    TOOLING = "tooling"
    SOFT_SKILL = "soft_skill"
    SENIORITY = "seniority"


class MatchLabel(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    GAP = "gap"
    UNKNOWN = "unknown"


class ApplicationStage(StrEnum):
    SAVED = "saved"
    ANALYZING = "analyzing"
    READY = "ready"
    APPLIED = "applied"
    SCREEN = "screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class DocumentType(StrEnum):
    RESUME = "resume"
    COVER_LETTER = "cover_letter"


class TailoringMode(StrEnum):
    CONSERVATIVE = "conservative"
    FULL = "full"


class ClaimVerificationStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTORY = "contradictory"


class GenerationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncStatus(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


class RunEventName(StrEnum):
    GITHUB_SYNC_STARTED = "github.sync.started"
    GITHUB_REPO_ANALYZING = "github.repo.analyzing"
    GITHUB_REPO_COMPLETED = "github.repo.completed"
    EVIDENCE_CREATED = "evidence.created"
    JOB_CAPTURED = "job.captured"
    JOB_ANALYSIS_STARTED = "job.analysis.started"
    JOB_ANALYSIS_COMPLETED = "job.analysis.completed"
    GENERATION_STARTED = "generation.started"
    GENERATION_VERIFYING = "generation.verifying"
    GENERATION_RENDERING = "generation.rendering"
    GENERATION_COMPLETED = "generation.completed"
    GENERATION_FAILED = "generation.failed"
