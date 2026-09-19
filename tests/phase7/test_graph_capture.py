import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.evidence import Evidence, EvidenceSkill, EvidenceSource
from proofhire_api.models.evidence_match import EvidenceMatch
from proofhire_api.models.job import Job
from proofhire_api.models.repository import Repository
from proofhire_api.models.requirement import Requirement
from proofhire_api.models.skill import Skill
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.user import User
from proofhire_api.routers.evidence import router
from proofhire_api.routers.jobs import capture_job
from proofhire_api.schemas.capture import JobCaptureRequest
from proofhire_api.services.evidence_graph import project_graph
from pydantic import ValidationError


async def seed(db):
    user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="unused")
    other = User(email=f"{uuid.uuid4()}@example.com", hashed_password="unused")
    db.add_all([user, other])
    await db.flush()
    repo = Repository(
        user_id=user.id,
        provider_repo_id=1,
        owner="test",
        name="proof",
        url="https://github.com/test/proof",
    )
    db.add(repo)
    await db.flush()
    artifact = SourceArtifact(
        repository_id=repo.id,
        type="source_file",
        path="api/main.py",
        commit_sha="a" * 40,
        content_hash="a" * 64,
        priority="p1",
    )
    db.add(artifact)
    await db.flush()
    evidence = Evidence(
        user_id=user.id,
        repository_id=repo.id,
        evidence_type="architecture",
        title="API design",
        normalized_claim="Designed a REST API",
        description="",
        confidence=0.8,
        status="confirmed",
        extraction_method="test",
    )
    db.add(evidence)
    await db.flush()
    db.add(
        EvidenceSource(
            evidence_id=evidence.id,
            source_artifact_id=artifact.id,
            locator="api/main.py#L2-L8",
            snippet_hash="a" * 64,
            commit_sha="a" * 40,
            line_start=2,
            line_end=8,
        )
    )
    skill = Skill(canonical_name="Python", aliases=[])
    db.add(skill)
    await db.flush()
    db.add(EvidenceSkill(evidence_id=evidence.id, skill_id=skill.id, strength=0.9))
    job = Job(user_id=user.id, source_text="REST API role", status="ready")
    db.add(job)
    await db.flush()
    req = Requirement(
        job_id=job.id,
        category="skill",
        text="REST APIs",
        normalized=["rest"],
        importance=0.9,
        required=True,
    )
    gap = Requirement(
        job_id=job.id,
        category="skill",
        text="Kubernetes",
        normalized=["kubernetes"],
        importance=0.8,
        required=False,
    )
    db.add_all([req, gap])
    await db.flush()
    db.add(
        EvidenceMatch(
            requirement_id=req.id,
            evidence_id=evidence.id,
            retrieval_score=0.9,
            rerank_score=0.8,
            status="partial",
            match_reason="API implementation does not prove production operation.",
        )
    )
    await db.commit()
    return user, other, repo, evidence, job, req, gap


@pytest.mark.asyncio
async def test_projection_preserves_partial_provenance_and_gap(db):
    user, _, _, evidence, job, req, gap = await seed(db)
    graph = await project_graph(db, user.id, job.id, None, 200)
    nodes = {n.id: n for n in graph.nodes}
    assert {n.kind for n in graph.nodes} == {
        "project",
        "architecture",
        "skill",
        "requirement",
    }
    assert nodes[f"requirement:{req.id}"].status == "partial"
    assert nodes[f"requirement:{gap.id}"].status == "gap"
    assert (
        nodes[f"evidence:{evidence.id}"].sources[0].url.endswith("/api/main.py#L2-L8")
    )
    assert all(e.source in nodes and e.target in nodes for e in graph.edges)
    assert next(e for e in graph.edges if e.kind == "matches").weight == 0.8


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["private", "rejected", "stale", "candidate"])
async def test_hidden_or_unconfirmed_evidence_never_lights_match(db, status):
    user, _, _, evidence, job, req, _ = await seed(db)
    evidence.status = status
    await db.commit()
    graph = await project_graph(db, user.id, job.id, None, 200)
    assert not any(e.kind == "matches" for e in graph.edges)
    assert (
        next(n for n in graph.nodes if n.id == f"requirement:{req.id}").status
        == "unknown"
    )
    if status != "candidate":
        assert not any(n.evidence_id for n in graph.nodes)


@pytest.mark.asyncio
async def test_tenant_isolation_and_foreign_filters(db):
    user, other, repo, _, job, _, _ = await seed(db)
    assert (await project_graph(db, other.id, None, None, 200)).nodes == []
    for kwargs in (
        {"job_id": job.id, "repository_id": None},
        {"job_id": None, "repository_id": repo.id},
    ):
        with pytest.raises(HTTPException) as exc:
            await project_graph(db, other.id, limit=200, **kwargs)
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_route_order_auth_and_limits(db):
    user, *_ = await seed(db)
    app = FastAPI()
    app.include_router(router)

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/evidence/graph")).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        response = await client.get("/api/v1/evidence/graph")
        assert response.status_code == 200
        assert response.json()["nodes"]
        assert (
            await client.get("/api/v1/evidence/graph?limit=1001")
        ).status_code == 422


@pytest.mark.asyncio
async def test_capture_idempotence_and_secret_block(db):
    user, other, *_ = await seed(db)
    body = JobCaptureRequest(
        selected_text="We need a software engineer experienced with Python REST APIs.",
        title="Backend Engineer",
        captured_at=datetime.now(timezone.utc),
    )
    job = await capture_job(body, current_user=user, db=db)
    assert job.source_title == "Backend Engineer"
    assert (await capture_job(body, current_user=user, db=db)).id == job.id
    with pytest.raises(HTTPException) as exc:
        await capture_job(body, current_user=other, db=db)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        await capture_job(
            JobCaptureRequest(selected_text=body.selected_text + " ghp_" + "x" * 36),
            current_user=user,
            db=db,
        )
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "kwargs",
    [
        {"selected_text": "  " * 40},
        {"page_url": "javascript:alert(1)"},
        {"page_url": "https://user:pass@example.com"},
        {"captured_at": "2026-09-16T10:00:00"},
    ],
)
def test_capture_validation(kwargs):
    with pytest.raises(ValidationError):
        JobCaptureRequest(
            **{
                "selected_text": "We need a software engineer experienced with Python REST APIs.",
                **kwargs,
            }
        )


@pytest.mark.asyncio
async def test_reanalysis_does_not_display_old_match_as_current(db):
    user, _, _, _, job, req, _ = await seed(db)
    job.status = "matching"
    await db.commit()
    graph = await project_graph(db, user.id, job.id, None, 200)
    assert (
        next(n for n in graph.nodes if n.id == f"requirement:{req.id}").status
        == "unknown"
    )
    assert not any(e.kind == "matches" for e in graph.edges)


@pytest.mark.asyncio
async def test_cors_and_validation_do_not_echo_untrusted_input(db):
    from proofhire_api.main import create_app

    app = create_app()
    user, *_ = await seed(db)

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/v1/jobs/capture",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        response = await client.post(
            "/api/v1/jobs/capture", json={"selected_text": "sensitive-too-short"}
        )
        assert response.status_code == 422
        assert "sensitive-too-short" not in response.text
