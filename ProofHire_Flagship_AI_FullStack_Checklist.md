# ProofHire --- Flagship AI Engineering + Full-Stack Resume Readiness Checklist

Use this checklist before presenting ProofHire as a flagship AI
Engineering and/or Full-Stack Development project.

## Track A --- Flagship AI Engineering

### 1. Repository Intelligence

-   [ ] GitHub OAuth/App integration works with real repositories
-   [ ] Repository tree is analyzed automatically
-   [ ] Relevant files are selected instead of blindly embedding
    everything
-   [ ] Dependency manifests, Docker, CI/CD, Kubernetes/IaC and tests
    are analyzed
-   [ ] ML/model infrastructure is detected
-   [ ] README/documentation evidence is extracted
-   [ ] Generated/vendor/irrelevant files are excluded
-   [ ] Secrets and credential files are excluded
-   [ ] Repository changes trigger incremental reprocessing

**Gate:** Given an unfamiliar repository, ProofHire can automatically
produce a defensible technical profile.

### 2. Developer Evidence Graph

-   [ ] Repository, SourceArtifact, Evidence and Skill entities
-   [ ] Provenance relationships
-   [ ] Confidence scores and evidence types
-   [ ] Candidate/confirmed/rejected/stale lifecycle
-   [ ] Multiple sources can support one evidence item
-   [ ] Evidence can support multiple JD requirements
-   [ ] Generated claims link back to evidence
-   [ ] Evidence retains commit SHA/content hash
-   [ ] Evidence updates when repository contents change

Every evidence object should answer: **What do we think the developer
did? Why? Where is the proof? How confident are we?**

### 3. JD Intelligence

-   [ ] Extract role, company and seniority
-   [ ] Extract responsibilities
-   [ ] Separate required and preferred qualifications
-   [ ] Extract technologies and domain requirements
-   [ ] Normalize equivalent terminology
-   [ ] Merge duplicate requirements
-   [ ] Preserve original JD text
-   [ ] Assign requirement importance
-   [ ] Structured validated output
-   [ ] Company marketing copy is not mistaken for candidate
    requirements

### 4. Retrieval + Reranking

-   [ ] Lexical retrieval
-   [ ] Vector retrieval
-   [ ] Skill/entity matching
-   [ ] Metadata filtering
-   [ ] Candidate fusion
-   [ ] Semantic reranking
-   [ ] Strong / Partial / Gap classification
-   [ ] Human-labelled retrieval benchmark
-   [ ] Recall@K measured
-   [ ] MRR and/or nDCG measured

### 5. Grounded Generation

-   [ ] Positioning planner
-   [ ] Evidence selector
-   [ ] Resume writer
-   [ ] Cover-letter writer
-   [ ] Structured outputs
-   [ ] Conservative and Full tailoring modes
-   [ ] Immutable profile facts
-   [ ] Metrics require evidence
-   [ ] Skills are never added solely because they occur in the JD
-   [ ] Prompt versioning
-   [ ] Generation metadata persisted

### 6. Claim-Level Verification

-   [ ] Atomic claim decomposition
-   [ ] Independent verifier stage
-   [ ] Evidence IDs attached to claims
-   [ ] Support confidence
-   [ ] Deterministic numeric validation
-   [ ] Employer/date/title validation
-   [ ] Unsupported claims blocked
-   [ ] Contradiction detection
-   [ ] Bounded repair loop
-   [ ] Unresolved claims removed instead of hallucinated

Pipeline:
`Generated bullet → atomic claims → evidence retrieval → verification → Supported / Partial / Unsupported / Contradictory`

### 7. Multi-Model Architecture

-   [ ] Provider abstraction
-   [ ] OpenAI adapter
-   [ ] Anthropic adapter
-   [ ] Mock provider
-   [ ] Models configurable per task
-   [ ] Structured-output validation
-   [ ] Retry and rate-limit handling
-   [ ] Token accounting
-   [ ] Latency tracking
-   [ ] Cost tracking
-   [ ] Domain logic does not directly depend on vendor SDKs

### 8. Evaluation Framework --- Non-Negotiable

Benchmark: - \[ \] 100+ technical JDs - \[ \] SWE, AI Engineering, ML
Engineering, Data Science, Data Engineering and MLOps/DevOps - \[ \]
Manually labelled requirements - \[ \] Manually labelled evidence
matches - \[ \] Known hallucination traps

Measure: - \[ \] Requirement precision / recall / F1 - \[ \] Recall@K -
\[ \] MRR - \[ \] nDCG - \[ \] Strong/Partial classification accuracy -
\[ \] Unsupported-claim rate - \[ \] Contradiction rate - \[ \] Evidence
citation precision - \[ \] Latency - \[ \] Tokens/run - \[ \]
Cost/application

**AI flagship gate:** You should be able to report real measured
benchmark results, not subjective claims that the system is accurate.

