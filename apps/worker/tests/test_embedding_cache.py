"""Embedding cache (PRD §28): against real Redis, with a counting fake
underneath so the saving is observed, not assumed."""

import uuid

from proofhire_worker.intelligence.embedding_cache import CachedEmbeddingProvider


class _Counting:
    dimension = 2

    def __init__(self, model_id: str = "m"):
        self.model_id = model_id
        self.calls: list[list[str]] = []

    async def embed(self, texts, *, input_type="document"):
        self.calls.append(list(texts))
        return [[float(len(t)), 1.0 if input_type == "document" else -1.0] for t in texts]


def _unique(n):
    return [f"{uuid.uuid4().hex} text {i}" for i in range(n)]


async def test_second_identical_call_does_not_reach_the_provider():
    inner = _Counting()
    cached = CachedEmbeddingProvider(inner)
    texts = _unique(3)

    first = await cached.embed(texts)
    second = await cached.embed(texts)

    assert first == second
    assert len(inner.calls) == 1


async def test_only_misses_are_sent_and_order_is_preserved():
    inner = _Counting()
    cached = CachedEmbeddingProvider(inner)
    a, b, c = _unique(3)

    await cached.embed([a, c])
    result = await cached.embed([a, b, c])

    assert inner.calls[-1] == [b], "only the uncached text should be embedded"
    assert result == [[float(len(a)), 1.0], [float(len(b)), 1.0], [float(len(c)), 1.0]]


async def test_cache_is_keyed_by_model_too():
    [t] = _unique(1)
    small, large = _Counting("small"), _Counting("large")

    await CachedEmbeddingProvider(small).embed([t])
    await CachedEmbeddingProvider(large).embed([t])

    assert len(small.calls) == len(large.calls) == 1


async def test_query_and_document_vectors_are_cached_separately():
    """A query-side vector may carry an instruction prefix, so the same text
    embedded as a query must not be served the document-side vector."""
    inner = _Counting()
    cached = CachedEmbeddingProvider(inner)
    [t] = _unique(1)

    document = await cached.embed([t], input_type="document")
    query = await cached.embed([t], input_type="query")

    assert len(inner.calls) == 2
    assert document != query


def test_wrapper_keeps_the_inner_identity():
    cached = CachedEmbeddingProvider(_Counting("bge"))
    assert (cached.model_id, cached.dimension) == ("bge", 2)


async def test_empty_input_is_a_no_op():
    inner = _Counting()
    assert await CachedEmbeddingProvider(inner).embed([]) == []
    assert inner.calls == []
