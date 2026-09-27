"""Selects a concrete LLMProvider based on config, without callers ever importing
a provider SDK directly (ADR-0005)."""

import os

from proofhire_worker.intelligence.embedding_cache import CachedEmbeddingProvider
from proofhire_worker.intelligence.embeddings import EmbeddingProvider, build_embedding_provider
from proofhire_worker.intelligence.llm_provider import LLMProvider
from proofhire_worker.intelligence.providers.anthropic_provider import AnthropicProvider
from proofhire_worker.intelligence.providers.groq_provider import GroqProvider
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
    if provider_name == "groq":
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        return GroqProvider(api_key)

    raise ValueError(f"Unknown LLM provider: {provider_name!r}")


def get_embedding_provider() -> EmbeddingProvider:
    """Chosen by EMBEDDING_PROVIDER, independently of LLM_DEFAULT_PROVIDER
    (ADR-0018). Defaults to the local ONNX model, so no deployment silently
    ends up with meaningless vectors: this used to fall back to hash-derived
    mock embeddings whenever OPENAI_API_KEY was unset — which is exactly the
    Groq-only deployment's configuration."""
    return CachedEmbeddingProvider(build_embedding_provider())