------------------------------------------------------------------------

## Track B --- Flagship Full-Stack / SWE

### 9. Production Frontend

-   [ ] Next.js + React + TypeScript
-   [ ] Proper server/client boundaries
-   [ ] TanStack Query or equivalent
-   [ ] Generated typed API client
-   [ ] Responsive desktop/tablet/mobile
-   [ ] Dark/light mode
-   [ ] Robust loading, error and empty states
-   [ ] Optimistic UI where appropriate
-   [ ] URL-addressable workspaces
-   [ ] Keyboard navigation and command palette
-   [ ] Accessible forms
-   [ ] WCAG AA primary workflows
-   [ ] Reduced-motion support

### 10. Signature Frontend Engineering

-   [ ] Interactive Evidence Constellation
-   [ ] Graph zoom/pan/search
-   [ ] JD requirement overlay
-   [ ] Animated evidence matching
-   [ ] Graph → coverage transition
-   [ ] Provenance rail
-   [ ] Resume live preview
-   [ ] Resume diff viewer
-   [ ] Interactive requirement matrix
-   [ ] Streaming pipeline status
-   [ ] Skeleton states and meaningful microinteractions
-   [ ] Virtualized rendering where necessary
-   [ ] Accessible non-graph equivalent

### 11. Backend Engineering

-   [ ] FastAPI + Pydantic v2 + SQLAlchemy
-   [ ] PostgreSQL + pgvector
-   [ ] Redis
-   [ ] Alembic migrations
-   [ ] Background workers
-   [ ] Object storage
-   [ ] SSE streaming
-   [ ] Pagination and filtering
-   [ ] Idempotency and retries
-   [ ] Rate limiting and caching
-   [ ] Transaction handling
-   [ ] API versioning
-   [ ] Structured errors
-   [ ] OpenAPI
-   [ ] Automatically generated TypeScript client

### 12. Asynchronous Architecture

-   [ ] Background job queue
-   [ ] Durable jobs
-   [ ] Retries with exponential backoff
-   [ ] Idempotency
-   [ ] Job status and progress events
-   [ ] Failure recovery
-   [ ] Cancellation where appropriate
-   [ ] Concurrency control
-   [ ] Separate ingest / AI / render workloads

### 13. Database Engineering

-   [ ] Normalized relational model
-   [ ] Migrations, foreign keys and unique constraints
-   [ ] Appropriate relational/vector indexes
-   [ ] Evidence graph edges
-   [ ] Cascade strategy
-   [ ] Soft/hard deletion policy
-   [ ] Audit timestamps
-   [ ] Content hashes
-   [ ] Concurrency handling where needed
-   [ ] EXPLAIN ANALYZE important queries
-   [ ] Benchmark queries before/after indexing

### 14. Authentication + Authorization

-   [ ] Real application auth
-   [ ] GitHub OAuth
-   [ ] Protected endpoints
-   [ ] Per-user ownership
-   [ ] Private-repository authorization
-   [ ] Secure sessions
-   [ ] Token rotation/revocation
-   [ ] Encrypted GitHub credentials
-   [ ] Logout, account deletion and GitHub disconnect

### 15. Browser Extension

-   [ ] Manifest V3 + TypeScript
-   [ ] Context menu
-   [ ] Selected-text extraction
-   [ ] Active-page metadata
-   [ ] Authentication handoff
-   [ ] Secure extension ↔ API communication
-   [ ] Minimal permissions
-   [ ] Failure/loading/success states
-   [ ] Open Analysis action

**Canonical UX:** Highlight JD → right-click → **Send to ProofHire**.

### 16. Document Engineering

-   [ ] Structured resume representation
-   [ ] HTML + PDF renderer
-   [ ] Multiple templates
-   [ ] A4 + Letter
-   [ ] Deterministic page breaking
-   [ ] Selectable PDF text
-   [ ] Plain-text export
-   [ ] PDF parse-back
-   [ ] Overflow detection
-   [ ] Rendering regression tests

### 17. Security

-   [ ] Secret scanning before ingestion
-   [ ] `.env`, credentials and private keys excluded
-   [ ] OAuth tokens encrypted
-   [ ] Only necessary source snippets reach LLMs
-   [ ] Raw private code excluded from logs
-   [ ] Signed object-storage URLs
-   [ ] CSRF/XSS/CSP protections
-   [ ] Input validation and rate limiting
-   [ ] Secure extension messaging
-   [ ] Dependency/container scanning
-   [ ] Prompt-injection tests

### 18. Testing

-   [ ] Backend unit tests
-   [ ] Frontend component tests
-   [ ] Database integration tests
-   [ ] API contract tests
-   [ ] Worker tests
-   [ ] Retrieval and AI-evaluation tests
-   [ ] Extension tests
-   [ ] Accessibility tests
-   [ ] Visual regression tests
-   [ ] Playwright E2E
-   [ ] PDF regression tests
-   [ ] Mocked LLM tests
-   [ ] Adversarial tests
-   [ ] CI test reports

