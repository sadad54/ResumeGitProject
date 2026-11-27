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
# its own free-tier quota (1,000 requests/day, 8,000 tokens/min, 200K
# tokens/day), so the high-volume tasks (extraction: one call per file group;
# rerank: one per requirement) run on the 20B model and leave the 120B
# model's budget for analysis, writing and verification.
#
# The verifier was on qwen/qwen3.8-27b, a different family from the writer.
# On 2026-09-28 Groq began capping that model at 1,000 output tokens per
# minute for this account and rejecting any request whose max_tokens exceeds
# it ("Request too large", measured) — a verification call can't fit, so it
# now runs on the 120B model: a separate call with the verifier prompt only,
# alongside the deterministic fact guard, which needs no model at all.
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "groq": {
        "*": "openai/gpt-oss-120b",
        "evidence_extract": "openai/gpt-oss-20b",
        "rerank": "openai/gpt-oss-20b",
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


# Reasoning effort for Groq's reasoning models, per task. Low where the task
# is extraction or a short judgement: on the real extraction prompt (12K
# characters) gpt-oss-20b returned 5 items in 2 s at low effort and failed
# with `json_validate_failed` at the default (medium), reproducibly; JD
# analysis found the same 12 requirements at either. Writing and verification
# keep the default. Override with LLM_REASONING_EFFORT_<TASK>.
REASONING_EFFORT: dict[str, dict[str, str]] = {
    "groq": {"evidence_extract": "low", "jd_extract": "low", "rerank": "low"},
}


def reasoning_effort_for(task: str) -> str | None:
    return os.environ.get(f"LLM_REASONING_EFFORT_{task.upper()}") or REASONING_EFFORT.get(
        provider_name(), {}
    ).get(task)


def config_for(task: str, **overrides) -> ModelConfig:
    overrides.setdefault("reasoning_effort", reasoning_effort_for(task))
    return ModelConfig(model=model_for(task), **overrides)


def resolved_models() -> dict[str, str]:
    return {task: model_for(task) for task in TASKS}
