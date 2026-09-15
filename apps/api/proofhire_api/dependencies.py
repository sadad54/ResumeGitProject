"""Shared FastAPI dependencies: current-user resolution and ownership enforcement.

`get_current_user` is the single choke point every feature router depends on to
scope queries by `user_id` (PRD §27 "row-level ownership checks"). No router should
query a user-owned table without going through this.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.models.user import User
from proofhire_api.security.jwt import InvalidTokenError, TokenType, decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_user(token: str | None, db: AsyncSession) -> User:
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        user_id = decode_token(token, TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials is not None else None
    return await _resolve_user(token, db)


async def get_current_user_sse(
    access_token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Same as get_current_user, but also accepts the token as an `access_token`
    query param — the browser's native EventSource API cannot set custom headers,
    so SSE routes need this fallback (PRD §23 SSE streaming)."""
    token = credentials.credentials if credentials is not None else access_token
    return await _resolve_user(token, db)
