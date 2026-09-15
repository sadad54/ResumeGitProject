"""GitHub OAuth flow (ADR-0013: OAuth, not a GitHub App, for V1).

Two-step flow:
1. `build_authorize_url` — called from POST /api/v1/github/connect, returns the URL
   the frontend redirects the browser to. The `state` param is a short-lived signed
   token embedding the requesting user's id, so the callback (a plain browser
   redirect with no Authorization header) can be tied back to a user without a
   server-side session store.
2. `exchange_code_for_token` — called from GET /api/v1/github/callback once GitHub
   redirects back with `code` + `state`.
"""

import urllib.parse
import uuid

import httpx

from proofhire_api.config import get_settings
from proofhire_api.security.jwt import (
    InvalidTokenError,
    TokenType,
    create_oauth_state_token,
    decode_token,
)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# Minimal scopes: public repo read + read access to user profile. `repo` (private
# repo access) is requested only if/when the user opts in to authorized private
# repositories (PRD §8.3 "no scraping private repositories without authorization").
OAUTH_SCOPES = "read:user public_repo"


def verify_oauth_state(state: str) -> uuid.UUID:
    try:
        return decode_token(state, TokenType.OAUTH_STATE)
    except InvalidTokenError as exc:
        raise ValueError("invalid or expired OAuth state") from exc


def build_authorize_url(user_id: uuid.UUID) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "scope": OAUTH_SCOPES,
        "state": create_oauth_state_token(user_id),
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


class GitHubOAuthError(Exception):
    pass


async def exchange_code_for_token(code: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
        )
    response.raise_for_status()
    payload = response.json()
    if "access_token" not in payload:
        raise GitHubOAuthError(payload.get("error_description", "OAuth exchange failed"))
    return payload["access_token"]


async def fetch_github_user(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
    response.raise_for_status()
    return response.json()
