"""OpenAI adapter. Structured output via JSON mode + Pydantic validation, with a
bounded repair loop on schema-validation failure (providers differ in how
reliably they honor a requested JSON schema — PRD Phase 2 risk spike)."""

from __future__ import annotations

import json
import time
from typing import TypeVar

from openai import AsyncOpenAI
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

# Rough $/1K-token estimates for cost telemetry (PRD §29). Not billing-accurate —
# update from real usage once GenerationRun data accumulates (Phase 9 spike).
_COST_PER_1K_INPUT = {"gpt-4o": 0.0025, "gpt-4o-mini": 0.00015}
_COST_PER_1K_OUTPUT = {"gpt-4o": 0.01, "gpt-4o-mini": 0.0006}


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

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
            response = await self._client.chat.completions.create(
                model=model_config.model,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
                response_format={"type": "json_object"},
                messages=chat_messages,
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
                f"OpenAI failed to produce schema-valid output for task={task!r} "
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

    async def embed(self, texts: list[str], *, model: str = "text-embedding-3-small") -> list[list[float]]:
        response = await self._client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]
