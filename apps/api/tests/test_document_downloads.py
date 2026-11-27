"""Export downloads through signed URLs, end to end through the real app,
Postgres and the configured storage backend (local in dev/CI).

Rows are seeded with `client.portal.call`, which runs on the TestClient's
own event loop — the loop its pooled DB connections belong to (see the
fixture comment in test_account_lifecycle.py).
"""

import uuid
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from proofhire_contracts import ClaimVerificationStatus, DocumentType, GenerationRunStatus

from proofhire_api.db import async_session_factory
from proofhire_api.main import app
from proofhire_api.models.evidence import Evidence, EvidenceSource
from proofhire_api.models.generated_claim import ClaimEvidence, GeneratedClaim
from proofhire_api.models.generated_document import GeneratedDocument
from proofhire_api.models.generation_run import GenerationRun
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.services.object_storage import document_key, get_object_storage

CONTENT = {
    "summary": "Engineer.",
    "skills": ["Python"],
    "experience": [
        {"title": "Engineer", "employer": "Acme", "start_date": "2021", "end_date": "2024",
         "bullets": ["Built a thing."]}
    ],
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _signup(client) -> tuple[dict, str]:
    email = f"downloads-{uuid.uuid4().hex[:10]}@example.com"
    tokens = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "correct-horse-battery"}
    ).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = client.get("/api/v1/auth/me", headers=auth).json()["id"]
    return auth, user_id


async def _seed_documents(user_id: str, count: int = 1, exported: bool = True) -> list[str]:
    ids = []
    async with async_session_factory() as session:
        job = Job(user_id=uuid.UUID(user_id), source_text="jd")
        session.add(job)
        await session.flush()
        for _ in range(count):
            run = GenerationRun(user_id=uuid.UUID(user_id), job_id=job.id, pipeline_version="t",
                                status=GenerationRunStatus.SUCCEEDED)
            session.add(run)
            await session.flush()
            doc = GeneratedDocument(job_id=job.id, generation_run_id=run.id,
                                    type=DocumentType.RESUME, content_json=CONTENT)
            session.add(doc)
            await session.flush()
            if exported:
                storage = get_object_storage()
                files = (("pdf", b"%PDF-1.7 test"), ("txt", b"Engineer."), ("html", b"<p>"))
                for ext, body in files:
                    key = document_key(user_id, doc.id, ext)
                    await storage.put(key, body, "application/octet-stream")
                doc.pdf_ref = document_key(user_id, doc.id, "pdf")
                doc.plaintext_ref = document_key(user_id, doc.id, "txt")
                doc.html_ref = document_key(user_id, doc.id, "html")
            await session.commit()  # separate commits -> distinct created_at
            ids.append(str(doc.id))
    return ids


@pytest.fixture
def owner(client):
    auth, user_id = _signup(client)
    yield auth, user_id
    client.delete("/api/v1/auth/me", headers=auth)


def _fetch(client, url: str):
    """Follow a signed URL the way a browser would: no Authorization header."""
    parsed = urlparse(url)
    return client.get(f"{parsed.path}?{parsed.query}")


def test_documents_expose_availability_not_storage_paths(client, owner):
    auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id)

    body = client.get(f"/api/v1/documents/{doc_id}", headers=auth).json()
    assert body["pdf_available"] is True and body["plaintext_available"] is True
    assert not {"pdf_ref", "html_ref", "plaintext_ref"} & body.keys()
    assert "created_at" in body


def test_signed_download_link_serves_the_file_without_a_bearer_token(client, owner):
    auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id)

    link = client.get(f"/api/v1/documents/{doc_id}/download?format=pdf", headers=auth)
    assert link.status_code == 200, link.text
    payload = link.json()
    assert payload["filename"].endswith(".pdf")

    response = _fetch(client, payload["url"])
    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 test"
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "private, no-store"

    txt = client.get(f"/api/v1/documents/{doc_id}/download?format=txt", headers=auth).json()
    assert _fetch(client, txt["url"]).content == b"Engineer."


def test_tampered_signed_links_are_refused(client, owner):
    auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id)
    url = client.get(f"/api/v1/documents/{doc_id}/download", headers=auth).json()["url"]

    other_key = url.replace(f"documents/{doc_id}", f"documents/{uuid.uuid4()}")
    assert _fetch(client, other_key).status_code == 403
    assert _fetch(client, url.replace("signature=", "signature=00")).status_code == 403
    assert _fetch(client, url.replace("filename=", "filename=x")).status_code == 403


