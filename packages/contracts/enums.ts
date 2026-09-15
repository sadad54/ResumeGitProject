/**
 * Canonical enums shared across ProofHire's API, worker, and web app.
 *
 * This file must stay in sync with `packages/contracts/enums.py` (the Python source
 * of truth). Once the FastAPI OpenAPI schema exists (Phase 0/1), this file should be
 * regenerated from it rather than hand-maintained (PRD §24, §35 "Frontend" rule:
 * "Agent 3 never hand-builds backend types. Generate from OpenAPI.").
 *
 * Hand-maintained only until codegen is wired up.
 */

export enum EvidenceStatus {
  Candidate = "candidate",
  Confirmed = "confirmed",
  Rejected = "rejected",
  Private = "private",
  Stale = "stale",
}

export enum EvidenceType {
  SkillUsage = "skill_usage",
  Architecture = "architecture",
  Implementation = "implementation",
  Integration = "integration",
  Deployment = "deployment",
  Testing = "testing",
  MlModel = "ml_model",
  DataPipeline = "data_pipeline",
  PerformanceMetric = "performance_metric",
  Ownership = "ownership",
  Contribution = "contribution",
  Feature = "feature",
}

export enum SourceArtifactType {
  Readme = "readme",
  SourceFile = "source_file",
  DependencyManifest = "dependency_manifest",
  CiConfig = "ci_config",
  Docker = "docker",
  Kubernetes = "kubernetes",
  Terraform = "terraform",
  Notebook = "notebook",
  Benchmark = "benchmark",
  Test = "test",
  Docs = "docs",
  CommitMetadata = "commit_metadata",
}

export enum ArtifactPriority {
  P0 = "p0",
  P1 = "p1",
  P2 = "p2",
  P3 = "p3",
}

export enum ProfileFactType {
  Employment = "employment",
  Education = "education",
  Award = "award",
  Certification = "certification",
  Contact = "contact",
  SummaryFact = "summary_fact",
}

export enum RequirementCategory {
  Skill = "skill",
  Experience = "experience",
  Responsibility = "responsibility",
  Domain = "domain",
  Education = "education",
  Tooling = "tooling",
  SoftSkill = "soft_skill",
  Seniority = "seniority",
}

export enum MatchLabel {
  Strong = "strong",
  Partial = "partial",
  Gap = "gap",
  Unknown = "unknown",
}

export enum ApplicationStage {
  Saved = "saved",
  Analyzing = "analyzing",
  Ready = "ready",
  Applied = "applied",
  Screen = "screen",
  Interview = "interview",
  Offer = "offer",
  Rejected = "rejected",
  Archived = "archived",
}

export enum DocumentType {
  Resume = "resume",
  CoverLetter = "cover_letter",
}

export enum TailoringMode {
  Conservative = "conservative",
  Full = "full",
}

export enum ClaimVerificationStatus {
  Supported = "supported",
  PartiallySupported = "partially_supported",
  Unsupported = "unsupported",
  Contradictory = "contradictory",
}

export enum GenerationRunStatus {
  Queued = "queued",
  Running = "running",
  Succeeded = "succeeded",
  Failed = "failed",
}

export enum SyncStatus {
  Idle = "idle",
  Queued = "queued",
  Syncing = "syncing",
  Completed = "completed",
  Failed = "failed",
}

export enum RunEventName {
  GithubSyncStarted = "github.sync.started",
  GithubRepoAnalyzing = "github.repo.analyzing",
  GithubRepoCompleted = "github.repo.completed",
  EvidenceCreated = "evidence.created",
  JobCaptured = "job.captured",
  JobAnalysisStarted = "job.analysis.started",
  JobAnalysisCompleted = "job.analysis.completed",
  GenerationStarted = "generation.started",
  GenerationVerifying = "generation.verifying",
  GenerationRendering = "generation.rendering",
  GenerationCompleted = "generation.completed",
  GenerationFailed = "generation.failed",
}
