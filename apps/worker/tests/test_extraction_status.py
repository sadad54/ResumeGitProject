"""The extraction actor always settles a repository out of `extracting`.

sync.py marks a repository EXTRACTING when it queues extraction; this is the
only signal the UI (and scripts/e2e_live.py) has that a repository's evidence
is ready. Before it existed, sync reported COMPLETED while extraction was
still running, and nothing ever said when it finished — or that it failed.
Real database; GitHub and the LLM are faked at the module boundary.
"""

import uuid

import pytest
from proofhire_api.db import async_session_factory
from proofhire_api.models.evidence import Evidence
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.repository import Repository
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.security.password import hash_password
from proofhire_api.security.token_crypto import encrypt_token
from proofhire_contracts import SyncStatus
from sqlalchemy import select

from proofhire_worker.intelligence import evidence_extraction as extraction
from proofhire_worker.intelligence.embeddings import MockEmbeddingProvider
from proofhire_worker.intelligence.llm_provider import StructuredResult, UsageMetadata
from proofhire_worker.intelligence.schemas import EvidenceExtractionOutput, EvidenceItemOutput

FILES = {
    "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n" * 20,
    "app/agent.py": "def plan(task):\n    return tools.call(task)\n" * 20,
}


class _GitHub:
    def __init__(self, _token):
        pass

    async def get_file_content(self, _owner, _name, path, _sha):
        return FILES.get(path)


class _Extractor:
    """Returns one evidence item per call, citing the first file it was given."""

    name = "fake"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = 0

    async def structured_generate(self, *, task, messages, schema, model_config):
        self.calls += 1
        if self.fail:
            raise RuntimeError("429 Too Many Requests")
        path = next(p for p in FILES if p in messages[-1].content)
        return StructuredResult(
            value=EvidenceExtractionOutput(evidence=[EvidenceItemOutput(
                evidence_type="implementation", title=f"Evidence from {path}",
                normalized_claim=f"Implements {path} ({uuid.uuid4().hex[:6]}).",
                description="d", confidence=0.8, source_paths=[path], skills=["python"],
            )]),
            usage=UsageMetadata(provider="fake", model="fake", input_tokens=1, output_tokens=1,
                                latency_ms=1.0),
        )


@pytest.fixture
async def repo_env():
    async with async_session_factory() as session:
        user = User(email=f"extract-status-{uuid.uuid4().hex[:8]}@example.com",
                    hashed_password=hash_password("x"))
        session.add(user)
        await session.flush()
        repo_number = int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000
        repo = Repository(user_id=user.id, provider_repo_id=repo_number, owner="octo",
                          name="svc", url="https://github.com/octo/svc",
                          sync_status=SyncStatus.EXTRACTING)
        session.add(repo)
        await session.flush()
        for path in FILES:
            session.add(SourceArtifact(repository_id=repo.id, type="source_file", path=path,
                                       commit_sha="a" * 40, content_hash=uuid.uuid4().hex * 2,
                                       priority="p1"))
        await session.commit()
        yield user, repo
        await session.delete(await session.get(User, user.id))
        await session.commit()


async def _connect(user):
    async with async_session_factory() as session:
        session.add(GitHubConnection(user_id=user.id, github_user_id=1, login="octo",
                                     token_ref=encrypt_token("gho_test"), scopes=[]))
        await session.commit()


async def _status_and_evidence(repo):
    async with async_session_factory() as session:
        status = (await session.get(Repository, repo.id)).sync_status
        count = len(list(await session.scalars(
            select(Evidence).where(Evidence.repository_id == repo.id))))
        return status, count


@pytest.fixture
def fakes(monkeypatch):
    def install(extractor):
        monkeypatch.setattr(extraction, "GitHubClient", _GitHub)
        monkeypatch.setattr(extraction, "get_provider", lambda: extractor)
        monkeypatch.setattr(extraction, "get_embedding_provider", MockEmbeddingProvider)

        async def no_events(*_a, **_k):
            return None

        monkeypatch.setattr(extraction, "publish_event", no_events)
    return install


async def test_successful_extraction_settles_completed(repo_env, fakes):
    user, repo = repo_env
    await _connect(user)
    fakes(_Extractor())
    await extraction._extract_for_repository(str(repo.id), str(uuid.uuid4()))
    status, count = await _status_and_evidence(repo)
    assert status == SyncStatus.COMPLETED
    assert count >= 1


async def test_every_llm_call_failing_settles_failed(repo_env, fakes):
    user, repo = repo_env
    await _connect(user)
    extractor = _Extractor(fail=True)
    fakes(extractor)
    await extraction._extract_for_repository(str(repo.id), str(uuid.uuid4()))
    status, count = await _status_and_evidence(repo)
    assert extractor.calls >= 1
    assert (status, count) == (SyncStatus.FAILED, 0)


async def test_no_github_connection_settles_failed_without_calling_the_llm(repo_env, fakes):
    _user, repo = repo_env
    extractor = _Extractor()
    fakes(extractor)
    await extraction._extract_for_repository(str(repo.id), str(uuid.uuid4()))
    status, _count = await _status_and_evidence(repo)
    assert status == SyncStatus.FAILED
    assert extractor.calls == 0


async def test_an_unexpected_crash_still_settles_the_status(repo_env, fakes, monkeypatch):
    user, repo = repo_env
    await _connect(user)
    fakes(_Extractor())

    def explode(_files):
        raise MemoryError("simulated crash mid-extraction")

    monkeypatch.setattr(extraction, "_group_files", explode)
    with pytest.raises(MemoryError):
        await extraction._extract_for_repository(str(repo.id), str(uuid.uuid4()))
    status, _count = await _status_and_evidence(repo)
    assert status == SyncStatus.FAILED
