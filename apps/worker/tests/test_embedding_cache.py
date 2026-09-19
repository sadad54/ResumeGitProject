"""Embedding cache (PRD §28): against real Redis, with a counting fake
underneath so the saving is observed, not assumed."""

import uuid

from proofhire_worker.intelligence.embedding_cache import CachedEmbeddingProvider


class _Counting:
    name = "fake"

    def __init__(self):
        self.calls: list[list[str]] = []

    async def embed(self, texts, *, model):
        self.calls.append(list(texts))
        return [[float(len(t)), 1.0] for t in texts]

    async def structured_generate(self, **kw):
        raise NotImplementedError


def _unique(n):
    return [f"{uuid.uuid4().hex} text {i}" for i in range(n)]


async def test_second_identical_call_does_not_reach_the_provider():
    inner = _Counting()
    cached = CachedEmbeddingProvider(inner)
    texts = _unique(3)

    first = await cached.embed(texts, model="m")
    second = await cached.embed(texts, model="m")

    assert first == second
    assert len(inner.calls) == 1


async def test_only_misses_are_sent_and_order_is_preserved():
    inner = _Counting()
    cached = CachedEmbeddingProvider(inner)
    a, b, c = _unique(3)

    await cached.embed([a, c], model="m")
    result = await cached.embed([a, b, c], model="m")

    assert inner.calls[-1] == [b], "only the uncached text should be embedded"
    assert result == [[float(len(a)), 1.0], [float(len(b)), 1.0], [float(len(c)), 1.0]]


async def test_cache_is_keyed_by_model_too():
    inner = _Counting()
    cached = CachedEmbeddingProvider(inner)
    [t] = _unique(1)

    await cached.embed([t], model="small")
    await cached.embed([t], model="large")

    assert len(inner.calls) == 2


async def test_empty_input_is_a_no_op():
    inner = _Counting()
    assert await CachedEmbeddingProvider(inner).embed([], model="m") == []
    assert inner.calls == []
