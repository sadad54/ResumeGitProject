"""GET /api/v1/me/overview and /auth/me's is_demo, through the real app."""

import uuid

import pytest
from fastapi.testclient import TestClient
from proofhire_contracts import DocumentType, EvidenceStatus, GenerationRunStatus

from proofhire_api.db import async_session_factory
from proofhire_api.main import app
from proofhire_api.models.evidence import Evidence
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def account(client):
    email = f"overview-{uuid.uuid4().hex[:10]}@example.com"
    tokens = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "correct-horse-battery"}
    ).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=auth).json()
    yield auth, me
    client.delete("/api/v1/auth/me", headers=auth)


def test_me_says_whether_the_session_is_the_demo_account(client, account):
    _auth, me = account
    assert me["is_demo"] is False

    demo = client.post("/api/v1/demo/session").json()
    demo_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {demo['access_token']}"}
    ).json()
    assert demo_me["is_demo"] is True


def test_a_new_account_starts_empty_and_disconnected(client, account):
    auth, _me = account
    body = client.get("/api/v1/me/overview", headers=auth).json()
    assert body["github"] == {
        "connected": False, "login": None, "connected_at": None, "last_sync_at": None
    }
    assert body["repositories"] == {"total": 0, "selected": 0, "synced": 0}
    assert body["evidence"]["total"] == 0
    assert body["documents"] == {"total": 0, "exported": 0}


async def _seed(user_id: str) -> None:
    uid = uuid.UUID(user_id)
    async with async_session_factory() as session:
        session.add(GitHubConnection(user_id=uid, github_user_id=42, login="octocat",
                                     token_ref="encrypted", scopes=[]))
        repo = Repository(user_id=uid, provider_repo_id=uuid.uuid4().int % 10**9, owner="octocat",
                          name="svc", url="https://github.com/octocat/svc", selected=True,
                          last_analyzed_sha="a" * 40)
        other = Repository(user_id=uid, provider_repo_id=uuid.uuid4().int % 10**9,
                           owner="octocat", name="docs", url="https://github.com/octocat/docs")
        session.add_all([repo, other])
        await session.flush()
        for status in (EvidenceStatus.CONFIRMED, EvidenceStatus.CONFIRMED,
                       EvidenceStatus.CANDIDATE, EvidenceStatus.STALE):
            session.add(Evidence(user_id=uid, repository_id=repo.id, evidence_type="implementation",
                                 title="t", normalized_claim=f"c-{uuid.uuid4()}", description="d",
                                 confidence=0.8, extraction_method="test", status=status))
        job = Job(user_id=uid, source_text="jd", status="ready")
        session.add_all([job, Job(user_id=uid, source_text="jd 2")])
        await session.flush()
        run = GenerationRun(user_id=uid, job_id=job.id, pipeline_version="t",
                            status=GenerationRunStatus.SUCCEEDED)
        session.add(run)
        await session.flush()
        session.add_all([
            GeneratedDocument(job_id=job.id, generation_run_id=run.id, type=DocumentType.RESUME,
                              content_json={}, pdf_ref=f"users/{uid}/documents/x.pdf"),
            GeneratedDocument(job_id=job.id, generation_run_id=run.id,
                              type=DocumentType.COVER_LETTER, content_json={}),
        ])
        await session.commit()


def test_overview_counts_only_what_the_user_owns(client, account):
    auth, me = account
    client.portal.call(_seed, me["id"])
    stranger = client.post(
        "/api/v1/auth/signup",
        json={"email": f"stranger-{uuid.uuid4().hex[:8]}@example.com", "password": "x" * 12},
    ).json()
    stranger_auth = {"Authorization": f"Bearer {stranger['access_token']}"}
    try:
        body = client.get("/api/v1/me/overview", headers=auth).json()
        assert body["github"]["connected"] is True and body["github"]["login"] == "octocat"
        assert body["repositories"] == {"total": 2, "selected": 1, "synced": 1}
        assert body["evidence"] == {"total": 4, "confirmed": 2, "candidate": 1, "stale": 1}
        assert body["jobs"] == {"total": 2, "ready": 1}
        assert body["documents"] == {"total": 2, "exported": 1}

        theirs = client.get("/api/v1/me/overview", headers=stranger_auth).json()
        assert theirs["evidence"]["total"] == 0 and theirs["github"]["connected"] is False
    finally:
        client.delete("/api/v1/auth/me", headers=stranger_auth)
