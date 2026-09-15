# ProofHire --- Product Requirements Document

## Evidence-grounded AI career agent for software engineers

**Version:** 1.0\
**Date:** 16 September 2026\
**Status:** Build-ready PRD\
**Primary launch niche:** Software engineering, AI/ML, data and adjacent
technical roles where candidates have public or authorized GitHub
repositories.

------------------------------------------------------------------------

## 1. Executive Summary

ProofHire is an evidence-grounded career application system for
technical candidates. Instead of treating a resume as the complete
source of truth, ProofHire builds a persistent **Developer Evidence
Graph** from the candidate's GitHub repositories, optional base resume,
and user-confirmed claims.

A user connects GitHub once. ProofHire analyzes repositories and
extracts structured evidence: technologies, architectures, features,
APIs, infrastructure, ML models, tests, CI/CD, deployments, benchmark
results, contributions and other defensible technical achievements. The
user may optionally upload a base resume to supply employment,
education, awards and other information that GitHub cannot establish.

When the user encounters a job description, they can: 1. paste a URL or
JD into the web app; 2. upload a JD; 3. highlight a JD in the browser
and choose **Send to ProofHire** from the context menu.

ProofHire converts the JD into a structured Requirement Graph, retrieves
the strongest candidate evidence for each requirement, identifies
unsupported gaps, produces a positioning strategy, and generates a
tailored ATS-safe resume and cover letter. Every material generated
claim must retain provenance to its supporting evidence. Unsupported
experience must not be invented.

The project's primary technical differentiator is therefore not "AI
resume generation." It is:

> **Code-derived, claim-level evidence grounding for technical career
> applications.**

The system is intentionally designed as a reusable **Developer Evidence
Engine**. Resume tailoring is the first product surface; the same
evidence layer can later support interview preparation, recruiter
outreach, portfolio generation, application questions, personal
skill-gap analysis and other career workflows.

------------------------------------------------------------------------

# 2. Problem

Current resume tailoring tools generally start with a resume, master
profile or manually written career history. This creates four problems:

### 2.1 Information compression

A one-page resume contains only a small fraction of a developer's
technical history.

### 2.2 Weak provenance

Generated claims often cannot be traced to concrete source material.

### 2.3 Hallucination pressure

A JD may contain skills that are absent from the candidate profile.
Generative systems can overstate or invent experience to increase
apparent alignment.

### 2.4 Repetitive workflow

Candidates repeatedly copy job descriptions, upload resumes, describe
projects and ask models to tailor documents.

ProofHire addresses these with persistent evidence extraction,
structured retrieval, deterministic validation and one-click JD
ingestion.

------------------------------------------------------------------------

# 3. Product Principles

1.  **Evidence before eloquence.** No resume sentence is more important
    than its factual support.
2.  **Never fabricate fit.** A missing skill is a gap, not an invitation
    to invent experience.
3.  **GitHub is a source of evidence, not prompt decoration.**
4.  **AI proposes; deterministic systems verify.**
5.  **Progressive disclosure.** The default UX is simple; technical
    provenance is available when requested.
6.  **Fast path first.** After onboarding, a JD should require one
    action to begin analysis.
7.  **User control.** The candidate approves material claims and
    generated artifacts.
8.  **Provider independence.** Core domain logic cannot depend on a
    single LLM vendor.
9.  **Observable AI.** Prompts, model versions, retrieval traces,
    latency, cost and evaluation results are recordable.
10. **Modular monolith before microservices.** Strong boundaries, simple
    deployment, extract services only when scale requires it.

------------------------------------------------------------------------

# 4. Competitive Deep Dive

Research snapshot: 16 September 2026.

## 4.1 end1989/tailored

**Current strengths** - Master Profile as a structured source of
truth. - Job URL ingestion. - Resume + cover-letter generation. -
Truthfulness checks enforced in the data/write layer rather than only in
prompts. - MCP support. - Portfolio scan workflow that can turn
repositories into evidence-backed project entries. - Application
tracking. - Multiple PDF/HTML/ATS templates. - Large automated test
suite.

**Architecture lessons** - Put factual invariants in deterministic
validators. - Keep generation provider-independent through a stable
contract. - Validate actual rendered PDFs, not only source content. -
Job lifecycle tracking belongs beside generation because users revisit
applications.

**Gap ProofHire must exploit** Tailored has moved toward repository
evidence, so "we scan GitHub" is no longer a sufficient differentiator.
ProofHire must make repository intelligence a first-class data model:
granular evidence nodes, source locators, confidence, extraction method,
requirement-to-evidence edges, claim provenance and evaluation metrics.

## 4.2 nikogura/resume-tailor

**Current strengths** - Structured career history. - Two-phase JD
analysis and generation. - Separate evaluator for hallucinations. -
Evaluation history becomes RAG context for future runs. - PDF
generation. - Job URL input.

**Architecture lessons** - Generation and evaluation should use
independent stages. - Evaluation failures can become reusable system
knowledge. - Anti-fabrication must be measured, not assumed.

**Gap ProofHire must exploit** The knowledge base is primarily
structured human-authored experience. ProofHire should derive evidence
from code/config/docs/commits and preserve source-level provenance.

## 4.3 srbhr/Resume-Matcher

**Current strengths** - Mature open-source product and broad feature
set. - FastAPI backend, Next.js/React frontend. - Multi-provider LLM
abstraction. - Resume parsing and improvement workflow. - Resume
builder, cover letters, interview preparation and application
tracking. - SQLite/SQLAlchemy architecture and encrypted API-key
handling. - PDF rendering through browser technology. - Large community
footprint.

**Architecture lessons** - Separate routers, services, schemas and
provider adapters. - Multi-provider support is valuable. - Local-first
is attractive for sensitive career data. - Resume generation is a
product workflow, not a single LLM call.

**Gap ProofHire must exploit** Resume Matcher is resume-centric.
ProofHire's core entity should be the evidence graph and its
relationship to job requirements.

## 4.4 narendranathe/tailor-resume

**Current strengths** - Deterministic pipeline. - Multiple input formats
normalized into one Profile model. - Weighted matching. - Relevance
gate. - Explicit behavior when metrics are missing. - Strong testing. -
Render-time constraints.

**Architecture lessons** - Keep deterministic scoring alongside LLM
semantic judgment. - Reject or flag poor-fit generation instead of
inflating alignment. - Make rendering failures visible. - Normalize
source formats before downstream processing.

**Gap ProofHire must exploit** Its matching operates primarily over
resume/profile content, not a code-derived evidence graph.

## 4.5 PSR94/resume-tailor

**Current strength** - Preserves an existing resume layout and
selectively replaces weak bullets instead of rebuilding everything.

**Lesson** ProofHire should support both **Conservative Tailoring** and
**Full Tailoring** modes.

------------------------------------------------------------------------

