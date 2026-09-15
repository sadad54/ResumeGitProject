"""AI intelligence tasks: evidence extraction, JD analysis, generation, verification
(Phase 2+). Owns the LLMProvider abstraction (llm_provider.py) — no provider SDK
should leak outside this package (PRD §25)."""

from proofhire_worker.intelligence.evidence_extraction import extract_evidence  # noqa: F401
