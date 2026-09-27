"""Deployed environments must refuse the committed placeholder secrets.

The API used to boot in production with AUTH_SECRET_KEY defaulting to the
string in config.py — which is in the public repository, so anyone could have
signed their own access tokens for any user id.
"""

import pytest
from cryptography.fernet import Fernet

from proofhire_api.config import (
    Settings,
    deployment_config_errors,
    deployment_config_warnings,
    get_settings,
)

GOOD = {
    "environment": "production",
    "auth_secret_key": "x" * 48,
    "token_encryption_key": Fernet.generate_key().decode(),
    "web_base_url": "https://proofhire.example",
    "api_base_url": "https://api.proofhire.example",
    "llm_default_provider": "groq",
    "groq_api_key": "not-a-real-key",
    "storage_backend": "s3",
    "s3_bucket_name": "exports",
    "s3_access_key_id": "key-id",
    "s3_secret_access_key": "key-secret",
}


class IsolatedSettings(Settings):
    """Reads only the values passed in. `_env_file=None` is not enough: with a
    developer's .env exported into the shell (GITHUB_OAUTH_CLIENT_ID set,
    redirect on localhost), every case here picked up an extra error."""

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, **_other_sources):
        return (init_settings,)


def settings(**overrides) -> Settings:
    return IsolatedSettings(**{**GOOD, **overrides})


def test_local_development_keeps_zero_setup_defaults():
    assert deployment_config_errors(IsolatedSettings(environment="development")) == []


def test_a_correctly_configured_deployment_passes():
    assert deployment_config_errors(settings()) == []
    assert deployment_config_warnings(settings()) == []


@pytest.mark.parametrize("secret", ["changeme-generate-a-real-secret", "", "short-but-real"])
def test_placeholder_or_weak_jwt_secret_is_refused(secret):
    [error] = deployment_config_errors(settings(auth_secret_key=secret))
    assert "AUTH_SECRET_KEY" in error


@pytest.mark.parametrize("key", ["changeme-generate-a-real-fernet-key", "not-base64-at-all"])
def test_placeholder_or_malformed_encryption_key_is_refused(key):
    [error] = deployment_config_errors(settings(token_encryption_key=key))
    assert "TOKEN_ENCRYPTION_KEY" in error


@pytest.mark.parametrize(
    "url", ["http://localhost:3000", "https://localhost", "http://proofhire.example"]
)
def test_origins_must_be_public_https(url):
    errors = deployment_config_errors(settings(web_base_url=url, api_base_url=url))
    assert any("WEB_BASE_URL" in e for e in errors)
    assert any("API_BASE_URL" in e for e in errors)


def test_oauth_callback_must_point_at_this_api():
    errors = deployment_config_errors(
        settings(
            github_oauth_client_id="Iv1.abc",
            github_oauth_redirect_uri="http://localhost:8000/api/v1/github/callback",
        )
    )
    assert any("GITHUB_OAUTH_REDIRECT_URI" in e for e in errors)
    assert deployment_config_errors(
        settings(
            github_oauth_client_id="Iv1.abc",
            github_oauth_redirect_uri="https://api.proofhire.example/api/v1/github/callback",
        )
    ) == []


def test_every_problem_is_reported_at_once():
    errors = deployment_config_errors(IsolatedSettings(environment="production"))
    assert len(errors) == 4  # secret, encryption key, both origins


def test_s3_without_credentials_is_refused():
    [error] = deployment_config_errors(settings(s3_access_key_id=""))
    assert "S3_ACCESS_KEY_ID" in error
    [error] = deployment_config_errors(settings(storage_backend="gcs"))
    assert "STORAGE_BACKEND" in error


def test_local_storage_in_a_deployment_warns_that_exports_are_ephemeral():
    assert deployment_config_errors(settings(storage_backend="local")) == []
    [warning] = deployment_config_warnings(settings(storage_backend="local"))
    assert "lost on restart" in warning


def test_missing_llm_key_warns_but_does_not_block():
    assert deployment_config_errors(settings(groq_api_key="")) == []
    [warning] = deployment_config_warnings(settings(groq_api_key=""))
    assert "GROQ" in warning.upper()


def test_app_refuses_to_start_with_placeholder_secrets(monkeypatch):
    from proofhire_api.main import create_app

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_SECRET_KEY", "changeme-generate-a-real-secret")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
            create_app()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
