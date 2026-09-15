"""Anthropic adapter. Structured output via forced tool use — Anthropic's models
follow a tool's input_schema far more reliably than free-form JSON-mode prompting,
so this is the "structured output mechanism" referenced in ADR-0005 for this
provider (deliberately different from OpenAI's JSON-mode approach; both converge
on the same LLMProvider.structured_generate contract)."""

from __future__ import annotations

import time
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from proofhire_worker.intelligence.llm_provider import (
    Message,
    ModelConfig,
    SchemaValidationError,
    StructuredResult,
    UsageMetadata,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

MAX_SCHEMA_REPAIR_ATTEMPTS = 2
_TOOL_NAME = "emit_structured_output"

_COST_PER_1K_INPUT = {"claude-sonnet-5": 0.003, "claude-haiku-4-5-20251001": 0.001}
_COST_PER_1K_OUTPUT = {"claude-sonnet-5": 0.015, "claude-haiku-4-5-20251001": 0.005}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def structured_generate(
        self,
        *,
        task: str,
        messages: list[Message],
        schema: type[SchemaT],
        model_config: ModelConfig,
    ) -> StructuredResult:
        start = time.perf_counter()
        system_content = next((m.content for m in messages if m.role == "system"), "")
        conversation = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]

        tool = {
            "name": _TOOL_NAME,
            "description": f"Emit the structured result for task={task}.",
            "input_schema": schema.model_json_schema(),
        }

        last_error: Exception | None = None
        total_input_tokens = 0
        total_output_tokens = 0
        parsed: BaseModel | None = None

        for attempt in range(MAX_SCHEMA_REPAIR_ATTEMPTS + 1):
            response = await self._client.messages.create(
                model=model_config.model,
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
                system=system_content,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=conversation,
            )
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_use is None:
                last_error = SchemaValidationError("no tool_use block in response")
            else:
                try:
                    parsed = schema.model_validate(tool_use.input)
                    break
                except ValidationError as exc:
                    last_error = exc

            conversation.append({"role": "assistant", "content": response.content})
            conversation.append(
                {
                    "role": "user",
                    "content": f"That tool call failed schema validation: {last_error}. Call {_TOOL_NAME} again with corrected input.",
                }
            )
        else:
            raise SchemaValidationError(
                f"Anthropic failed to produce schema-valid output for task={task!r} "
                f"after {MAX_SCHEMA_REPAIR_ATTEMPTS + 1} attempts: {last_error}"
            )

        latency_ms = (time.perf_counter() - start) * 1000
        cost = (
            total_input_tokens / 1000 * _COST_PER_1K_INPUT.get(model_config.model, 0.0)
            + total_output_tokens / 1000 * _COST_PER_1K_OUTPUT.get(model_config.model, 0.0)
        )

        assert parsed is not None
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
        # Anthropic has no first-party embeddings endpoint. Rather than bolt on a
        # third embeddings vendor (extra API key, extra dependency) for what would
        # be a rarely-exercised path, embeddings always go through OpenAIProvider
        # regardless of LLM_DEFAULT_PROVIDER — see get_embedding_provider() in
        # provider_factory.py. This method exists only to satisfy the LLMProvider
        # Protocol; calling it directly is a caller error.
        raise NotImplementedError(
            "AnthropicProvider has no embeddings endpoint — use "
            "provider_factory.get_embedding_provider() instead of calling "
            "AnthropicProvider.embed() directly."
        )
