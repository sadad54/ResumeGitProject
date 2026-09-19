from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import bearer_scheme, get_current_user
from proofhire_api.models.user import User
from proofhire_api.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserPublic,
)
from proofhire_api.security.jwt import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token_claims,
)
from proofhire_api.security.password import hash_password, verify_password
from proofhire_api.security.token_revocation import (
    RevocationBackendUnavailable,
    is_revoked,
    revoke,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        claims = decode_token_claims(body.refresh_token, TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc

    try:
        if await is_revoked(claims.jti):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has been revoked")
    except RevocationBackendUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication temporarily unavailable"
        ) from exc

    user = await db.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    # Rotation means the presented refresh token is spent: revoke it so a
    # captured copy can't be replayed to mint further sessions.
    await revoke(claims.jti, claims.expires_at)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    _current_user: User = Depends(get_current_user),
) -> None:
    """Revoke this session's tokens.

    Both tokens are revoked: dropping only the access token would leave the
    refresh token able to mint a fresh one, which is not a logout.
    """
    if credentials is not None:
        access_claims = decode_token_claims(credentials.credentials, TokenType.ACCESS)
        await revoke(access_claims.jti, access_claims.expires_at)

    if body.refresh_token:
        try:
            refresh_claims = decode_token_claims(body.refresh_token, TokenType.REFRESH)
        except InvalidTokenError:
            return  # already unusable; nothing to revoke
        await revoke(refresh_claims.jti, refresh_claims.expires_at)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete the account and everything owned by it.

    Hard delete, by design (see docs/adr/0016-deletion-policy.md): this is the
    user's own data-erasure path, so leaving soft-deleted rows behind would
    defeat the point. Every owned table cascades from `users`, including the
    encrypted GitHub token.
    """
    await db.delete(current_user)
    await db.commit()
