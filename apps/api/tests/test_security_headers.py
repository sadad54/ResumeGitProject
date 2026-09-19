"""Regression test for baseline security response headers (Phase 10 hardening)."""

from fastapi.testclient import TestClient

from proofhire_api.main import app


def test_health_response_carries_security_headers():
    client = TestClient(app)
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["cache-control"] == "no-store"


def test_ready_reports_each_dependency():
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"status": "ready", "postgres": "ok", "redis": "ok"}


def test_ready_returns_503_when_redis_is_unavailable(monkeypatch):
    from proofhire_api.routers import health

    class _Down:
        async def ping(self):
            raise ConnectionError("redis down")

    monkeypatch.setattr(health, "get_redis", lambda: _Down())

    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["redis"] == "unavailable"
    assert response.json()["postgres"] == "ok"
