"""SSE run-progress stream: replay, isolation between runs, reconnects.

The race these pin down: events were Redis pub/sub, which drops anything
published before the browser subscribed, so a run that failed within
milliseconds left the browser waiting out its timeout. Events are now a
stream per run; clients read after the position the trigger request
returned (`events_after`).
"""

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from proofhire_contracts import RunEventName

from proofhire_api.db import async_session_factory
from proofhire_api.main import app
from proofhire_api.models.job import Job
from proofhire_api.routers.events import stream_position
from proofhire_worker.events import publish_event


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def job(client):
    tokens = client.post("/api/v1/auth/signup", json={
        "email": f"events-{uuid.uuid4().hex[:10]}@example.com", "password": "x" * 12,
    }).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=auth).json()

    async def create_job() -> str:
        async with async_session_factory() as session:
            row = Job(user_id=uuid.UUID(me["id"]), source_text="jd")
            session.add(row)
            await session.commit()
            return str(row.id)

    job_id = client.portal.call(create_job)
    yield job_id, auth
    client.delete("/api/v1/auth/me", headers=auth)


def publish(run_id: str, event: RunEventName, data: dict) -> None:
    asyncio.run(publish_event(run_id, event, data))


def read_events(client, job_id: str, auth: dict, **params) -> list[tuple[str, dict]]:
    """Every (event, data) until the stream ends; pings skipped."""
    events, name = [], None
    headers = {**auth, **params.pop("headers", {})}
    with client.stream("GET", f"/api/v1/events/runs/{job_id}", params=params,
                       headers=headers) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and name != "ping":
                events.append((name, json.loads(line.split(":", 1)[1])))
    return events


def test_an_event_published_before_the_client_connects_is_replayed(client, job):
    """The race: a run that fails before the browser subscribes."""
    job_id, auth = job
    position = client.portal.call(stream_position, job_id)
    publish(job_id, RunEventName.GENERATION_FAILED, {"job_id": job_id})
    assert read_events(client, job_id, auth, after=position) == [
        ("generation.failed", {"job_id": job_id})]


def test_replay_starts_at_this_run_not_at_earlier_runs_on_the_same_key(client, job):
    """Generation reuses the job id: replaying from the start would hand a
    second generation the first one's completion (and its old document)."""
    job_id, auth = job
    publish(job_id, RunEventName.GENERATION_COMPLETED, {"document_id": "old"})
    position = client.portal.call(stream_position, job_id)
    publish(job_id, RunEventName.GENERATION_STARTED, {})
    publish(job_id, RunEventName.GENERATION_COMPLETED, {"document_id": "new"})
    assert read_events(client, job_id, auth, after=position) == [
        ("generation.started", {}), ("generation.completed", {"document_id": "new"})]


def test_a_reconnecting_client_resumes_after_its_last_event_id(client, job):
    job_id, auth = job
    position = client.portal.call(stream_position, job_id)
    publish(job_id, RunEventName.GENERATION_STARTED, {})
    seen = client.portal.call(stream_position, job_id)  # the id of that first event
    publish(job_id, RunEventName.GENERATION_FAILED, {"job_id": job_id})
    assert position != seen
    assert read_events(client, job_id, auth, headers={"Last-Event-ID": seen}) == [
        ("generation.failed", {"job_id": job_id})]


def test_a_malformed_cursor_is_rejected(client, job):
    job_id, auth = job
    response = client.get(f"/api/v1/events/runs/{job_id}", params={"after": "0; DEL x"},
                          headers=auth)
    assert response.status_code == 422
