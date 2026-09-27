"""Verify every configured task model is actually served by the provider.

Providers retire models: Groq removed llama-3.3-70b-versatile, which this
repo's deploy script still selected, and the only symptom would have been
every analysis failing at request time. This asks the provider's own model
list instead of trusting configuration.

    python -m proofhire_worker.intelligence.check_models   # exit 1 if any are missing

Run by the deploy script before shipping and by the container entrypoint at
start (non-fatal there: an unreachable provider at boot shouldn't stop the API
from serving everything that doesn't need a model).
"""

from __future__ import annotations

import asyncio
import os
import sys

from proofhire_worker.intelligence.model_selection import provider_name, resolved_models


async def available_models(provider: str) -> set[str] | None:
    """None when the provider has no model list to check (mock)."""
    if provider == "mock":
        return None
    if provider in {"groq", "openai"}:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.environ.get("GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1" if provider == "groq" else None,
        )
        return {m.id async for m in client.models.list()}
    if provider == "anthropic":
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        return {m.id async for m in client.models.list()}
    raise ValueError(f"Unknown LLM provider: {provider!r}")


async def missing_models() -> dict[str, str]:
    """task -> model id, for every configured model the provider doesn't serve."""
    available = await available_models(provider_name())
    if available is None:
        return {}
    return {task: model for task, model in resolved_models().items() if model not in available}


def main() -> int:
    provider = provider_name()
    try:
        missing = asyncio.run(missing_models())
    except Exception as exc:  # network, auth — report plainly, no traceback noise
        print(f"could not list {provider} models: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    for task, model in resolved_models().items():
        status = "MISSING" if task in missing else "ok"
        print(f"{provider:9} {task:19} {model:32} {status}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
