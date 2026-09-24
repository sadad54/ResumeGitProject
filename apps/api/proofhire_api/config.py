"""Application settings, loaded from environment (.env in local dev).

See .env.example at the repo root for the full list of expected variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "proofhire-dev"

    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""

    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
