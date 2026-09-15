"""Regression test for the CORS bug found during real-browser testing: the
browser's preflight OPTIONS request must succeed for the web app's origin,
or every cross-origin mutating request (POST/PATCH/etc. from localhost:3000
to localhost:8000) fails before it even reaches the route handler."""

from fastapi.testclient import TestClient

from proofhire_api.config import get_settings
from proofhire_api.main import app


def test_preflight_options_succeeds_for_configured_web_origin():
    client = TestClient(app)
    settings = get_settings()

    response = client.options(
        "/api/v1/auth/signup",
        headers={
            "Origin": settings.web_base_url,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.web_base_url