# 5. Competitive Feature Matrix

  --------------------------------------------------------------------------------------------------------
  Capability     ProofHire     Tailored               nikogura           Resume Matcher   tailor-resume
                 target                                                                   
  -------------- ------------- ---------------------- ------------------ ---------------- ----------------
  Base resume    Yes           Master profile         Structured history Resume-centric   Resume-centric
  optional                                                                                

  GitHub         Native        Portfolio scan         Project metadata   Not core         Not core
  connection                   workflow                                                   

  Automated      Core          Partial/agent-driven   No core pipeline   No core pipeline No
  code/config                                                                             
  analysis                                                                                

  Persistent     Core          Profile entries        Structured         Resume/job DB    Profile
  evidence graph                                      summaries/RAG                       

  Source-level   Core          Some evidence-backed   Evaluation based   Limited          Limited
  claim                        profile support                                            
  provenance                                                                              

  JD URL/paste   Yes           Yes                    Yes                Paste            Paste

  Browser        Core          Not core               No                 No               Planned
  context-menu                                                                            integrations
  ingestion                                                                               

  Requirement    Core          JD parsing             JD analysis        Keyword/job      Weighted scoring
  graph                                                                  parsing          

  Hybrid         Core          Agent/profile          RAG                AI/keyword       Deterministic
  retrieval                    selection                                 matching         

  Independent    Core          Deterministic write    Separate evaluator LLM pipeline     Deterministic
  claim verifier               guard                                                      checks

  Evidence       Core          Partial                Relevance ranking  Match score      ATS score
  coverage                                                                                
  matrix                                                                                  

  Refuse/flag    Yes           Truthfulness guard     Anti-fabrication   Suggestions      Relevance gate
  unsupported                                                                             
  fit                                                                                     

  Resume         Yes           Yes                    Yes                Yes              Yes
  generation                                                                              

  Cover letter   Yes           Yes                    Yes                Yes              Adjacent

  Multiple       Yes           Yes                    LaTeX              Yes              LaTeX
  templates                                                                               

  Application    V1            Yes                    Output folders     Yes              No
  tracking                                                                                

  Evaluation     Core          Strong tests           Evaluator          Tests            458+ tests
  benchmark      engineering                                                              
  suite          goal                                                                     

  Interview prep V1.5          No core                No                 Yes              No
  --------------------------------------------------------------------------------------------------------

**Conclusion:** ProofHire must win on the depth, structure, auditability
and evaluation of developer evidence---not merely on document
generation.

------------------------------------------------------------------------

# 6. Target Users

## Primary persona: Early-career technical candidate

-   SWE, AI/ML Engineer, Data Scientist, Data Engineer, MLOps, DevOps.
-   Has multiple GitHub projects.
-   Applies to many related but differently worded roles.
-   Needs to surface relevant project evidence without exaggerating.

## Secondary persona: Experienced open-source engineer

-   Has substantial public code that is poorly represented in a
    conventional resume.
-   Wants fast job-specific positioning with factual guarantees.

## Future persona: Career coach/recruiter

Out of MVP scope. Could manage candidate profiles with explicit consent.

------------------------------------------------------------------------

# 7. Jobs To Be Done

-   "When I find a technical job, show me which parts of my actual work
    support its requirements."
-   "Turn that evidence into an application without inventing skills."
-   "Show me what I cannot honestly claim."
-   "Generate a polished resume and cover letter without repeated
    copy/paste."
-   "Let me inspect why every important claim was written."
-   "Keep my developer knowledge current as my GitHub changes."

------------------------------------------------------------------------

# 8. Scope

## 8.1 MVP / V1

-   Account/authentication.
-   GitHub OAuth/App connection.
-   Repository selection and sync.
-   Repository metadata ingestion.
-   README, code, config, CI/CD, dependency and selected commit
    analysis.
-   Evidence extraction and persistent evidence graph.
-   Optional PDF/DOCX resume upload and structured profile extraction.
-   Evidence review/confirmation UI.
-   JD paste and URL ingestion.
-   Chrome/Chromium browser extension with context-menu JD capture.
-   Structured JD requirement extraction.
-   Requirement-to-evidence matching.
-   Evidence Coverage Matrix.
-   Gap detection.
-   Positioning strategy.
-   Conservative and Full tailoring.
-   ATS-safe resume generation.
-   Cover-letter generation.
-   Claim-level provenance.
-   Deterministic claim validation.
-   PDF generation and parse-back validation.
-   Application history.
-   Evaluation/telemetry for AI quality.
-   Responsive premium web interface.
-   Light/dark modes.
-   Accessibility baseline.

## 8.2 V1.5

-   Interview preparation grounded in evidence.
-   Recruiter outreach messages.
-   Application question drafting.
-   GitHub webhook incremental refresh.
-   Multi-resume profile variants.
-   Local-model support.
-   More browsers.
-   Public shareable evidence/portfolio view.

## 8.3 Out of scope for V1

-   Automated job applications.
-   Scraping private repositories without authorization.
-   LinkedIn automation.
-   Fabricating metrics.
-   Candidate ranking for employers.
-   Mobile-native apps.
-   Full ATS emulation.
-   Claims that a specific "ATS score" predicts hiring outcomes.

------------------------------------------------------------------------

# 9. Core User Journey

## 9.1 Onboarding

1.  User creates account.
2.  Connect GitHub.
3.  Select repositories: all public, selected public, and optionally
    authorized private repos.
4.  Optional: upload base resume.
5.  System begins ingestion.
6.  UI streams progress by repository.
7.  Evidence Review opens when first useful evidence is ready.
8.  User can approve, edit, reject or mark evidence private.

**Target:** user reaches first evidence insight in \< 2 minutes for a
small GitHub profile.

## 9.2 Job capture

Three equivalent entry paths: - paste JD; - enter job URL; - browser
extension → highlight text → right-click → **Send to ProofHire**.

Extension payload: - selected text; - page URL; - page title; -
timestamp; - optional inferred company/role; - authenticated
user/session reference.

## 9.3 Analysis

1.  Normalize JD.
2.  Extract company, role, seniority, responsibilities, required
    qualifications, preferred qualifications, technologies and domain.
3.  Build Requirement Graph.
4.  Retrieve candidate evidence.
5.  Rerank evidence per requirement.
6.  Produce coverage/gap matrix.
7.  Determine whether claims are strongly supported, partially supported
    or unsupported.
8.  Generate positioning strategy.

## 9.4 Generation

1.  User chooses Conservative or Full Tailoring.
2.  Planner selects evidence.
3.  Writer generates structured resume content.
4.  Claim extractor identifies factual claims.
5.  Verifier checks claims against evidence/profile.
6.  Deterministic validators enforce immutable facts.
7.  Failed claims are repaired or removed.
8.  Renderer produces HTML/PDF/plain-text.
9.  Parse-back validator confirms output text and required sections.
10. User reviews diff and provenance.
11. User exports.

