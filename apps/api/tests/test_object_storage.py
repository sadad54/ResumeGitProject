"""Object storage backends (services/object_storage.py): the local backend
against a temp directory, the S3 backend against moto's in-process S3 — same
contract, so the API and worker can't tell them apart."""

import time
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from proofhire_api.config import Settings
from proofhire_api.services.object_storage import (
    InvalidKey,
    LocalStorage,
    ObjectNotFound,
    S3Storage,
    document_key,
    user_prefix,
    validate_key,
    verify_local_signature,
)

SECRET = "s" * 48


@pytest.fixture
def local(tmp_path):
    return LocalStorage(tmp_path, api_base_url="https://api.example", secret=SECRET)


@pytest.fixture
def s3():
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        settings = Settings(
            _env_file=None,
            storage_backend="s3",
            s3_bucket_name="exports",
            s3_access_key_id="testing",
            s3_secret_access_key="testing",
            s3_region="us-east-1",
        )
        storage = S3Storage(settings)
        storage._client.create_bucket(Bucket="exports")
        yield storage


@pytest.mark.parametrize(
    "key",
    [
        "../etc/passwd", "/abs/path", "users//x", "users/../../x",
        "users/a/../../../x", "", ".hidden",
    ],
)
def test_traversal_and_malformed_keys_are_rejected(key):
    with pytest.raises(InvalidKey):
        validate_key(key)


def test_document_keys_are_owner_scoped_and_deterministic():
    key = document_key("u1", "d1", "pdf")
    assert key == "users/u1/documents/d1.pdf"
    assert key.startswith(user_prefix("u1"))
    assert document_key("u1", "d1", "pdf") == key


@pytest.mark.parametrize("backend", ["local", "s3"])
async def test_put_get_exists_delete_roundtrip(backend, request):
    storage = request.getfixturevalue(backend)
    key = document_key("u1", "d1", "pdf")
    assert not await storage.exists(key)
    with pytest.raises(ObjectNotFound):
        await storage.get(key)

    await storage.put(key, b"%PDF-1.7 v1", "application/pdf")
    await storage.put(key, b"%PDF-1.7 v2", "application/pdf")  # overwrite, not a second object
    assert await storage.get(key) == b"%PDF-1.7 v2"
    assert await storage.exists(key)

    await storage.delete(key)
    assert not await storage.exists(key)


@pytest.mark.parametrize("backend", ["local", "s3"])
async def test_delete_prefix_removes_only_that_users_objects(backend, request):
    storage = request.getfixturevalue(backend)
    for ext in ("pdf", "html", "txt"):
        await storage.put(document_key("alice", "d1", ext), b"x", "text/plain")
    await storage.put(document_key("alice", "d2", "pdf"), b"x", "application/pdf")
    await storage.put(document_key("bob", "d3", "pdf"), b"x", "application/pdf")

    assert await storage.delete_prefix(user_prefix("alice")) == 4
    assert not await storage.exists(document_key("alice", "d1", "pdf"))
    assert await storage.exists(document_key("bob", "d3", "pdf"))
    assert await storage.delete_prefix(user_prefix("nobody")) == 0


def test_local_signed_url_verifies_and_rejects_tampering(local):
    link = local.signed_url("users/u1/documents/d1.pdf", filename="resume.pdf", ttl_seconds=60)
    parsed = urlparse(link.url)
    assert parsed.scheme == "https" and parsed.netloc == "api.example"
    key = unquote(parsed.path.removeprefix("/api/v1/files/"))
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    expires = int(q["expires"])
    assert link.expires_at == expires

    assert verify_local_signature(SECRET, key, expires, q["filename"], q["signature"])
    # Any change to what was signed invalidates it.
    other_key = "users/u2/documents/d1.pdf"
    assert not verify_local_signature(SECRET, other_key, expires, q["filename"], q["signature"])
    assert not verify_local_signature(SECRET, key, expires + 60, q["filename"], q["signature"])
    assert not verify_local_signature(SECRET, key, expires, "other.pdf", q["signature"])
    assert not verify_local_signature("x" * 48, key, expires, q["filename"], q["signature"])
    # And it stops working once expired.
    assert not verify_local_signature(
        SECRET, key, expires, q["filename"], q["signature"], now=time.time() + 120
    )


def test_s3_signed_url_is_a_presigned_attachment(s3):
    link = s3.signed_url("users/u1/documents/d1.pdf", filename="resume.pdf", ttl_seconds=60)
    query = parse_qs(urlparse(link.url).query)
    assert "X-Amz-Signature" in query
    assert query["X-Amz-Expires"] == ["60"]
    assert query["response-content-disposition"] == ['attachment; filename="resume.pdf"']


async def test_readiness_check_passes_on_a_working_backend(local, s3):
    await local.check()
    await s3.check()
