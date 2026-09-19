"""Logout / token revocation / account deletion / GitHub disconnect
(PRD §27, checklist §14). Exercised through the real app + real Redis + real
Postgres: revocation is precisely the behavior that a mocked token store would
assert into existence without proving.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from proofhire_api.main import app


@pytest.fixture(scope="module")
def client():
    # Module-scoped: each TestClient runs its own portal event loop, and
    # proofhire_api.db's pooled asyncpg connections are bound to whichever loop
    # opened them. A per-test client would hand connections from a closed loop
    # to the next test (RuntimeError: Event loop is closed) — the same
    # loop-affinity constraint documented in apps/worker/proofhire_worker/db.py.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def account(client):
    email = f"lifecycle-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 201, response.text
    tokens = response.json()
    yield email, tokens

    # Best-effort cleanup; the delete-account test removes its own user.
    client.delete(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )


def test_access_token_works_before_logout_and_is_refused_after(client, account):
    _email, tokens = account
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200

    logout = client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=auth
    )
    assert logout.status_code == 204, logout.text

    after = client.get("/api/v1/auth/me", headers=auth)
    assert after.status_code == 401
    assert "revoked" in after.json()["detail"].lower()


def test_refresh_token_cannot_mint_a_new_session_after_logout(client, account):
    """The real point of logout: the refresh token must be dead too, otherwise
    the client can immediately re-acquire a valid access token."""
    _email, tokens = account
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=auth
    )

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401


def test_refresh_rotation_revokes_the_spent_refresh_token(client, account):
    _email, tokens = account

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    replayed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replayed.status_code == 401

    still_valid = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert still_valid.status_code == 200


def test_logging_out_one_session_leaves_another_session_working(client, account):
    """Per-token jti revocation, not a user-level kill switch."""
    email, tokens = account
    second = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
    ).json()

    client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {second['access_token']}"},
        ).status_code
        == 200
    )


def test_account_deletion_removes_the_user_entirely(client):
    email = f"delete-me-{uuid.uuid4().hex[:10]}@example.com"
    tokens = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "correct-horse-battery"}
    ).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert client.delete("/api/v1/auth/me", headers=auth).status_code == 204

    # The token is still cryptographically valid, so this proves the *user row*
    # is gone rather than merely that the session ended.
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
    relogin = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    assert relogin.status_code == 401


def test_github_disconnect_returns_404_when_nothing_is_connected(client, account):
    _email, tokens = account
    response = client.delete(
        "/api/v1/github/connection",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 404