------------------------------------------------------------------------

# 10. Information Architecture

Primary navigation:

-   **Home**
-   **Evidence**
-   **Jobs**
-   **Applications**
-   **Documents**
-   **Settings**

## Home

A calm command center: - GitHub sync status. - evidence count and
freshness. - recent jobs. - applications in progress. - prominent
"Analyze a job" command. - meaningful gaps/actions, not vanity charts.

## Evidence

Three synchronized views: 1. **Graph View** ---
skills/projects/claims/evidence relationships. 2. **Explorer View** ---
filterable evidence list. 3. **Repository View** --- evidence organized
by repository and source.

## Job Workspace

A split workspace: - left: JD Requirement Graph / coverage matrix; -
center: positioning and generated resume; - right: evidence
inspector/provenance.

------------------------------------------------------------------------

# 11. State-of-the-Art Frontend Experience

The frontend should feel like a 2026 developer tool, not an HR SaaS
template.

## 11.1 Visual direction

**"Editorial developer intelligence."** - High information density
without clutter. - Strong typography. - Restrained neutral surfaces with
a luminous accent system. - Fine borders, subtle depth, glass only where
functionally useful. - Monospace reserved for evidence, paths, hashes
and technical metadata. - Avoid generic gradient blobs and excessive
card grids.

## 11.2 Signature interaction: Evidence Constellation

The Evidence page visualizes the user's technical history as a navigable
graph: - project nodes; - skill nodes; - architecture/capability
nodes; - evidence nodes; - weighted edges; - hover reveals source; -
selecting a JD overlays requirement nodes and lights up supporting
evidence paths.

This is not decoration: it is an alternate interface to the same
evidence data.

Use WebGL/canvas only where necessary; provide accessible list/table
equivalents.

## 11.3 Job analysis animation

When a JD enters: 1. JD panel condenses into requirement chips. 2.
requirement nodes enter the evidence graph; 3. evidence paths
illuminate; 4. unmatched requirements remain visually distinct; 5.
workspace transitions into the coverage matrix.

Motion should explain computation, not delay it.

## 11.4 Resume provenance interaction

Hover/click a generated bullet: - highlight the claim; - open provenance
rail; - show supporting evidence; - repository/file path; - source
snippet; - confidence; - extraction method; - verification status.

## 11.5 Command palette

`Cmd/Ctrl + K`: - Analyze job - Sync GitHub - Search evidence - Open
application - Export resume - Change template - Toggle theme

## 11.6 Motion

Use Framer Motion for purposeful transitions. - 150--220 ms
micro-interactions. - 250--450 ms workspace transitions. - honor
`prefers-reduced-motion`. - no motion that blocks primary actions.

## 11.7 Responsive

Desktop is primary. Tablet fully usable. Mobile supports
review/status/export but graph-heavy workflows may switch to list mode.

## 11.8 Accessibility

-   WCAG 2.2 AA target.
-   full keyboard navigation.
-   visible focus states.
-   semantic HTML.
-   graph has nonvisual equivalent.
-   color never sole carrier of match status.

------------------------------------------------------------------------

# 12. Recommended Technical Architecture

## 12.1 Architecture style

Start as a **modular monorepo + modular monolith backend + asynchronous
workers**.

Do not begin with microservices. Define boundaries so high-load
components can later be extracted.

## 12.2 Monorepo

``` text
proofhire/
├── apps/
│   ├── web/                  # Next.js web app
│   ├── api/                  # FastAPI API
│   ├── worker/               # async ingestion/AI workers
│   └── extension/            # browser extension
├── packages/
│   ├── contracts/            # OpenAPI-generated TS/Python contracts
│   ├── design-system/        # shared UI tokens/components
│   ├── prompts/              # versioned prompt definitions
│   ├── evals/                # datasets + evaluation harness
│   └── config/
├── infra/
│   ├── docker/
│   ├── migrations/
│   └── deployment/
├── docs/
│   ├── adr/
│   ├── api/
│   └── product/
└── tests/
    └── e2e/
```

## 12.3 Stack

**Web:** Next.js 16+, React 19+, TypeScript, Tailwind CSS, shadcn/Radix
primitives, Framer Motion, TanStack Query.\
**Graph:** React Flow for initial graph UX; graduate to Sigma.js/WebGL
if graph scale demands it.\
**API:** Python 3.13+, FastAPI, Pydantic v2, SQLAlchemy 2.\
**Worker:** Celery/Dramatiq/Arq-class worker; recommended initial
choice: Dramatiq + Redis for simple durable background jobs.\
**Primary DB:** PostgreSQL.\
**Vector:** pgvector initially.\
**Graph:** PostgreSQL relational edge tables initially; do not add Neo4j
until query patterns prove it necessary.\
**Object storage:** S3-compatible storage for uploaded resumes/rendered
documents.\
**Cache/queue:** Redis.\
**LLM:** provider adapter with structured outputs; support at least
OpenAI + Anthropic behind one interface.\
**Observability:** OpenTelemetry + structured logs + Sentry-class error
reporting.\
**PDF:** HTML/CSS → Playwright/Chromium PDF; parse-back text
validation.\
**Auth:** managed auth or standards-based OIDC; GitHub OAuth separate
from application auth if necessary.\
**Extension:** Manifest V3, TypeScript, minimal permissions.

------------------------------------------------------------------------

# 13. Domain Model

## User

`id, email, display_name, created_at, settings`

## GitHubConnection

`id, user_id, github_user_id, login, token_ref, scopes, connected_at, last_sync_at`

Tokens must never be stored plaintext.

## Repository

`id, user_id, provider_repo_id, owner, name, url, visibility, default_branch, language_summary, stars, selected, last_commit_sha, last_analyzed_sha, sync_status`

## SourceArtifact

Represents an analyzable source.
`id, repository_id, type, path, commit_sha, content_hash, language, metadata, storage_ref`

Types include:
`readme, source_file, dependency_manifest, ci_config, docker, kubernetes, terraform, notebook, benchmark, test, docs, commit_metadata`

## Evidence

`id, user_id, repository_id, evidence_type, title, normalized_claim, description, confidence, extraction_method, status, created_at, superseded_by`

Statuses: `candidate, confirmed, rejected, private, stale`

Evidence types:
`skill_usage, architecture, implementation, integration, deployment, testing, ml_model, data_pipeline, performance_metric, ownership, contribution, feature`

## EvidenceSource

Many-to-many evidence provenance:
`evidence_id, source_artifact_id, locator, snippet_hash, line_start?, line_end?, commit_sha, relevance`

## Skill

`id, canonical_name, aliases, category`

## EvidenceSkill

`evidence_id, skill_id, strength`

## ProfileFact

