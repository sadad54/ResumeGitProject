"""Shared paste/extension entry point. Never fetch an untrusted capture URL."""

import uuid
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, Field, field_validator


class JobCaptureRequest(BaseModel):
    capture_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    selected_text: str = Field(min_length=40, max_length=60000)
    page_url: str | None = Field(default=None, max_length=2048)
    title: str | None = Field(default=None, max_length=500)
    captured_at: AwareDatetime | None = None

    @field_validator("selected_text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 40:
            raise ValueError("Paste at least 40 characters of job description")
        return value

    @field_validator("page_url")
    @classmethod
    def safe_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("page_url must be an HTTP(S) URL without credentials")
        return value
