"""Deterministic mock LLM provider — no network calls, no API key, no cost.

Used in unit/integration tests and local dev without provider keys configured.
Callers register a `fixture_fn` (or rely on the default schema-defaults behavior)
so tests get predictable, reviewable output instead of depending on live model
behavior. This is what keeps the rest of Phase 2+'s test suite fast and free.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from proofhire_worker.intelligence.llm_provider import (
    Message,
    ModelConfig,
    StructuredResult,
    UsageMetadata,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

FixtureFn = Callable[[str, list[Message], type[BaseModel]], BaseModel]


def _default_fixture(task: str, messages: list[Message], schema: type[BaseModel]) -> BaseModel:
    """Best-effort schema-valid default when no fixture is registered for a task —
    tries each field's type default. Tests needing realistic content should
    register a fixture for their task via MockLLMProvider(fixtures={...})."""
    return schema.model_construct()


class MockLLMProvider:
    name = "mock"

    def __init__(self, fixtures: dict[str, FixtureFn] | None = None) -> None:
        self._fixtures = fixtures or {}

    async def structured_generate(
        self,
        *,
        task: str,
        messages: list[Message],
        schema: type[SchemaT],
        model_config: ModelConfig,
    ) -> StructuredResult:
        start = time.perf_counter()
        fixture = self._fixtures.get(task, _default_fixture)
        value = fixture(task, messages, schema)
        latency_ms = (time.perf_counter() - start) * 1000
        return StructuredResult(
            value=value,
            usage=UsageMetadata(
                provider=self.name,
                model=model_config.model,
                input_tokens=sum(len(m.content) // 4 for m in messages),
                output_tokens=len(str(value)) // 4,
                latency_ms=latency_ms,
                estimated_cost_usd=0.0,
            ),
        )

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        # Deterministic pseudo-embedding: hash-based, stable across calls for the
        # same text. Dimension matches EMBEDDING_DIMENSION (the real OpenAI
        # text-embedding-3-small size) so the pgvector column works identically
        # whether or not a real OPENAI_API_KEY is configured in local dev.
        import hashlib

        from proofhire_contracts.embedding import EMBEDDING_DIMENSION

        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            # Cycle the 32-byte digest to fill EMBEDDING_DIMENSION floats.
            vectors.append([digest[i % len(digest)] / 255.0 for i in range(EMBEDDING_DIMENSION)])
        return vectors
