"""Token revocation denylist (PRD §27 "token rotation/revocation").

JWTs are stateless, so "logout" can't mean "delete the session row" — the issued
token stays cryptographically valid until it expires. This records revoked token
ids in Redis so `get_current_user` can refuse them.

Entries expire exactly when the token itself would have, so the denylist stays
bounded by the number of *unexpired* revoked tokens rather than growing forever.

Unlike the rate limiter, this fails **closed**: if Redis is unreachable we cannot
prove a token wasn't revoked, and silently honoring a logged-out session is a
worse outcome than a temporary auth failure.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from proofhire_api.redis_client import get_redis

logger = logging.getLogger(__name__)


class RevocationBackendUnavailable(Exception):
    pass


def _key(jti: str) -> str:
    return f"revoked_token:{jti}"


async def revoke(jti: str, expires_at: datetime) -> None:
    ttl = int((expires_at - datetime.now(UTC)).total_seconds())
    if ttl <= 0:
        return  # already expired; nothing to deny
    try:
        await get_redis().set(_key(jti), "1", ex=ttl)
    except Exception as exc:
        logger.error("token_revocation_write_failed", extra={"jti": jti})
        raise RevocationBackendUnavailable(str(exc)) from exc


async def is_revoked(jti: str) -> bool:
    try:
        return await get_redis().exists(_key(jti)) == 1
    except Exception as exc:
        logger.error("token_revocation_read_failed", extra={"jti": jti})
        raise RevocationBackendUnavailable(str(exc)) from exc
