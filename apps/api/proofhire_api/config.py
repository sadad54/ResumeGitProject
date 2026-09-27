"""Application settings, loaded from environment (.env in local dev).

See .env.example at the repo root for the full list of expected variables.
"""

import logging
from functools import lru_cache
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# The committed defaults below exist so local dev and tests start with zero
# setup. In a deployed environment every one of them is a vulnerability: a
# JWT signed with a secret that is in the public repository can be forged by
# anyone who reads it.
_PLACEHOLDER_SECRETS = frozenset(
    {"changeme-generate-a-real-secret", "changeme-generate-a-real-fernet-key", ""}
)
DEPLOYED_ENVIRONMENTS = frozenset({"production", "staging"})
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+asyncpg://proofhire:proofhire@localhost:5432/proofhire"
    redis_url: str = "redis://localhost:6379/0"

    auth_secret_key: str = "changeme-generate-a-real-secret"
    auth_access_token_expire_minutes: int = 30
    auth_refresh_token_expire_days: int = 30

    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_redirect_uri: str = "http://localhost:3000/api/github/callback"

    token_encryption_key: str = "changeme-generate-a-real-fernet-key"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    llm_default_provider: str = "anthropic"

    # Rendered exports (services/object_storage.py). "local" writes under
    # LOCAL_STORAGE_ROOT (default: repo infra/storage, gitignored); "s3" uses
    # any S3-compatible endpoint below.
    storage_backend: str = "local"
    local_storage_root: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "proofhire-dev"
    s3_region: str = "us-east-1"
    download_url_ttl_seconds: int = 300

    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""

    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _is_public_https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "") not in _LOCAL_HOSTS


def deployment_config_errors(settings: Settings) -> list[str]:
    """Every reason these settings are unsafe to serve real users with.

    Empty outside DEPLOYED_ENVIRONMENTS: local dev keeps its zero-setup
    defaults. Pure, so tests can check each rule without booting the app.
    """
    if settings.environment not in DEPLOYED_ENVIRONMENTS:
        return []
    errors: list[str] = []
    if settings.auth_secret_key in _PLACEHOLDER_SECRETS or len(settings.auth_secret_key) < 32:
        errors.append(
            "AUTH_SECRET_KEY is unset, the committed placeholder, or shorter than 32 "
            "characters (tokens signed with it are forgeable)"
        )
    if settings.token_encryption_key in _PLACEHOLDER_SECRETS:
        errors.append("TOKEN_ENCRYPTION_KEY is unset or the committed placeholder")
    else:
        try:
            Fernet(settings.token_encryption_key.encode("utf-8"))
        except ValueError:
            errors.append("TOKEN_ENCRYPTION_KEY is not a valid Fernet key")
    for name in ("web_base_url", "api_base_url"):
        value = getattr(settings, name)
        if not _is_public_https(value):
            errors.append(f"{name.upper()} must be a public https:// origin, got {value!r}")
    if settings.github_oauth_client_id and not settings.github_oauth_redirect_uri.startswith(
        settings.api_base_url.rstrip("/") + "/"
    ):
        errors.append(
            "GITHUB_OAUTH_REDIRECT_URI must be this API's own /api/v1/github/callback "
            f"(API_BASE_URL is {settings.api_base_url!r})"
        )
    if settings.storage_backend not in {"local", "s3"}:
        errors.append(f"STORAGE_BACKEND must be 'local' or 's3', got {settings.storage_backend!r}")
    elif settings.storage_backend == "s3" and not (
        settings.s3_bucket_name and settings.s3_access_key_id and settings.s3_secret_access_key
    ):
        errors.append(
            "STORAGE_BACKEND=s3 needs S3_BUCKET_NAME, S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY"
        )
    return errors


def deployment_config_warnings(settings: Settings) -> list[str]:
    """Degraded-but-safe configuration: worth a loud log line, not a refusal
    to start (the container smoke test deliberately runs a deployed
    environment on the mock provider)."""
    if settings.environment not in DEPLOYED_ENVIRONMENTS:
        return []
    warnings: list[str] = []
    provider = settings.llm_default_provider
    keys = {
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
    }
    if provider == "mock":
        warnings.append(
            "LLM_DEFAULT_PROVIDER=mock: analysis and generation return empty placeholders"
        )
    elif provider in keys and not keys[provider]:
        warnings.append(
            f"LLM_DEFAULT_PROVIDER={provider} but its API key is not set: every LLM task will fail"
        )
    if settings.storage_backend == "local":
        warnings.append(
            "STORAGE_BACKEND=local: exports live on this container's disk and are lost on "
            "restart (the UI re-offers export when a file has gone)"
        )
    return warnings


def validate_deployment_config(settings: Settings | None = None) -> None:
    """Called at API and worker startup. Raises with every problem at once,
    so one failed deploy shows the whole list instead of one per attempt."""
    settings = settings or get_settings()
    for warning in deployment_config_warnings(settings):
        logger.warning("deployment_config_degraded", extra={"reason": warning})
    errors = deployment_config_errors(settings)
    if errors:
        raise RuntimeError(
            f"Refusing to start with ENVIRONMENT={settings.environment}: " + "; ".join(errors)
        )
