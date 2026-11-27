"""Embedding providers (ADR-0018) and the re-embedding backfill.

The local-model tests load the real bge-small ONNX model (~65 MB, fetched once
into the fastembed cache) because the property that matters — related texts
land closer than unrelated ones — can't be asserted against a fake.
"""

import math
import uuid

import pytest
from proofhire_contracts import EvidenceStatus
from proofhire_contracts.embedding import EMBEDDING_DIMENSION

from proofhire_api.models.evidence import Evidence
from proofhire_api.models.repository import Repository
from proofhire_api.models.user import User
from proofhire_api.security.password import hash_password
from proofhire_worker.db import async_session_factory
from proofhire_worker.intelligence.embeddings import (
    BGE_QUERY_INSTRUCTION,
    LocalEmbeddingProvider,
    MockEmbeddingProvider,
    build_embedding_provider,
    evidence_embedding_text,
)
from proofhire_worker.intelligence.reembed import reembed_stale_evidence


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    )


# --- selection ---------------------------------------------------------------


def test_default_provider_is_the_local_model(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    provider = build_embedding_provider()
    assert isinstance(provider, LocalEmbeddingProvider)
    assert provider.model_id == "BAAI/bge-small-en-v1.5"


def test_openai_embeddings_need_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_embedding_provider("openai")


def test_openai_identity_includes_the_requested_dimension(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = build_embedding_provider("openai")
    assert provider.model_id == f"text-embedding-3-small@{EMBEDDING_DIMENSION}"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        build_embedding_provider("word2vec")


def test_a_model_of_the_wrong_dimension_is_refused_before_any_download():
    provider = LocalEmbeddingProvider("BAAI/bge-base-en-v1.5")  # 768-d
    with pytest.raises(ValueError, match="768"):
        provider._model()


# --- mock ----------------------------------------------------------------------


async def test_mock_vectors_are_deterministic_normalised_and_centred():
    provider = MockEmbeddingProvider()
    [a1, b] = await provider.embed(["same text", "other text"])
    [a2] = await provider.embed(["same text"])
    assert a1 == a2 and a1 != b
    assert len(a1) == EMBEDDING_DIMENSION
    assert math.isclose(math.sqrt(sum(v * v for v in a1)), 1.0, rel_tol=1e-9)
    # The old mock was all-positive, so any two vectors scored ~0.75 cosine.
    assert abs(_cos(a1, b)) < 0.5


# --- the real local model -----------------------------------------------------


@pytest.fixture(scope="module")
def local():
    pytest.importorskip("fastembed")
    return LocalEmbeddingProvider()


async def test_local_model_produces_unit_vectors_of_the_column_dimension(local):
    [vector] = await local.embed(["Built a FastAPI service backed by Postgres."])
    assert len(vector) == EMBEDDING_DIMENSION
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-4)


async def test_local_model_ranks_related_evidence_above_unrelated(local):
    [requirement] = await local.embed(
        ["Experience building REST APIs in Python"], input_type="query"
    )
    related, unrelated = await local.embed(
        [
            "Implemented a FastAPI backend with JWT authentication and pagination.",
            "Baked sourdough bread and documented the fermentation schedule.",
        ]
    )
    assert _cos(requirement, related) > _cos(requirement, unrelated) + 0.1


async def test_query_instruction_only_changes_query_side_vectors():
    pytest.importorskip("fastembed")
    plain = LocalEmbeddingProvider(query_instruction=False)
    instructed = LocalEmbeddingProvider(query_instruction=True)
    text = "Kubernetes deployment experience"

    assert await plain.embed([text]) == await instructed.embed([text])
    assert await plain.embed([text], input_type="query") != await instructed.embed(
        [text], input_type="query"
    )
    assert await instructed.embed([text], input_type="query") == await plain.embed(
        [BGE_QUERY_INSTRUCTION + text]
    )


def test_evidence_text_is_one_definition():
    assert evidence_embedding_text("Title", "claim", "desc") == "Title. claim desc"


# --- backfill ------------------------------------------------------------------


@pytest.fixture
async def stale_rows():
    async with async_session_factory() as session:
        user = User(email=f"reembed-{uuid.uuid4().hex[:8]}@example.com",
                    hashed_password=hash_password("x"))
        session.add(user)
        await session.flush()
        repo = Repository(user_id=user.id, provider_repo_id=uuid.uuid4().int % 10**9,
                          owner="octo", name="r", url="https://github.com/octo/r")
        session.add(repo)
        await session.flush()
        ids = []
        for i, (vector, model) in enumerate(
            [(None, None), ([0.1] * EMBEDDING_DIMENSION, "some-older-model")]
        ):
            ev = Evidence(user_id=user.id, repository_id=repo.id, evidence_type="implementation",
                          title=f"t{i}", normalized_claim=f"c{i}", description="d", confidence=0.8,
                          extraction_method="test", status=EvidenceStatus.CANDIDATE,
                          embedding=vector, embedding_model=model)
            session.add(ev)
            await session.flush()
            ids.append(ev.id)
        await session.commit()
        yield user.id, ids
        await session.delete(await session.get(User, user.id))
        await session.commit()


async def test_backfill_reembeds_missing_and_foreign_vectors_then_is_a_no_op(stale_rows):
    user_id, ids = stale_rows
    provider = MockEmbeddingProvider()
    assert await reembed_stale_evidence(provider, batch_size=1, user_id=user_id) == 2

    async with async_session_factory() as session:
        for evidence_id in ids:
            row = await session.get(Evidence, evidence_id)
            assert row.embedding_model == provider.model_id
            expected = await provider.embed(
                [evidence_embedding_text(row.title, row.normalized_claim, row.description)]
            )
            assert [round(v, 5) for v in row.embedding] == [round(v, 5) for v in expected[0]]

    assert await reembed_stale_evidence(provider, user_id=user_id) == 0
