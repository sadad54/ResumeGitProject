"""Envelope encryption for third-party tokens at rest (PRD §27: "tokens must never
be stored plaintext"). GitHubConnection.token_ref stores the output of `encrypt()`.

Uses Fernet (symmetric, authenticated encryption) keyed by TOKEN_ENCRYPTION_KEY.
In production this key should come from a managed KMS/secret manager, not a raw
env var — swap `get_settings().token_encryption_key` for a KMS-backed key fetch
when deploying beyond local dev (tracked as a Phase 10 hardening item).
"""

from cryptography.fernet import Fernet

from proofhire_api.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.token_encryption_key.encode("utf-8"))


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