For optional resume/user facts:
`id, user_id, type, value_json, source, immutable, confirmed`

Types:
`employment, education, award, certification, contact, summary_fact`

## Job

`id, user_id, source_url, source_text, company, role, seniority, location, captured_at, status`

## Requirement

`id, job_id, category, text, normalized, importance, required, confidence`

Categories:
`skill, experience, responsibility, domain, education, tooling, soft_skill, seniority`

## EvidenceMatch

`requirement_id, evidence_id, retrieval_score, rerank_score, match_reason, status`

## Application

`id, user_id, job_id, stage, created_at, updated_at`

Stages:
`saved, analyzing, ready, applied, screen, interview, offer, rejected, archived`

## GeneratedDocument

`id, application_id, type, template_id, version, content_json, html_ref, pdf_ref, plaintext_ref, generation_run_id`

## GeneratedClaim

`id, document_id, claim_text, claim_type, verification_status, confidence`

## ClaimEvidence

`claim_id, evidence_id, support_score, verifier_reason`

## GenerationRun

`id, user_id, job_id, pipeline_version, model_config, prompt_versions, token_usage, latency_ms, estimated_cost, status`

------------------------------------------------------------------------

# 14. Evidence Graph Semantics

Logical graph:

``` text
(User)-[:OWNS]->(Repository)
(Repository)-[:CONTAINS]->(SourceArtifact)
(SourceArtifact)-[:SUPPORTS]->(Evidence)
(Evidence)-[:DEMONSTRATES]->(Skill)
(Job)-[:HAS]->(Requirement)
(Evidence)-[:MATCHES]->(Requirement)
(GeneratedClaim)-[:SUPPORTED_BY]->(Evidence)
```

PostgreSQL remains the source of truth. Graph semantics are represented
with relational tables and indexed joins.

Every Evidence node MUST have at least one EvidenceSource unless its
source is an explicitly user-confirmed ProfileFact.

------------------------------------------------------------------------

# 15. GitHub Ingestion Pipeline

## Stage 1: Repository inventory

Fetch: - metadata; - default branch; - languages; - repository tree; -
latest SHA; - topics; - releases where useful.

## Stage 2: Relevance-aware file selection

Do not blindly embed every file.

Priority classes: **P0:** README, package/dependency manifests,
Dockerfiles, compose, CI, Kubernetes, Terraform, ML configs,
benchmark/results docs.\
**P1:** entry points, service boundaries, API definitions,
model/training/evaluation code, database schemas.\
**P2:** representative implementation files.\
**P3:** low-information/generated/vendor files --- exclude.

## Stage 3: Deterministic extraction

Before LLM analysis, extract: - languages; - frameworks/dependencies; -
CI providers; - containers; - infrastructure; - test frameworks; - model
libraries; - DBs; - APIs; - obvious metrics in benchmark/result
artifacts.

## Stage 4: Semantic evidence extraction

LLM receives bounded source groups and produces structured candidate
Evidence objects with source locators.

## Stage 5: Deduplication

Merge semantically equivalent evidence while retaining all provenance.

## Stage 6: confidence and validation

Confidence combines: - deterministic signals; - number of independent
sources; - source type; - semantic extraction confidence; -
contradiction checks.

## Stage 7: persistence/indexing

Store graph entities and vector representations.

## Stage 8: incremental sync

Compare latest commit SHA/content hashes. Reprocess only changed
relevant artifacts and dependent evidence.

------------------------------------------------------------------------

# 16. JD Requirement Pipeline

Structured output:

``` json
{
  "role": "...",
  "company": "...",
  "seniority": "...",
  "requirements": [
    {
      "text": "...",
      "category": "skill",
      "required": true,
      "importance": 0.92,
      "normalized": ["kafka", "stream-processing"]
    }
  ]
}
```

Rules: - Preserve original text. - Distinguish required from
preferred. - Do not treat generic company marketing text as a candidate
requirement. - Group duplicates but retain source references. - Keep
seniority/years-of-experience separate from technical skill matching.

------------------------------------------------------------------------

# 17. Retrieval and Matching

## Candidate generation

Hybrid retrieval: 1. lexical/BM25-like matching; 2. vector similarity;
3. skill/entity overlap; 4. repository metadata filters; 5.
evidence-type priors.

## Reranking

Cross-encoder or LLM structured reranker evaluates: - directness; -
depth; - recency; - source quality; - requirement specificity.

## Match labels

-   **Strong:** direct, defensible evidence.
-   **Partial:** related evidence but not equivalent.
-   **Gap:** no defensible evidence.
-   **Unknown:** evidence may exist but source coverage is insufficient.

Never collapse Partial into Strong merely to improve perceived fit.

------------------------------------------------------------------------

# 18. Evidence Coverage Matrix

This replaces misleading "ATS probability" language.

Per requirement show: - requirement; - required/preferred; -
importance; - match label; - best evidence; - source repository; -
support confidence; - explanation; - action.

Aggregate indicators may include: - required-requirement evidence
coverage; - preferred-requirement coverage; - evidence confidence; -
unsupported critical requirements.

These are descriptive system metrics, not promises about ATS or hiring
outcomes.

------------------------------------------------------------------------

# 19. Generation Pipeline

``` text
Requirement Graph
      +
Evidence Matches
      +
Profile Facts
      ↓
Positioning Planner
      ↓
Evidence Selection
      ↓
Resume Writer / Cover Letter Writer
      ↓
Claim Extraction
      ↓
Evidence Verifier
      ↓
Deterministic Fact Guard
      ↓
Repair Loop (max N)
      ↓
Renderer
      ↓
Parse-back Validator
      ↓
User Review
```

## 19.1 Positioning Planner

Produces: - target professional identity; - 3--5 strongest themes; -
project priority; - skills priority; - gaps to avoid overstating; -
recommended section ordering.

## 19.2 Resume writer

Constraints: - only supplied ProfileFacts/Evidence may create factual
claims; - metrics must have evidence or user confirmation; - preserve
immutable employer/date/degree facts; - concise action/result-oriented
bullets; - avoid keyword stuffing; - no hidden text; - no claims of
skills solely because they appear in the JD.

## 19.3 Claim verifier

For every generated factual claim: 1. decompose into atomic
propositions; 2. retrieve cited evidence; 3. classify
`supported | partially_supported | unsupported | contradictory`; 4.
return reason and evidence IDs.

Unsupported claims cannot reach final export.

## 19.4 Deterministic guard

Validate exact entities: - employer; - title; - dates; - degree; -
certification; - project/repository identity; - numeric metrics.

## 19.5 Repair loop

Writer receives only failed claims and verifier reasons. Maximum 2
repair passes before dropping the claim.

------------------------------------------------------------------------

# 20. Resume Modes

## Conservative Tailoring

