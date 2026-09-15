"""Self-hosted JWT issuance/verification for ProofHire's own application auth
(ADR: self-hosted JWT/OIDC, decided over a hosted auth SaaS for Phase 1).

Separate from the GitHub OAuth token, which authenticates the GitHub *connection*,
not the ProofHire user session (PRD §12.3: "GitHub OAuth separate from application
auth").
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import jwt

from proofhire_api.config import get_settings

ALGORITHM = "HS256"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    OAUTH_STATE = "oauth_state"


class InvalidTokenError(Exception):
    pass


def _create_token(user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(
        user_id,
        TokenType.ACCESS,
        timedelta(minutes=settings.auth_access_token_expire_minutes),
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(
        user_id,
        TokenType.REFRESH,
        timedelta(days=settings.auth_refresh_token_expire_days),
    )


def create_oauth_state_token(user_id: uuid.UUID) -> str:
    """Short-lived token carrying a user id through a third-party OAuth redirect
    that has no Authorization header (PRD §12.3 GitHub OAuth flow)."""
    return _create_token(user_id, TokenType.OAUTH_STATE, timedelta(minutes=10))


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"expected token type {expected_type.value}")

    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("malformed subject claim") from exc
