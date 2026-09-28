"""Groq adapter. Groq's API is OpenAI-compatible, so this reuses the `openai`
SDK client pointed at Groq's base URL rather than adding a new dependency —
the real differences from OpenAIProvider are the base URL, the model
catalogue, reasoning controls, and Groq having no embeddings endpoint
(embeddings are a separate provider: `intelligence/embeddings.py`).

Responses use strict structured outputs (`json_schema`, `strict: true`):
constrained decoding, so the reply is valid JSON of the requested shape by
construction. JSON-object mode, used before, lost extraction groups to
`json_validate_failed` in the first live run.
"""

from __future__ import annotations

import json
import time
from typing import TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from proofhire_worker.intelligence.json_schema import strict_json_schema
from proofhire_worker.intelligence.llm_provider import (
    LLMProviderError,
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


def _is_json_validate_failure(exc: Exception) -> bool:
    return isinstance(exc, openai.BadRequestError) and "json_validate_failed" in str(exc)


class OutputTruncatedError(LLMProviderError):
    """The model stopped at max_tokens before finishing its answer. With a
    reasoning model this usually means reasoning consumed the budget."""


def _is_retryable(exc: Exception) -> bool:
    """Same policy as OpenAIProvider — the SDK's exception types are shared
    since Groq is accessed through the OpenAI client — except that Groq
    reports "Request too large" (the request's max_tokens exceeds a per-minute
    limit outright) as a 429, and that one can never succeed on retry."""
    if isinstance(exc, openai.RateLimitError) and "request too large" in str(exc).lower():
        return False
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
        # max_retries=0: retry policy lives in one place (retry.with_retries),
        # which logs every retry and knows which 429s can never succeed. The
        # SDK's own two silent retries multiplied every attempt by three.
        self._client = AsyncOpenAI(api_key=api_key, base_url=_BASE_URL, max_retries=0)

    async def structured_generate(
        self,
        *,
        task: str,
        messages: list[Message],
        schema: type[SchemaT],
        model_config: ModelConfig,
    ) -> StructuredResult:
        start = time.perf_counter()
        json_schema = strict_json_schema(schema)
        # The schema also goes in the prompt: its field descriptions carry
        # instructions (allowed labels, what a claim is), and nothing
        # guarantees the decoder's schema reaches the model as context.
        schema_text = json.dumps(json_schema, separators=(",", ":"))

        chat_messages = [
            {
                "role": "system",
                "content": (
                    f"{next((m.content for m in messages if m.role == 'system'), '')}\n\n"
                    f"Respond ONLY with JSON matching this schema:\n{schema_text}"
                ),
            },
            *[{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": True},
        }
        extra_body = (
            {"reasoning_effort": model_config.reasoning_effort}
            if model_config.reasoning_effort
            else None
        )

        last_error: Exception | None = None
        total_input_tokens = 0
        total_output_tokens = 0

        for attempt in range(MAX_SCHEMA_REPAIR_ATTEMPTS + 1):
            try:
                response = await with_retries(
                    lambda: self._client.chat.completions.create(
                        model=model_config.model,
                        temperature=model_config.temperature,
                        max_tokens=model_config.max_tokens,
                        response_format=response_format,
                        messages=chat_messages,
                        extra_body=extra_body,
                    ),
                    is_retryable=_is_retryable,
                    provider=self.name,
                    task=task,
                )
            except openai.BadRequestError as exc:
                # Groq's `json_validate_failed` still occurs in strict mode:
                # reproducibly for gpt-oss-20b at medium reasoning effort on a
                # 12K-character extraction prompt, and never at low effort on
                # the same prompt (measured). Degrade effort once, then give up.
                if not _is_json_validate_failure(exc) or extra_body == {"reasoning_effort": "low"}:
                    raise
                last_error = exc
                extra_body = {"reasoning_effort": "low"}
                continue
            usage = response.usage
            total_input_tokens += usage.prompt_tokens if usage else 0
            total_output_tokens += usage.completion_tokens if usage else 0

            choice = response.choices[0]
            raw = choice.message.content
            if choice.finish_reason == "length" or not raw:
                # Never read a cut-off or empty reply as "{}": for schemas whose
                # fields all have defaults that validates, and an extraction
                # group would silently report zero evidence.
                raise OutputTruncatedError(
                    f"{model_config.model} returned no complete answer for task={task!r} "
                    f"(finish_reason={choice.finish_reason!r}, "
                    f"max_tokens={model_config.max_tokens})"
                )
            try:
                parsed = schema.model_validate_json(raw)
                break
            except (ValidationError, ValueError) as exc:
                # Strict decoding guarantees the shape, not Pydantic's bounds
                # (confidence in [0, 1], for example), which the schema can't
                # express in strict mode; those go back to the model.
                last_error = exc
                chat_messages.append({"role": "assistant", "content": raw})
                chat_messages.append(
                    {
                        "role": "user",
                        "content": f"That response failed schema validation: {exc}. "
                        "Return corrected JSON only.",
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