-   preserve section structure;
-   preserve layout/template;
-   reorder within safe boundaries;
-   replace/rewrite selected bullets;
-   reorder skills;
-   optionally rewrite summary.

## Full Tailoring

-   choose strongest projects;
-   reorder sections;
-   rewrite supported bullets;
-   change emphasis;
-   generate target summary;
-   choose template based on content density.

Both modes preserve immutable facts.

------------------------------------------------------------------------

# 21. Rendering

V1 templates: 1. **Jake-inspired ATS Minimal** 2. **Technical Dense** 3.
**Modern Editorial**

Requirements: - single-column ATS-safe option; - selectable Letter/A4; -
text remains selectable; - no essential information in images; - stable
page breaking; - PDF, HTML and plain-text exports; - deterministic
template snapshots; - parse generated PDF and compare required
content; - warn on overflow/underflow.

Do not reproduce third-party templates in ways that violate their
licenses; implement original template code inspired by general layout
principles and document attribution/license where required.

------------------------------------------------------------------------

# 22. Browser Extension

## V1

Manifest V3.

Context menu: **Send selection to ProofHire**

If no text selected: **Analyze this job with ProofHire** - attempts safe
page extraction; - if extraction fails, opens capture panel for paste.

Permissions should be minimal: - contextMenus; - activeTab; - storage; -
authenticated calls to ProofHire.

Avoid broad `<all_urls>` content-script access unless a feature
demonstrably requires it.

## Flow

1.  User highlights JD.
2.  Right-click.
3.  Extension sends payload.
4.  Toast: "Sent to ProofHire."
5.  Optional button: "Open analysis."
6.  Web app receives a live/poll update and creates Job workspace.

------------------------------------------------------------------------

# 23. API Contract --- V1

Version all endpoints under `/api/v1`.

## GitHub

`POST /github/connect`\
`GET /github/repositories`\
`PATCH /github/repositories/{id}`\
`POST /github/sync`\
`GET /github/sync/{run_id}`

## Evidence

`GET /evidence`\
`GET /evidence/{id}`\
`PATCH /evidence/{id}`\
`GET /evidence/graph`\
`POST /evidence/search`

## Profile

`POST /profile/resume`\
`GET /profile/facts`\
`PATCH /profile/facts/{id}`

## Jobs

`POST /jobs`\
`POST /jobs/capture`\
`GET /jobs/{id}`\
`POST /jobs/{id}/analyze`\
`GET /jobs/{id}/requirements`\
`GET /jobs/{id}/coverage`

## Generation

`POST /jobs/{id}/positioning`\
`POST /jobs/{id}/generate`\
`GET /generation-runs/{id}`\
`GET /documents/{id}`\
`GET /documents/{id}/claims`\
`POST /documents/{id}/export`

## Applications

`GET /applications`\
`POST /applications`\
`PATCH /applications/{id}`

## Streaming

Use SSE initially: `GET /events/runs/{run_id}`

WebSockets are unnecessary until bidirectional realtime requirements
appear.

------------------------------------------------------------------------

# 24. Shared Contracts

All three implementation agents must treat these as immutable without an
ADR: - domain entity names; - API route names; - enum values; - JSON
schemas; - event names; - database ownership; - design tokens.

Generate TypeScript clients/types from FastAPI OpenAPI rather than
manually duplicating schemas.

Critical events: - `github.sync.started` - `github.repo.analyzing` -
`github.repo.completed` - `evidence.created` - `job.captured` -
`job.analysis.started` - `job.analysis.completed` -
`generation.started` - `generation.verifying` - `generation.rendering` -
`generation.completed` - `generation.failed`

------------------------------------------------------------------------

# 25. AI Provider Abstraction

Interface:

``` python
class LLMProvider(Protocol):
    async def structured_generate(
        self,
        *,
        task: str,
        messages: list[Message],
        schema: type[BaseModel],
        model_config: ModelConfig,
    ) -> BaseModel: ...
```

No domain service imports an OpenAI/Anthropic SDK directly.

Provider adapters own: - API translation; - retries; - rate-limit
handling; - structured-output behavior; - token/cost metadata.

Prompt versions are explicit: `jd_extract:v1`, `evidence_extract:v1`,
`rerank:v1`, `position:v1`, `resume_write:v1`, `claim_verify:v1`.

------------------------------------------------------------------------

# 26. Evaluation Strategy

This is a first-class product requirement and a major portfolio
differentiator.

## 26.1 Evaluation dataset

Create a versioned benchmark: - 100+ technical JDs initially; - SWE,
frontend, backend, full-stack, AI/ML, data, MLOps/DevOps; - a set of
synthetic/public test developer profiles; - human-labeled JD
requirements; - human-labeled evidence matches; - known unsupported
claims.

Never include private user data in public eval datasets.

## 26.2 Metrics

### Requirement extraction

-   precision;
-   recall;
-   F1;
-   required/preferred classification accuracy.

### Retrieval

-   Recall@K;
-   MRR/nDCG;
-   strong-vs-partial classification accuracy.

### Grounded generation

-   unsupported claim rate;
-   contradiction rate;
-   citation/evidence precision;
-   claim coverage.

### Document quality

-   parse-back success rate;
-   overflow rate;
-   required-section preservation;
-   deterministic snapshot checks.

### Operational

-   p50/p95 latency;
-   tokens/run;
-   cost/run;
-   ingestion time/repository;
-   cache hit rate.

## 26.3 Target V1 quality gates

-   ≥ 0.90 requirement extraction F1 on internal benchmark.
-   ≥ 0.90 Recall@5 for labeled supporting evidence.
-   \< 1% unsupported factual claims after verifier/guard.
-   100% immutable-fact preservation in deterministic tests.
-   ≥ 99% successful parse-back across template regression corpus.
-   Zero secrets in logs.

Targets are engineering goals, not externally guaranteed claims.

------------------------------------------------------------------------

# 27. Security and Privacy

Career data and private repositories are sensitive.

Requirements: - OAuth least privilege. - encrypted tokens at rest using
managed KMS/secret encryption. - never send an entire private repository
to an LLM by default. - bounded, relevant source snippets only. -
user-visible setting for which repositories may be processed. - ability
to disconnect GitHub. - ability to delete imported repository data. -
redact secrets before persistence/LLM transmission. - secret scanner
before semantic extraction. - do not ingest `.env`, credentials, private
keys or known secret file patterns. - object storage signed URLs. -
row-level ownership checks. - rate limiting. - audit security-sensitive
actions. - CSP and secure extension messaging. - CSRF protections where
relevant. - dependency and container scanning in CI.

------------------------------------------------------------------------

# 28. Performance and Scalability

## V1 targets

-   normal API requests p95 \< 400 ms excluding AI/background
    operations.
