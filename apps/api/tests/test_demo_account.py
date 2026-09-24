"""Read-only guest/demo account (checklist: recruiter-facing live demo without
a GitHub OAuth dance). Exercised through the real app + real Postgres + real
Redis, same as test_account_lifecycle.py — the read-only enforcement lives in
dependencies.get_current_user, which is exactly the kind of thing a mocked
dependency would assert into existence without proving.
"""

import pytest
from fastapi.testclient import TestClient

from proofhire_api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo_tokens(client):
    response = client.post("/api/v1/demo/session")
    assert response.status_code == 200, response.text
    return response.json()


def test_demo_session_issues_a_usable_access_token(client, demo_tokens):
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {demo_tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "demo@proofhire.app"


def test_demo_session_is_idempotent_across_visitors(client):
    """Every visitor shares the one seeded account, not a fresh row each time."""
    first = client.post("/api/v1/demo/session").json()
    second = client.post("/api/v1/demo/session").json()

    first_id = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {first['access_token']}"}
    ).json()["id"]
    second_id = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}
    ).json()["id"]
    assert first_id == second_id


def test_demo_account_cannot_delete_itself(client, demo_tokens):
    response = client.delete(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {demo_tokens['access_token']}"}
    )
    assert response.status_code == 403
    assert "read-only" in response.json()["detail"].lower()

    # Proves it wasn't deleted despite the attempt.
    still_there = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {demo_tokens['access_token']}"}
    )
    assert still_there.status_code == 200


def test_demo_account_cannot_trigger_a_github_sync(client, demo_tokens):
    response = client.post(
        "/api/v1/github/sync",
        json={"repository_ids": []},
        headers={"Authorization": f"Bearer {demo_tokens['access_token']}"},
    )
    assert response.status_code == 403


def test_demo_account_can_still_read(client, demo_tokens):
    response = client.get(
        "/api/v1/applications", headers={"Authorization": f"Bearer {demo_tokens['access_token']}"}
    )
    assert response.status_code == 200
    response = client.get(
        "/api/v1/github/repositories",
        headers={"Authorization": f"Bearer {demo_tokens['access_token']}"},
    )
    assert response.status_code == 200


def test_demo_account_logout_is_blocked_as_a_mutation(client, demo_tokens):
    """logout is a POST, so the same read-only gate covers it — a demo visitor
    ending their own session isn't a real-world need worth special-casing."""
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": demo_tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {demo_tokens['access_token']}"},
    )
    assert response.status_code == 403
