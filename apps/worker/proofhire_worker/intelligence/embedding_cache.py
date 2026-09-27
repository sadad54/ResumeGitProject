"""Content-hash embedding cache (PRD §28, checklist §11.10 "caching" and
Track D "cache savings").

Embeddings are deterministic for a given (model, input type, text), and the
same texts recur: every coverage run re-embeds each requirement, re-analysing
a job re-embeds the same requirement texts, and evidence re-extraction after
an incremental sync re-embeds unchanged evidence. With a paid provider each
of those is a billed call; with the local model it is CPU time.

Keyed by sha256(model_id, input_type, text) in Redis with a 30-day TTL. The
input type is part of the key because a query-side vector may carry an
instruction prefix and differ from the document-side vector of the same text.
Misses are batched into one underlying call so the cache never makes a cold
path slower than before. Hits/misses are logged per call (`embedding_cache`)
so the dashboards in infra/observability can report the saving rather than
it being asserted.

Uses a fresh client per call because worker tasks run under a new event loop
each time (see proofhire_worker/db.py); a cached client would be bound to a
dead loop.
"""

from __future__ import annotations

import hashlib
import json
import logging

import redis.asyncio as aioredis

from proofhire_api.config import get_settings
from proofhire_worker.intelligence.embeddings import EmbeddingProvider, InputType

logger = logging.getLogger(__name__)

TTL_SECONDS = 30 * 24 * 3600


def _key(model_id: str, input_type: str, text: str) -> str:
    digest = hashlib.sha256(f"{model_id}\x00{input_type}\x00{text}".encode()).hexdigest()
    return f"embedding:{digest}"


class CachedEmbeddingProvider:
    """Wraps any EmbeddingProvider; same identity, cached `embed`."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner
        self.model_id = inner.model_id
        self.dimension = inner.dimension

    async def embed(
        self, texts: list[str], *, input_type: InputType = "document"
    ) -> list[list[float]]:
        if not texts:
            return []
        keys = [_key(self.model_id, input_type, t) for t in texts]
        client = aioredis.from_url(get_settings().redis_url)
        try:
            try:
                cached = await client.mget(keys)
            except Exception:
                # Cache unavailable: behave exactly as if it didn't exist.
                logger.warning("embedding_cache_unavailable")
                return await self._inner.embed(texts, input_type=input_type)

            results: list[list[float] | None] = [json.loads(c) if c else None for c in cached]
            miss_indices = [i for i, r in enumerate(results) if r is None]

            if miss_indices:
                fresh = await self._inner.embed(
                    [texts[i] for i in miss_indices], input_type=input_type
                )
                pipe = client.pipeline()
                for i, vector in zip(miss_indices, fresh, strict=True):
                    results[i] = vector
                    pipe.set(keys[i], json.dumps(vector), ex=TTL_SECONDS)
                try:
                    await pipe.execute()
                except Exception:
                    logger.warning("embedding_cache_write_failed")

            logger.info(
                "embedding_cache",
                extra={
                    "model": self.model_id,
                    "input_type": input_type,
                    "requested": len(texts),
                    "hits": len(texts) - len(miss_indices),
                    "misses": len(miss_indices),
                },
            )
            return [r for r in results if r is not None]
        finally:
            await client.aclose()