-   first useful job-analysis progress event \< 2 s.
-   all AI/ingestion work asynchronous.
-   repository sync idempotent.
-   job generation idempotency key.
-   queue supports retries with exponential backoff.
-   concurrency limits per user/provider.
-   source content deduplicated by content hash.
-   embeddings cached by normalized content hash.

## Scale path

1.  Postgres + pgvector.
2.  Redis queue/cache.
3.  stateless API replicas.
4.  independent worker replicas by queue: `ingest`, `ai`, `render`.
5.  object storage/CDN.
6.  only then evaluate specialized vector DB or graph DB.

------------------------------------------------------------------------

# 29. Observability

Every run gets `trace_id` and `generation_run_id`.

Capture: - pipeline stage; - prompt version; - model; - latency; -
retries; - token usage; - estimated cost; - retrieval
candidates/scores; - verifier outcomes; - render status.

Never log raw private source code by default.

Dashboards: - pipeline success rate; - stage latency; - provider
errors; - unsupported-claim catches; - cost/run; - ingestion backlog.

------------------------------------------------------------------------

# 30. Testing Strategy

## Unit

-   parsers;
-   normalization;
-   scoring;
-   dedup;
-   deterministic guards;
-   template utilities.

## Contract

-   OpenAPI snapshot.
-   generated client compatibility.
-   event schemas.

## Integration

-   GitHub fixture ingestion.
-   Postgres/pgvector retrieval.
-   provider adapters with mocked responses.
-   object storage.
-   worker retries/idempotency.

## AI evaluation tests

-   structured-output fixtures.
-   requirement extraction benchmark.
-   retrieval benchmark.
-   adversarial hallucination cases.

## Frontend

-   component tests;
-   accessibility tests;
-   visual regression;
-   reduced-motion behavior.

## E2E

Playwright: 1. onboarding fixture; 2. sync repository; 3. evidence
appears; 4. capture JD; 5. analyze; 6. inspect provenance; 7. generate;
8. verify; 9. export PDF; 10. parse-back assertion.

------------------------------------------------------------------------

# 31. CI/CD

On every PR: - format/lint; - type check; - unit tests; - contract
tests; - frontend tests; - build; - security/dependency scan.

On main: - integration tests; - selected eval suite; - Docker build; -
preview/staging deploy.

Nightly: - full AI eval suite with spend cap; - template rendering
corpus; - dependency/security scan.

Use conventional commits and changesets only if package publishing
requires them.

------------------------------------------------------------------------

# 32. Analytics / Product Metrics

Privacy-respecting events: - onboarding completed; - GitHub connected; -
repos selected; - first evidence reviewed; - JD captured by source; -
analysis completed; - generation completed; - provenance opened; -
document exported; - evidence edited/rejected.

Primary product metric: **% of captured technical jobs that reach a
verified document export.**

Quality guardrail: **unsupported claim rate.**

Do not optimize engagement at the expense of truthful outputs.

------------------------------------------------------------------------

# 33. Design System

## Foundations

-   4/8 px spacing rhythm.
-   fluid type scale.
-   semantic color tokens, never hard-coded feature colors.
-   radii hierarchy: small controls, medium panels, large
    modal/workspaces.
-   shadows subtle and elevation-driven.
-   light/dark token parity.

## Typography

-   high-quality grotesk/sans for UI.
-   readable editorial face optional for marketing only.
-   monospace for code/evidence metadata.
-   avoid mixing more than three font roles.

## Core components

-   Button
-   IconButton
-   Input/Textarea
-   Select/Combobox
-   CommandPalette
-   Tooltip
-   Popover
-   Dialog
-   Sheet
-   Tabs
-   DataTable
-   StatusPill
-   RequirementChip
-   EvidenceCard
-   EvidenceSource
-   ConfidenceIndicator
-   ProvenanceRail
-   GraphNode
-   GraphEdge
-   ResumePreview
-   DiffViewer
-   PipelineProgress
-   EmptyState
-   Skeleton
-   Toast

Every component needs keyboard, focus, dark mode and reduced-motion
states.

------------------------------------------------------------------------

# 34. Three-Agent Parallel Implementation Plan

The project is deliberately partitioned so three coding agents can work
concurrently with minimal file conflicts.

## Day 0 --- Integration contract (owner: you/lead, before parallel work)

Create the monorepo skeleton and commit: - directory structure; - root
README; - `docs/product/PRD.md`; - `docs/adr/0001-architecture.md`; -
initial `openapi.yaml` or FastAPI schema stubs; - canonical enums in
`packages/contracts`; - `.editorconfig`; - lint/format configs; - Docker
Compose for Postgres + Redis; - CI skeleton.

Then create branches:

``` text
agent/platform
agent/intelligence
agent/experience
```

Agents may add files inside their owned paths but must not casually
modify another agent's owned paths.

------------------------------------------------------------------------

## AGENT 1 --- Platform, Data & GitHub Ingestion

**Mission:** Build the trustworthy data plane.

### Owns

``` text
apps/api/
apps/worker/ingestion/
infra/migrations/
packages/contracts/   # schema implementation, changes require ADR
tests/integration/platform/
```

### Deliverables

#### A1. Platform foundation

-   FastAPI app.
-   config/environment system.
-   PostgreSQL async SQLAlchemy.
-   Alembic migrations.
-   Redis.
-   background job framework.
-   health/readiness endpoints.
-   structured logging.
-   trace IDs.

#### A2. Authentication/ownership

-   user model.
-   auth middleware.
-   ownership checks.
-   test auth fixture.

#### A3. GitHub integration

-   OAuth/GitHub App flow.
-   encrypted token persistence.
-   repo listing/selection.
-   repository sync.
-   rate-limit handling.
-   incremental SHA/content-hash logic.

#### A4. Repository source extraction

-   repository tree inventory.
-   ignore generated/vendor/binary/secret files.
-   artifact priority classifier.
-   deterministic technology extraction.
-   SourceArtifact persistence.

#### A5. Evidence persistence APIs

Implement storage and APIs for Evidence/EvidenceSource/Skill and graph
projection.

**Important:** Agent 1 persists candidate evidence produced by Agent 2
but does not own semantic evidence-generation prompts.

#### A6. Job/application persistence

CRUD for Job, Requirement, Application, GeneratedDocument,
GenerationRun.

#### A7. SSE run events

Provide event stream contract used by frontend.

### Agent 1 acceptance criteria

-   migrations create complete V1 schema;
-   repository fixture sync is idempotent;
-   changed SHA reprocesses only affected artifacts;
-   secrets excluded;
-   ownership tests pass;
-   API OpenAPI contract matches shared schemas;
-   integration tests run against real Postgres/Redis containers.

------------------------------------------------------------------------

## AGENT 2 --- AI Intelligence, Retrieval, Verification & Evals

**Mission:** Build the differentiated AI engineering core.

### Owns

