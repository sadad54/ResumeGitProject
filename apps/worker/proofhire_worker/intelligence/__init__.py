"""AI intelligence tasks: evidence extraction, JD analysis, generation, verification
(Phase 2+). Owns the LLMProvider abstraction (llm_provider.py) — no provider SDK
should leak outside this package (PRD §25)."""

from proofhire_worker.intelligence.coverage import compute_coverage  # noqa: F401
from proofhire_worker.intelligence.evidence_extraction import extract_evidence  # noqa: F401
from proofhire_worker.intelligence.generation import generate_document  # noqa: F401
from proofhire_worker.intelligence.job_analysis import analyze_job  # noqa: F401
