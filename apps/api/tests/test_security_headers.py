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
