"""Provider-independent LLM interface (PRD §25, ADR-0005).

No domain/task code should import an OpenAI or Anthropic SDK directly — everything
goes through `LLMProvider.structured_generate` / `.embed`. This is what keeps
Phase 2+ tasks (evidence extraction, JD analysis, positioning, writing, claim
verification) swappable across providers and testable against MockLLMProvider
without hitting a real API or spending money in CI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ModelConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class UsageMetadata:
    """Attached to every structured_generate call for GenerationRun telemetry
    (PRD §29: prompt version, model, token usage, latency, cost)."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost_usd: float = 0.0


@dataclass
class StructuredResult:
    value: BaseModel
    usage: UsageMetadata


class LLMProviderError(Exception):
    pass


class SchemaValidationError(LLMProviderError):
    """Raised when the provider's output cannot be coerced into the requested
    schema after retries. Callers (e.g. the claim verifier's repair loop) should
    treat this as a hard failure, not silently proceed."""


class LLMProvider(Protocol):
    name: str

    async def structured_generate(
        self,
        *,
        task: str,
        messages: list[Message],
        schema: type[SchemaT],
        model_config: ModelConfig,
    ) -> StructuredResult: ...

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]: ...
