"""Verify every configured task model is served, and accepts the requests the
pipeline actually sends.

Two failures this has to catch before users do, both seen on Groq:
- Retired models: Groq removed llama-3.3-70b-versatile, which the deploy
  script still selected; every analysis would have failed at request time.
  The model list check asks the provider instead of trusting configuration.
- Request limits: on 2026-09-28 Groq began rejecting any qwen3.8-27b request
  whose max_tokens exceeded a new 1,000 output-tokens-per-minute cap ("Request
  too large"), which the claim verifier's 4,096 always did. A model can be
  listed and still refuse every real call. `--probe` sends one minimal
  request per distinct (model, max_tokens, reasoning effort) the tasks use,
  with the same structured-output mode, and reports refusals.

    python -m proofhire_worker.intelligence.check_models           # model list only
    python -m proofhire_worker.intelligence.check_models --probe   # + request limits

Exit 1 if anything is missing or refused. Run by the deploy script before
shipping and by the container entrypoint at start (non-fatal there: an
unreachable provider at boot shouldn't stop the API from serving everything
that doesn't need a model).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable

from proofhire_worker.intelligence.model_selection import (
    TASKS,
    config_for,
    provider_name,
    resolved_models,
)

_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def _openai_compatible_client(provider: str):
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=os.environ.get("GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY", ""),
        base_url="https://api.groq.com/openai/v1" if provider == "groq" else None,
    )


async def available_models(provider: str) -> set[str] | None:
    """None when the provider has no model list to check (mock)."""
    if provider == "mock":
        return None
    if provider in {"groq", "openai"}:
        client = _openai_compatible_client(provider)
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


Create = Callable[..., Awaitable[object]]


async def probe_limits(create: Create | None = None) -> dict[str, str]:
    """task -> refusal message, for every task whose real request shape the
    provider refuses. Only Groq's request limits are probed: its refusals
    are per-account and change without notice."""
    if provider_name() != "groq":
        return {}
    if create is None:
        create = _openai_compatible_client("groq").chat.completions.create
    refusals: dict[str, str] = {}
    by_shape: dict[tuple, list[str]] = {}
    for task in TASKS:
        config = config_for(task)
        by_shape.setdefault((config.model, config.max_tokens, config.reasoning_effort), []).append(
            task
        )
    for (model, max_tokens, effort), tasks in by_shape.items():
        try:
            await create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": 'Reply with the JSON {"ok": true}.'}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "probe", "schema": _PROBE_SCHEMA, "strict": True},
                },
                extra_body={"reasoning_effort": effort} if effort else None,
            )
        except Exception as exc:  # the message is the diagnosis
            for task in tasks:
                refusals[task] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return refusals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--probe",
        action="store_true",
        help="also send one minimal real request per distinct request shape",
    )
    args = ap.parse_args()
    provider = provider_name()
    try:
        missing = asyncio.run(missing_models())
        refused = asyncio.run(probe_limits()) if args.probe and not missing else {}
    except Exception as exc:  # network, auth — report plainly, no traceback noise
        print(f"could not reach {provider}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    for task, model in resolved_models().items():
        effort = config_for(task).reasoning_effort or "-"
        status = "MISSING" if task in missing else "REFUSED" if task in refused else "ok"
        print(f"{provider:9} {task:19} {model:24} effort={effort:6} {status}")
    for task, why in refused.items():
        print(f"  {task}: {why}", file=sys.stderr)
    return 1 if missing or refused else 0


if __name__ == "__main__":
    sys.exit(main())