``` text
apps/worker/intelligence/
packages/prompts/
packages/evals/
tests/evals/
tests/integration/intelligence/
```

### Must consume, not redefine

-   Agent 1 domain contracts.
-   repository/source/evidence schemas.
-   job/requirement schemas.

### Deliverables

#### B1. LLM provider abstraction

-   OpenAI adapter.
-   Anthropic adapter.
-   mock adapter.
-   structured output.
-   retry/rate-limit policy.
-   model usage metadata.

#### B2. Evidence extraction

Input: selected SourceArtifacts.\
Output: typed candidate Evidence + provenance.

Include: - source grouping/chunking; - deterministic + semantic evidence
fusion; - dedup; - confidence calculation; - contradiction handling.

#### B3. Embeddings and hybrid retrieval

-   embedding abstraction;
-   pgvector queries through platform repository interface;
-   lexical/entity candidate generation;
-   reranking;
-   match classification.

#### B4. JD intelligence

-   requirement extraction;
-   normalization;
-   required/preferred classification;
-   importance;
-   duplicate merging.

#### B5. Coverage engine

Produce Evidence Coverage Matrix and descriptive aggregate coverage.

#### B6. Positioning planner

Generate supported positioning themes and explicitly list gaps.

#### B7. Document generation

-   resume structured content;
-   cover letter;
-   Conservative/Full modes;
-   versioned prompts.

#### B8. Claim verification

-   claim decomposition;
-   evidence lookup;
-   supported/partial/unsupported/contradictory;
-   deterministic fact guard hooks;
-   repair loop.

#### B9. Evaluation harness

-   dataset schema;
-   CLI;
-   requirement F1;
-   Recall@K/MRR/nDCG;
-   unsupported claim rate;
-   latency/token/cost reports;
-   seeded fixtures.

### Agent 2 acceptance criteria

-   all AI outputs validated by Pydantic schemas;
-   mock provider supports deterministic CI;
-   unsupported claims cannot be marked exportable;
-   eval command produces machine-readable JSON + human summary;
-   prompt versions stored with GenerationRun;
-   no provider SDK leaks into domain services.

------------------------------------------------------------------------

## AGENT 3 --- Product Experience, Design System, Web App & Extension

**Mission:** Build the premium user-facing experience.

### Owns

``` text
apps/web/
apps/extension/
packages/design-system/
tests/e2e/
```

### Must consume

-   generated API client/contracts.
-   SSE event schemas.
-   mock API fixtures until Agent 1 endpoints land.

### Deliverables

#### C1. Design system

-   semantic tokens;
-   typography;
-   light/dark;
-   primitives;
-   accessibility;
-   motion tokens;
-   Storybook or equivalent component playground.

#### C2. Application shell

-   navigation;
-   responsive layout;
-   command palette;
-   global loading/error states.

#### C3. Onboarding

-   GitHub connect;
-   repo selection;
-   optional resume upload;
-   sync progress.

#### C4. Evidence experience

-   explorer/list;
-   repository view;
-   Evidence Constellation graph;
-   evidence review/edit/reject/private;
-   source/provenance inspector.

#### C5. Job workspace

-   JD input;
-   requirement graph/chips;
-   Evidence Coverage Matrix;
-   gap states;
-   positioning view;
-   pipeline progress.

#### C6. Resume workspace

-   live preview;
-   template switcher;
-   Conservative/Full toggle;
-   bullet-level provenance;
-   diff view;
-   export controls.

#### C7. Applications

-   saved/application status.
-   recent analyses.
-   basic stage board/list.

#### C8. Browser extension

-   Manifest V3.
-   context menu.
-   selected-text capture.
-   page fallback.
-   authentication handoff.
-   success/error UI.
-   open-analysis action.

#### C9. E2E and visual quality

-   Playwright journeys.
-   visual regression.
-   axe accessibility checks.
-   reduced-motion tests.
-   mobile/tablet smoke tests.

### Agent 3 acceptance criteria

-   full workflow works against mocks before backend completion;
-   API calls only through generated client;
-   no duplicated domain enums;
-   keyboard-complete primary flows;
-   WCAG AA checks on primary pages;
-   Lighthouse targets on non-graph pages: Performance ≥90,
    Accessibility ≥95, Best Practices ≥95;
-   graph gracefully degrades to list view.

------------------------------------------------------------------------

# 35. Cross-Agent Interfaces

To keep all three agents productive simultaneously:

## Contract freeze rule

Any breaking change to: - entity schema; - API route; - event; - enum;
requires an ADR + migration note.

## Mock-first rule

Agent 3 receives generated/mock fixtures on Day 0 and never waits for
backend implementation.

## Repository interfaces

Agent 2 does not query SQLAlchemy directly. It uses interfaces such as:

``` python
class EvidenceRepository(Protocol):
    async def save_candidates(self, items: list[EvidenceCandidate]) -> list[Evidence]: ...
    async def hybrid_search(self, query: EvidenceQuery) -> list[EvidenceHit]: ...
```

Agent 1 supplies the implementation.

## AI task interfaces

Agent 1 does not import LLM provider code. It queues typed tasks: -
`extract_evidence` - `analyze_job` - `generate_application`

Agent 2 implements task handlers.

## Frontend

Agent 3 never hand-builds backend types. Generate from OpenAPI.

------------------------------------------------------------------------

# 36. Suggested Sprint Plan

## Sprint 0 --- 2--3 days

Shared: - scaffold; - contracts; - DB; - design tokens; - CI; - fixture
repository; - fixture JD; - mock API.

## Sprint 1 --- Foundation

**Agent 1:** GitHub auth/repo inventory/source artifacts.\
**Agent 2:** providers + JD extraction + evidence schema/extractor.\
**Agent 3:** shell + onboarding + evidence/job mocked UI.

Milestone: GitHub can be connected and a mocked evidence graph is
visible.

## Sprint 2 --- Evidence Engine

**Agent 1:** artifact selection + persistence + vectors.\
**Agent 2:** evidence extraction + hybrid retrieval + reranker.\
**Agent 3:** real Evidence Explorer/Constellation + provenance.

Milestone: repository → evidence → searchable graph.

## Sprint 3 --- Job Intelligence

**Agent 1:** Job/Requirement/Application APIs + SSE.\
**Agent 2:** requirement graph + matching + coverage + positioning.\
**Agent 3:** Job Workspace + coverage animation + gaps.

Milestone: JD → evidence-backed coverage matrix.

## Sprint 4 --- Generation

**Agent 1:** document storage + render service + run tracking.\
**Agent 2:** writer + verifier + repair + deterministic guards.\
**Agent 3:** resume workspace + provenance + diff + export.

Milestone: verified PDF generated end-to-end.

## Sprint 5 --- Zero-friction workflow

**Agent 1:** capture endpoint/auth hardening.\
**Agent 2:** latency/caching improvements.\
**Agent 3:** extension + capture handoff.