def test_download_links_are_ownership_scoped(client, owner):
    _auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id)
    stranger, _ = _signup(client)
    try:
        response = client.get(f"/api/v1/documents/{doc_id}/download", headers=stranger)
        assert response.status_code == 404
    finally:
        client.delete("/api/v1/auth/me", headers=stranger)


def test_unexported_document_has_no_download(client, owner):
    auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id, 1, False)
    response = client.get(f"/api/v1/documents/{doc_id}/download", headers=auth)
    assert response.status_code == 404
    assert "export" in response.json()["detail"].lower()


def test_a_vanished_export_self_heals_to_not_exported(client, owner):
    """The single-container deploy loses local files on restart. The first
    download after that must say so (410) and flip the document back to
    not-exported, instead of every download 500ing forever."""
    auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id)
    client.portal.call(get_object_storage().delete, document_key(user_id, doc_id, "pdf"))

    response = client.get(f"/api/v1/documents/{doc_id}/download", headers=auth)
    assert response.status_code == 410

    body = client.get(f"/api/v1/documents/{doc_id}", headers=auth).json()
    assert body["pdf_available"] is False and body["exported_at"] is None


def test_documents_list_newest_first(client, owner):
    auth, user_id = owner
    ids = client.portal.call(_seed_documents, user_id, 3, False)
    listed = [d["id"] for d in client.get("/api/v1/documents", headers=auth).json()]
    assert listed == list(reversed(ids))


def test_account_deletion_purges_exported_files(client):
    auth, user_id = _signup(client)
    [doc_id] = client.portal.call(_seed_documents, user_id)
    key = document_key(user_id, doc_id, "pdf")
    assert client.portal.call(get_object_storage().exists, key)

    assert client.delete("/api/v1/auth/me", headers=auth).status_code == 204
    assert not client.portal.call(get_object_storage().exists, key)


async def _seed_claim_with_two_evidence(user_id: str, doc_id: str) -> None:
    async with async_session_factory() as session:
        uid = uuid.UUID(user_id)
        repo = Repository(user_id=uid, provider_repo_id=uuid.uuid4().int % 10**9, owner="octo",
                          name="svc", url="https://github.com/octo/svc")
        session.add(repo)
        await session.flush()
        artifact = SourceArtifact(repository_id=repo.id, path="app.py", type="source_file",
                                  priority="p1", content_hash="h", commit_sha="a" * 40)
        session.add(artifact)
        await session.flush()
        claim = GeneratedClaim(document_id=uuid.UUID(doc_id), claim_text="Built a thing.",
                               claim_type="achievement",
                               verification_status=ClaimVerificationStatus.SUPPORTED,
                               confidence=0.9)
        session.add(claim)
        await session.flush()
        for title, score, locators in (("weak", 0.2, [("weak.py#L1", 0.9)]),
                                       ("strong", 0.95, [("low.py#L1", 0.1), ("high.py#L5", 0.8)])):
            ev = Evidence(user_id=uid, repository_id=repo.id, title=title, description="d",
                          normalized_claim=title, evidence_type="implementation",
                          extraction_method="test", confidence=0.9)
            session.add(ev)
            await session.flush()
            for locator, relevance in locators:
                session.add(EvidenceSource(evidence_id=ev.id, source_artifact_id=artifact.id,
                                           locator=locator, snippet_hash="h", commit_sha="a" * 40,
                                           relevance=relevance))
            session.add(ClaimEvidence(claim_id=claim.id, evidence_id=ev.id, support_score=score))
        await session.commit()


def test_claim_provenance_cites_the_strongest_evidence_and_best_source(client, owner):
    auth, user_id = owner
    [doc_id] = client.portal.call(_seed_documents, user_id, 1, False)
    client.portal.call(_seed_claim_with_two_evidence, user_id, doc_id)

    [claim] = client.get(f"/api/v1/documents/{doc_id}/claims", headers=auth).json()
    assert claim["evidence_title"] == "strong"
    assert claim["source_locator"] == "high.py#L5"
    assert claim["evidence_repository"] == "octo/svc"


def test_demo_account_may_export_and_sign_out_but_not_generate(client):
    tokens = client.post("/api/v1/demo/session").json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    job_id = uuid.uuid4()

    # Blocked: an ordinary write (403 from the guard, before any lookup).
    blocked = client.post(f"/api/v1/jobs/{job_id}/generate", json={}, headers=auth)
    assert blocked.status_code == 403

    # Allowed through the guard: export (404 here only because the id is made up).
    export = client.post(f"/api/v1/documents/{uuid.uuid4()}/export", headers=auth)
    assert export.status_code == 404

    logout = client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=auth
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
