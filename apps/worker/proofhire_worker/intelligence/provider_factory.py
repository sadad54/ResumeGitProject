"""Selects a concrete LLMProvider based on config, without callers ever importing
a provider SDK directly (ADR-0005)."""

import os

from proofhire_worker.intelligence.embedding_cache import CachedEmbeddingProvider
from proofhire_worker.intelligence.llm_provider import LLMProvider
from proofhire_worker.intelligence.providers.anthropic_provider import AnthropicProvider
from proofhire_worker.intelligence.providers.mock_provider import MockLLMProvider
from proofhire_worker.intelligence.providers.openai_provider import OpenAIProvider


def get_provider(name: str | None = None) -> LLMProvider:
    provider_name = name or os.environ.get("LLM_DEFAULT_PROVIDER", "anthropic")

    if provider_name == "mock":
        return MockLLMProvider()
    if provider_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return OpenAIProvider(api_key)
    if provider_name == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(api_key)

    raise ValueError(f"Unknown LLM provider: {provider_name!r}")


def get_embedding_provider() -> LLMProvider:
    """Embeddings always go through OpenAI regardless of LLM_DEFAULT_PROVIDER —
    Anthropic has no first-party embeddings endpoint (see AnthropicProvider.embed).
    Falls back to the mock provider if no OpenAI key is configured, so local dev
    without any API keys still exercises the full pipeline deterministically."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    inner: LLMProvider = OpenAIProvider(api_key) if api_key else MockLLMProvider()
    return CachedEmbeddingProvider(inner)
