# packages/prompts

Versioned prompt definitions (PRD §25): `jd_extract:v1`, `evidence_extract:v1`,
`rerank:v1`, `position:v1`, `resume_write:v1`, `claim_verify:v1`.

Populated starting Phase 2, alongside the LLM provider abstraction in
`apps/worker/proofhire_worker/intelligence/llm_provider.py`. Every `GenerationRun`
record stores which prompt versions were used (PRD §13, §29).
