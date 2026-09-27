"""The OAuth callback is a browser navigation, so every outcome — success,
the user cancelling on GitHub, a stale state, a failed token exchange — must
redirect back into the web app rather than render JSON on the API's domain."""

import uuid

import pytest
from fastapi.testclient import TestClient

from proofhire_api.config import get_settings
from proofhire_api.main import app
from proofhire_api.routers import github as github_router
from proofhire_api.services.github_oauth import GitHubOAuthError, build_authorize_url


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _settings_url(outcome: str) -> str:
    return f"{get_settings().web_base_url}/settings?github={outcome}"


def _state() -> str:
    url = build_authorize_url(uuid.uuid4())
    return url.split("state=")[1].split("&")[0]


def test_user_cancelling_on_github_lands_back_on_settings(client):
    response = client.get(
        "/api/v1/github/callback",
        params={
            "error": "access_denied",
            "error_description": "The user denied",
            "state": _state(),
        },
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == _settings_url("denied")


def test_a_forged_or_expired_state_is_refused_without_stranding_the_user(client):
    response = client.get(
        "/api/v1/github/callback", params={"code": "abc", "state": "not-a-token"},
        follow_redirects=False,
    )
    assert response.headers["location"] == _settings_url("expired")


def test_a_failed_token_exchange_redirects_with_a_fixed_reason(client, monkeypatch):
    async def fail(_code):
        raise GitHubOAuthError("bad_verification_code: <script>")

    monkeypatch.setattr(github_router, "exchange_code_for_token", fail)
    response = client.get(
        "/api/v1/github/callback", params={"code": "abc", "state": _state()},
        follow_redirects=False,
    )
    # GitHub's free-text error never reaches the URL the web app renders.
    assert response.headers["location"] == _settings_url("error")


def test_missing_parameters_redirect_instead_of_422(client):
    response = client.get("/api/v1/github/callback", follow_redirects=False)
    assert response.headers["location"] == _settings_url("error")
