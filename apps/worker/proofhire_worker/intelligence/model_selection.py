"""Per-task model selection (PRD §25, checklist §7 "models configurable per task").

Each pipeline task can run on its own model, chosen by environment variable,
so the cheap high-volume tasks (rerank runs once per requirement; extraction
runs once per file group) can use a smaller model than the writer without a
code change, and either provider's model can be swapped in.

Resolution order for task `rerank`: `LLM_MODEL_RERANK`, then
`LLM_MODEL_DEFAULT`, then the built-in default. Task names match the `task=`
argument passed to `structured_generate`, which is also what appears in the
`llm_call_completed` log event, so a dashboard can attribute cost per
(task, model) without further wiring.
"""

from __future__ import annotations

import os

from proofhire_worker.intelligence.llm_provider import ModelConfig

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

TASKS = (
    "evidence_extract",
    "jd_extract",
    "rerank",
    "position",
    "resume_write",
    "cover_letter_write",
    "claim_verify",
)


def model_for(task: str) -> str:
    return (
        os.environ.get(f"LLM_MODEL_{task.upper()}")
        or os.environ.get("LLM_MODEL_DEFAULT")
        or DEFAULT_MODEL
    )


def config_for(task: str, **overrides) -> ModelConfig:
    return ModelConfig(model=model_for(task), **overrides)


def embedding_model() -> str:
    return os.environ.get("LLM_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
