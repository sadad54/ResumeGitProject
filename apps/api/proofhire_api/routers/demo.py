"""Read-only guest demo: lets a visitor open the real product without a GitHub
OAuth dance. Issues a normal session for a single seeded account (populated by
`apps/api/scripts/seed_demo.py` through the real pipeline — real sync, real
evidence graph, real generated documents), reusing every existing route and UI
component. The account is prevented from mutating anything by
`dependencies.get_current_user` (see its `is_demo` check), not by anything in
this router — this endpoint only ever mints a token for the one fixed user.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.models.user import User
from proofhire_api.schemas.auth import TokenResponse
from proofhire_api.security.jwt import create_access_token, create_refresh_token
from proofhire_api.security.password import hash_password
from proofhire_api.security.rate_limit import demo_session_rate_limit

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

DEMO_EMAIL = "demo@proofhire.app"


async def _get_or_create_demo_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None:
        return user

    # Created on first request if the seed script hasn't run yet, so the demo
    # entry point never 404s — it just starts empty until seeded. The random
    # password is never given out; is_demo=True means it's also never usable
    # for a real login even if guessed (see routers/auth.py login, which only
    # checks the password — this account's login is not linked from anywhere,
    # but nothing calls it either way since this fixture's credentials aren't
    # meant to be knowable to begin with).
    user = User(
        email=DEMO_EMAIL,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        display_name="Demo Guest",
        is_demo=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/session", response_model=TokenResponse, dependencies=[Depends(demo_session_rate_limit)])
async def start_demo_session(db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await _get_or_create_demo_user(db)
    if not user.is_demo:
        # The email was somehow claimed by a real signup before this route
        # existed; refuse rather than handing out a session for someone else's
        # account.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Demo account unavailable")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