Milestone: highlight JD → right-click → analysis.

## Sprint 6 --- Portfolio-grade hardening

All: - full eval suite; - performance; - security; - accessibility; -
E2E; - docs; - demo dataset; - deployment; - architecture diagram; -
benchmark report.

------------------------------------------------------------------------

# 37. Definition of Done for V1

V1 is done only when a new user can:

1.  create an account;
2.  connect GitHub;
3.  select repositories;
4.  optionally upload a resume;
5.  see evidence automatically extracted with provenance;
6.  capture a technical JD through the extension;
7.  see structured requirements;
8.  see Strong/Partial/Gap evidence coverage;
9.  inspect exact evidence for a requirement;
10. generate a positioning strategy;
11. generate a tailored resume;
12. click a resume bullet and inspect supporting evidence;
13. be prevented from exporting unsupported factual claims;
14. generate a cover letter;
15. export a parse-validated PDF;
16. revisit the application later.

Engineering Definition of Done: - CI green; - migrations reproducible; -
no high-severity known security issue; - no plaintext provider/GitHub
tokens; - core E2E passes; - evaluation quality gates reported; -
accessible fallback for graph; - observability available for every
generation run.

------------------------------------------------------------------------

# 38. Portfolio/README Story

The repository should not market itself as another resume generator.

Recommended description:

> **ProofHire is an evidence-grounded AI career agent for software
> engineers. It converts authorized GitHub repositories into a
> provenance-aware developer evidence graph, maps job requirements to
> defensible code-derived evidence using hybrid retrieval and reranking,
> and generates verified application materials with claim-level
> citations and hallucination guards.**

README should show: 1. 20-second product GIF/video; 2. architecture
diagram; 3. right-click JD workflow; 4. Evidence Constellation; 5. claim
provenance; 6. evaluation benchmark; 7. local setup; 8. design
decisions/ADRs; 9. privacy model; 10. roadmap.

------------------------------------------------------------------------

# 39. Key Architectural Decisions to Record as ADRs

-   ADR-0001 Modular monolith + workers.
-   ADR-0002 PostgreSQL/pgvector before specialized graph/vector DB.
-   ADR-0003 Evidence is first-class domain entity.
-   ADR-0004 Every evidence node requires provenance.
-   ADR-0005 Provider-independent LLM interface.
-   ADR-0006 Hybrid retrieval + reranking.
-   ADR-0007 Deterministic fact guard after generation.
-   ADR-0008 SSE before WebSockets.
-   ADR-0009 Browser-rendered PDF + parse-back validation.
-   ADR-0010 OpenAPI-generated frontend contracts.
-   ADR-0011 Minimal-permission browser extension.
-   ADR-0012 No microservices until measured scaling need.

------------------------------------------------------------------------

# 40. Major Risks and Mitigations

## GitHub evidence can be misleading

A dependency in `package.json` does not prove deep expertise.
**Mitigation:** evidence types/strength, multiple-source corroboration,
source-quality weighting, Partial vs Strong labels.

## Repository scale/cost

Large profiles can contain millions of lines. **Mitigation:**
deterministic inventory, relevance-aware selection, content hashes,
bounded semantic extraction, incremental sync.

## Hallucinated metrics

Models love adding numbers. **Mitigation:** numeric fact guard; metrics
require source evidence or explicit user confirmation.

## Prompt injection in repository/JD text

Untrusted text may contain instructions. **Mitigation:** treat source as
data, delimit inputs, structured outputs, instruction hierarchy,
sanitizer, adversarial evals.

## Login-walled job sites

Server fetch may fail. **Mitigation:** browser-selected text is the
primary frictionless route; paste fallback.

## Graph UX becomes gimmicky

**Mitigation:** graph and table are views over identical data; every
graph insight must be actionable.

## Over-engineering

**Mitigation:** modular monolith; Postgres graph representation;
pgvector; three queues; extract services only with measured need.

------------------------------------------------------------------------

# 41. Research References

Public repositories reviewed for competitive/architecture analysis:

-   https://github.com/end1989/tailored
-   https://github.com/nikogura/resume-tailor
-   https://github.com/srbhr/Resume-Matcher
-   https://github.com/narendranathe/tailor-resume
-   https://github.com/PSR94/resume-tailor
-   https://github.com/rotsl/resume-tailor

Snapshot reflects repository information visible on 16 September 2026.
Competitor implementations can change; re-check before making future
product claims.

------------------------------------------------------------------------

# 42. Immediate Build Command for Three Agents

Give each coding agent the entire PRD, then append only its role prompt.

## Prompt for Agent 1

> You are Platform Agent. Implement only the AGENT 1 ownership and
> deliverables in Section 34. Treat Sections 12--25 and 27--31 as
> binding architecture contracts. Do not implement semantic AI prompts
> or frontend UI. Work on `agent/platform`. Before changing a shared
> contract, write an ADR and stop for integration approval. Maintain
> tests and leave the branch merge-ready.

## Prompt for Agent 2

> You are Intelligence Agent. Implement only the AGENT 2 ownership and
> deliverables in Section 34. Treat the domain/API schemas as externally
> owned contracts. Use repository interfaces instead of SQLAlchemy. Do
> not build frontend UI or GitHub OAuth. Work on `agent/intelligence`.
> Build deterministic mock-provider tests and the evaluation harness
> from the beginning. Maintain tests and leave the branch merge-ready.

## Prompt for Agent 3

> You are Experience Agent. Implement only the AGENT 3 ownership and
> deliverables in Section 34. Build against generated clients and mock
> fixtures so you never block on backend work. Do not duplicate backend
> schemas or implement AI logic. Work on `agent/experience`. Treat the
> visual and interaction requirements in Sections 10--11 and 33 as
> product requirements, including accessibility and reduced motion.
> Maintain E2E/visual tests and leave the branch merge-ready.

------------------------------------------------------------------------

# 43. Final Product Test

The canonical demo must be:

``` text
Connect GitHub
      ↓
Evidence graph builds
      ↓
Open technical job posting
      ↓
Highlight JD → right click → Send to ProofHire
      ↓
Requirement nodes appear
      ↓
Evidence paths connect to requirements
      ↓
Strong / Partial / Gap matrix
      ↓
Positioning strategy
      ↓
Generate resume
      ↓
Click bullet
      ↓
See repository/file evidence proving the claim
      ↓
Verifier passes
      ↓
Export ATS-safe PDF
```

If this flow is fast, visually memorable, technically defensible and
quantitatively evaluated, ProofHire demonstrates far more than prompt
engineering: it demonstrates data ingestion, code intelligence, RAG,
structured extraction, retrieval/reranking, LLM orchestration,
evaluation, safety/grounding, backend architecture, browser integration,
observability, document rendering and high-end frontend engineering in
one coherent product.
