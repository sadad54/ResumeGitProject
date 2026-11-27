import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    # Optional so a client that has already dropped its refresh token can still
    # revoke the access token it's holding.
    refresh_token: str | None = None


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    created_at: datetime
    # The shared read-only guest account (routers/demo.py). The UI uses it to
    # disable writes up front instead of letting each one fail with a 403.
    is_demo: bool = False

    model_config = {"from_attributes": True}
