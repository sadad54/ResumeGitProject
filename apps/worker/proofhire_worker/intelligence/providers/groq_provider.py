"""Groq adapter. Groq's API is OpenAI-compatible (same request/response shape,
including JSON mode), so this reuses the `openai` SDK client pointed at Groq's
base URL rather than adding a new dependency — the only real differences from
OpenAIProvider are the base URL, the model catalogue, and Groq having no
embeddings endpoint (see `embed` below and `provider_factory.get_embedding_provider`)."""

from __future__ import annotations

import json
import time
from typing import TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from proofhire_worker.intelligence.llm_provider import (
    Message,
    ModelConfig,
    SchemaValidationError,
    StructuredResult,
    UsageMetadata,
)
from proofhire_worker.intelligence.retry import with_retries

SchemaT = TypeVar("SchemaT", bound=BaseModel)

MAX_SCHEMA_REPAIR_ATTEMPTS = 2
_BASE_URL = "https://api.groq.com/openai/v1"


def _is_retryable(exc: Exception) -> bool:
    """Same policy as OpenAIProvider — the SDK's exception types are shared
    since Groq is accessed through the OpenAI client."""
    if isinstance(
        exc,
        openai.RateLimitError | openai.APITimeoutError | openai.APIConnectionError,
    ):
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status >= 500


# Groq's free tier has no per-token charge; kept at 0.0 rather than fabricated
# figures. Update once Groq bills these models for real (checklist §29 cost
# telemetry note).
_COST_PER_1K_INPUT: dict[str, float] = {}
_COST_PER_1K_OUTPUT: dict[str, float] = {}


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=_BASE_URL)

    async def structured_generate(
        self,
        *,
        task: str,
        messages: list[Message],
        schema: type[SchemaT],
        model_config: ModelConfig,
    ) -> StructuredResult:
        start = time.perf_counter()
        schema_json = json.dumps(schema.model_json_schema())

        chat_messages = [
            {
                "role": "system",
                "content": (
                    f"{next((m.content for m in messages if m.role == 'system'), '')}\n\n"
                    f"Respond ONLY with JSON matching this schema:\n{schema_json}"
                ),
            },
            *[{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
        ]

        last_error: Exception | None = None
        total_input_tokens = 0
        total_output_tokens = 0

        for attempt in range(MAX_SCHEMA_REPAIR_ATTEMPTS + 1):
            response = await with_retries(
                lambda: self._client.chat.completions.create(
                    model=model_config.model,
                    temperature=model_config.temperature,
                    max_tokens=model_config.max_tokens,
                    response_format={"type": "json_object"},
                    messages=chat_messages,
                ),
                is_retryable=_is_retryable,
                provider=self.name,
                task=task,
            )
            usage = response.usage
            total_input_tokens += usage.prompt_tokens if usage else 0
            total_output_tokens += usage.completion_tokens if usage else 0

            raw = response.choices[0].message.content or "{}"
            try:
                parsed = schema.model_validate_json(raw)
                break
            except (ValidationError, ValueError) as exc:
                last_error = exc
                chat_messages.append({"role": "assistant", "content": raw})
                chat_messages.append(
                    {
                        "role": "user",
                        "content": f"That response failed schema validation: {exc}. Return corrected JSON only.",
                    }
                )
        else:
            raise SchemaValidationError(
                f"Groq failed to produce schema-valid output for task={task!r} "
                f"after {MAX_SCHEMA_REPAIR_ATTEMPTS + 1} attempts: {last_error}"
            )

        latency_ms = (time.perf_counter() - start) * 1000
        cost = (
            total_input_tokens / 1000 * _COST_PER_1K_INPUT.get(model_config.model, 0.0)
            + total_output_tokens / 1000 * _COST_PER_1K_OUTPUT.get(model_config.model, 0.0)
        )

        return StructuredResult(
            value=parsed,
            usage=UsageMetadata(
                provider=self.name,
                model=model_config.model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                latency_ms=latency_ms,
                estimated_cost_usd=cost,
            ),
        )

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        # Groq has no embeddings endpoint. Embeddings always go through
        # OpenAIProvider (or the mock provider) regardless of LLM_DEFAULT_PROVIDER
        # — see provider_factory.get_embedding_provider(). This method exists
        # only to satisfy the LLMProvider Protocol; calling it directly is a
        # caller error.
        raise NotImplementedError(
            "GroqProvider has no embeddings endpoint — use "
            "provider_factory.get_embedding_provider() instead of calling "
            "GroqProvider.embed() directly."
        )
