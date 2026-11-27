"""Embedding providers (ADR-0018).

Separate from `LLMProvider` on purpose: generation providers and embedding
providers are chosen independently (Groq and Anthropic have no embeddings
endpoint at all), and a vector is only comparable to vectors made by the same
model. So every provider here carries a `model_id`, and every stored vector
records it (`evidence.embedding_model`); retrieval never compares across ids.

- ``local`` (default): BAAI/bge-small-en-v1.5 through ONNX Runtime on CPU,
  via fastembed. No API key, no per-call cost, 384-d; ~9 ms per text in a warm
  batch (docs/product/metrics/embedding-model.json). This
  replaced a silent fallback where, without an OpenAI key, "embeddings" were
  SHA-256 bytes — vectors with no semantic content at all.
- ``openai``: text-embedding-3-small asked for EMBEDDING_DIMENSION dims
  (Matryoshka truncation), so it fits the same column.
- ``mock``: hash-derived, deterministic, zero-cost. Tests only: it carries no
  meaning, and the deployment config check warns if it is selected.

Selected by EMBEDDING_PROVIDER; EMBEDDING_MODEL overrides the model name.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import threading
from pathlib import Path
from typing import Literal, Protocol

from proofhire_contracts.embedding import (
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
)

logger = logging.getLogger(__name__)

InputType = Literal["document", "query"]

# bge models were trained with this instruction on the *query* side of
# asymmetric retrieval (short query -> longer passage). fastembed's
# query_embed does not add it for bge-small (checked: identical vectors), so
# it is applied here, behind EMBEDDING_QUERY_INSTRUCTION, and measured in the
# retrieval benchmark rather than assumed to help.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingProvider(Protocol):
    model_id: str
    dimension: int

    async def embed(
        self, texts: list[str], *, input_type: InputType = "document"
    ) -> list[list[float]]: ...


def evidence_embedding_text(title: str, normalized_claim: str, description: str) -> str:
    """The one definition of what an evidence item's vector represents, shared
    by extraction and the re-embedding backfill so both produce the same
    vector for the same row."""
    return f"{title}. {normalized_claim} {description}".strip()


# --- local (ONNX) --------------------------------------------------------

_local_models: dict[tuple[str, str], object] = {}
_local_lock = threading.Lock()


def default_cache_dir() -> str:
    # fastembed defaults to the system temp dir, which containers and some
    # hosts wipe; an explicit, stable location lets the image bake the model in.
    return os.environ.get("EMBEDDING_CACHE_DIR") or str(
        Path.home() / ".cache" / "proofhire" / "fastembed"
    )


class LocalEmbeddingProvider:
    """One ONNX session per (model, cache dir) per process: loading costs
    seconds, so it happens once and every task after that reuses it."""

    def __init__(
        self,
        model_name: str = DEFAULT_LOCAL_EMBEDDING_MODEL,
        *,
        cache_dir: str | None = None,
        query_instruction: bool = False,
    ) -> None:
        self.model_id = model_name
        self.dimension = EMBEDDING_DIMENSION
        self._cache_dir = cache_dir or default_cache_dir()
        self._query_prefix = (
            BGE_QUERY_INSTRUCTION if query_instruction and "bge" in model_name.lower() else ""
        )

    def _model(self):
        key = (self.model_id, self._cache_dir)
        with _local_lock:
            model = _local_models.get(key)
            if model is None:
                from fastembed import TextEmbedding

                described = {
                    m["model"]: m for m in TextEmbedding.list_supported_models()
                }.get(self.model_id)
                if described is not None and described.get("dim") != EMBEDDING_DIMENSION:
                    raise ValueError(
                        f"{self.model_id} produces {described.get('dim')}-d vectors; the "
                        f"evidence.embedding column is {EMBEDDING_DIMENSION}-d"
                    )
                model = TextEmbedding(self.model_id, cache_dir=self._cache_dir)
                _local_models[key] = model
                logger.info("embedding_model_loaded", extra={"model": self.model_id})
            return model

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        model = self._model()
        # onnxruntime sessions are thread-safe, but serialising keeps a burst
        # of worker threads from oversubscribing the CPU with intra-op threads.
        with _local_lock:
            return [vector.tolist() for vector in model.embed(texts, batch_size=64)]

    async def embed(
        self, texts: list[str], *, input_type: InputType = "document"
    ) -> list[list[float]]:
        if not texts:
            return []
        if input_type == "query" and self._query_prefix:
            texts = [self._query_prefix + t for t in texts]
        return await asyncio.to_thread(self._embed_sync, texts)


# --- OpenAI --------------------------------------------------------------


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str = DEFAULT_OPENAI_EMBEDDING_MODEL) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model_name = model_name
        self.dimension = EMBEDDING_DIMENSION
        # The dimension is part of the identity: text-embedding-3-small at 384
        # dims and at 1536 dims are different vector spaces.
        self.model_id = f"{model_name}@{EMBEDDING_DIMENSION}"

    async def embed(
        self, texts: list[str], *, input_type: InputType = "document"
    ) -> list[list[float]]:
        if not texts:
            return []
        from proofhire_worker.intelligence.providers.openai_provider import _is_retryable
        from proofhire_worker.intelligence.retry import with_retries

        response = await with_retries(
            lambda: self._client.embeddings.create(
                model=self._model_name, input=texts, dimensions=EMBEDDING_DIMENSION
            ),
            is_retryable=_is_retryable,
            provider="openai",
            task="embed",
        )
        return [item.embedding for item in response.data]


# --- mock ----------------------------------------------------------------


class MockEmbeddingProvider:
    """Deterministic and meaningless — for tests that need *a* vector, never
    for anything that ranks. Centred and L2-normalised so it at least behaves
    like a real embedding geometrically (the old version was all-positive,
    which made every pair of vectors look ~75% similar)."""

    model_id = "mock-sha256"
    dimension = EMBEDDING_DIMENSION

    async def embed(
        self, texts: list[str], *, input_type: InputType = "document"
    ) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            raw = [(digest[i % len(digest)] / 255.0) - 0.5 for i in range(self.dimension)]
            norm = math.sqrt(sum(v * v for v in raw)) or 1.0
            vectors.append([v / norm for v in raw])
        return vectors


# --- selection -----------------------------------------------------------


def embedding_provider_name() -> str:
    return os.environ.get("EMBEDDING_PROVIDER", "local")


def build_embedding_provider(name: str | None = None) -> EmbeddingProvider:
    name = name or embedding_provider_name()
    override = os.environ.get("EMBEDDING_MODEL") or None
    if name == "local":
        return LocalEmbeddingProvider(
            override or DEFAULT_LOCAL_EMBEDDING_MODEL,
            query_instruction=os.environ.get("EMBEDDING_QUERY_INSTRUCTION", "0") == "1",
        )
    if name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set")
        return OpenAIEmbeddingProvider(api_key, override or DEFAULT_OPENAI_EMBEDDING_MODEL)
    if name == "mock":
        return MockEmbeddingProvider()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {name!r}")
