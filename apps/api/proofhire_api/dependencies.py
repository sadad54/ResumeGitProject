"""Shared FastAPI dependencies: current-user resolution and ownership enforcement.

`get_current_user` is the single choke point every feature router depends on to
scope queries by `user_id` (PRD §27 "row-level ownership checks"). No router should
query a user-owned table without going through this.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.models.user import User
from proofhire_api.security.jwt import InvalidTokenError, TokenType, decode_token_claims
from proofhire_api.security.token_revocation import RevocationBackendUnavailable, is_revoked

bearer_scheme = HTTPBearer(auto_error=False)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def _resolve_user(token: str | None, db: AsyncSession) -> User:
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        claims = decode_token_claims(token, TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    try:
        if await is_revoked(claims.jti):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")
    except RevocationBackendUnavailable as exc:
        # Fail closed: we cannot prove this token wasn't logged out.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication temporarily unavailable"
        ) from exc

    user = await db.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials is not None else None
    user = await _resolve_user(token, db)
    # The seeded guest/demo account (routers/demo.py) is read-only everywhere,
    # enforced here rather than per-router since every feature router already
    # depends on get_current_user for ownership scoping (see module docstring)
    # — one choke point instead of a mutating-endpoint allowlist that a new
    # router could forget to apply.
    if user.is_demo:
        if request.method not in _SAFE_METHODS:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "The demo account is read-only. Sign up to make changes.",
            )
        # Reads are normally unlimited (cheap, ownership-scoped — see
        # security/rate_limit.py), but the demo account is shared by every
        # visitor and some of its GET routes do real work per request (e.g.
        # live export preview re-renders through the real renderer), so it
        # gets its own shared budget the way sync/generate/export do for
        # real accounts. Imported here, not at module level: rate_limit.py
        # itself depends on get_current_user for the per-user limiters above.
        from proofhire_api.security.rate_limit import demo_read_rate_limit

        await demo_read_rate_limit()
    return user
