"""Per-task model selection (PRD §25, checklist §7 "models configurable per task").

Each pipeline task can run on its own model, chosen by environment variable,
so the cheap high-volume tasks (rerank runs once per requirement; extraction
runs once per file group) can use a smaller model than the writer without a
code change, and either provider's model can be swapped in.

Resolution order for task `rerank`: `LLM_MODEL_RERANK`, then
`LLM_MODEL_DEFAULT`, then the default for the configured provider
(LLM_DEFAULT_PROVIDER). Task names match the `task=` argument passed to
`structured_generate`, which is also what appears in the `llm_call_completed`
log event, so a dashboard can attribute cost per (task, model) without
further wiring.

Defaults are per provider because model ids are: the previous single
default ("claude-sonnet-5") was sent to Groq whenever no override was set,
and the deploy script's Groq override (llama-3.3-70b-versatile) had been
retired by Groq — both fail every call. `check_models` verifies the resolved
ids against the provider's live model list at deploy and worker start.
"""

from __future__ import annotations

import os

from proofhire_worker.intelligence.llm_provider import ModelConfig

TASKS = (
    "evidence_extract",
    "jd_extract",
    "rerank",
    "position",
    "resume_write",
    "cover_letter_write",
    "claim_verify",
)

# Groq: verified against GET /openai/v1/models on 2026-09-27. Each model has
# its own free-tier quota (1,000 requests/day, 8,000 tokens/min at the time),
# so spreading tasks across three models triples usable throughput. The
# verifier runs on a different model family than the writer, so the two are
# less likely to share a blind spot.
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "groq": {
        "*": "openai/gpt-oss-120b",
        "evidence_extract": "openai/gpt-oss-20b",
        "rerank": "openai/gpt-oss-20b",
        "claim_verify": "qwen/qwen3.8-27b",
    },
    "anthropic": {"*": "claude-sonnet-5"},
    "openai": {"*": "gpt-4o-mini"},
    "mock": {"*": "mock"},
}

# Kept for callers/tests that referenced the old single default.
DEFAULT_MODEL = PROVIDER_DEFAULTS["anthropic"]["*"]


def provider_name() -> str:
    return os.environ.get("LLM_DEFAULT_PROVIDER", "anthropic")


def model_for(task: str) -> str:
    defaults = PROVIDER_DEFAULTS.get(provider_name(), PROVIDER_DEFAULTS["anthropic"])
    return (
        os.environ.get(f"LLM_MODEL_{task.upper()}")
        or os.environ.get("LLM_MODEL_DEFAULT")
        or defaults.get(task)
        or defaults["*"]
    )


def config_for(task: str, **overrides) -> ModelConfig:
    return ModelConfig(model=model_for(task), **overrides)


def resolved_models() -> dict[str, str]:
    return {task: model_for(task) for task in TASKS}