------------------------------------------------------------------------

## Track C --- Production / Systems Credibility

-   [ ] Dockerized development and production
-   [ ] GitHub Actions
-   [ ] Preview, staging and production deployments
-   [ ] Automated DB migrations
-   [ ] Health/readiness endpoints
-   [ ] OpenTelemetry
-   [ ] Structured logs
-   [ ] Error monitoring
-   [ ] API → worker → LLM tracing
-   [ ] Latency/token/cost/queue dashboards
-   [ ] Rollback and backup strategy
-   [ ] Environment separation

### Load Testing

-   [ ] 10 concurrent users
-   [ ] 50 concurrent users
-   [ ] 100 concurrent users
-   [ ] 250+ concurrent users
-   [ ] Identify bottleneck
-   [ ] Optimize bottleneck
-   [ ] Rerun benchmark
-   [ ] Document measured improvement

Report workload, failure rate, p95 latency, concurrency and
machine/environment context.

------------------------------------------------------------------------

## Track D --- Metrics to Instrument Before Resume Writing

### AI

-   [ ] JDs evaluated
-   [ ] Labelled requirements
-   [ ] Extraction F1
-   [ ] Recall@5
-   [ ] nDCG@5
-   [ ] Unsupported-claim rate
-   [ ] Verifier catch rate

### Systems

-   [ ] Repositories/source files processed
-   [ ] Evidence nodes generated
-   [ ] Incremental-sync reduction
-   [ ] API p95
-   [ ] Generation p95
-   [ ] Concurrent users tested
-   [ ] Failure rate
-   [ ] Queue throughput

### Cost

-   [ ] Tokens/repository
-   [ ] Tokens/application
-   [ ] Cost/repository
-   [ ] Cost/application
-   [ ] Cache savings

### Frontend

-   [ ] Lighthouse performance/accessibility
-   [ ] Initial JS payload
-   [ ] Graph FPS at 100/500/1,000 nodes
-   [ ] LCP
-   [ ] INP
-   [ ] CLS

------------------------------------------------------------------------

# Final Resume Gates

## AI Engineering Flagship

-   [ ] Real GitHub ingestion
-   [ ] Persistent Evidence Graph
-   [ ] Hybrid retrieval + reranking
-   [ ] Claim-level provenance
-   [ ] Independent verification
-   [ ] Hallucination guard
-   [ ] Quantitative evaluation dataset
-   [ ] Measured retrieval performance
-   [ ] Measured generation grounding
-   [ ] Production deployment

## Full-Stack / SWE Flagship

-   [ ] Polished Next.js/React/TypeScript app
-   [ ] FastAPI backend
-   [ ] Real PostgreSQL schema
-   [ ] Redis/background processing
-   [ ] GitHub OAuth
-   [ ] Browser extension
-   [ ] SSE/realtime progress
-   [ ] Object storage
-   [ ] Generated typed API client
-   [ ] Responsive + accessible UI
-   [ ] Substantial automated tests
-   [ ] CI/CD
-   [ ] Production deployment
-   [ ] Observability
-   [ ] Security controls
-   [ ] Measured load/performance

## Flagship on BOTH Resumes --- Final Gate

The real end-to-end flow must work:

`Real user → GitHub OAuth → repository ingestion → Developer Evidence Graph → browser extension → real JD → requirement extraction → hybrid retrieval + reranking → Evidence Coverage Matrix → grounded generation → claim verification → interactive provenance → PDF rendering → parse-back validation → export`

And it must include: - \[ \] Real integrations rather than mocked middle
stages - \[ \] Automated tests - \[ \] Quantitative AI evaluation - \[
\] Performance measurements - \[ \] Production deployment - \[ \]
Security controls - \[ \] Observability - \[ \] Polished demo

------------------------------------------------------------------------

# Portfolio Positioning

  Project               Primary signal
  --------------------- -----------------------------
  **ProofHire**         AI Engineering + Full Stack
  **Driftline**         ML Engineering + MLOps
  **SAFE-RAG**          LLM Evaluation + Research
  **Text-to-SQL**       Applied AI Research
  **InterviewPilot**    Applied AI Product
  **Freight Rate ML**   Classical ML

For an **AI Engineering resume**, emphasize ProofHire's evidence graph,
RAG/retrieval, reranking, grounded generation, claim verification,
evaluation, latency and cost.

For a **Full-Stack/SWE resume**, emphasize the browser extension,
Next.js UX, FastAPI async architecture, PostgreSQL/pgvector,
Redis/workers, typed API contracts, auth/security, testing, CI/CD and
deployment/performance.

The goal is one genuine system supporting two materially different,
truthful project narratives depending on the target role.
