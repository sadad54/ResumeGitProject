"""Object storage for rendered exports (PRD §12.3, checklist §11 / §17).

One interface, two backends, chosen by STORAGE_BACKEND:

- ``local`` — files under LOCAL_STORAGE_ROOT. Local dev, and the single-
  container free deployment where the API and worker share a disk.
- ``s3`` — any S3-compatible store (AWS S3, Cloudflare R2, Supabase Storage,
  MinIO). Required once the API and worker run on separate machines.

Keys are backend-independent (``users/<user_id>/documents/<document_id>.pdf``):
the database never stores a filesystem path, so switching backends needs no
data migration and API responses can't leak server paths. Deterministic keys
mean a re-export overwrites its previous object instead of orphaning it, and
deleting an account is a prefix delete.

Downloads never stream through an authenticated API call: the API checks
ownership, then hands out a short-lived signed URL the browser navigates to
directly. S3 presigns natively; the local backend signs with an HMAC key
derived from AUTH_SECRET_KEY and is served by ``GET /api/v1/files/{key}``.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlencode

from proofhire_api.config import Settings, get_settings

_DEFAULT_LOCAL_ROOT = Path(__file__).resolve().parents[4] / "infra" / "storage"
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$")
_SIGNING_CONTEXT = b"proofhire/object-storage/signed-url/v1"


class ObjectNotFound(Exception):
    pass


class InvalidKey(ValueError):
    pass


@dataclass(frozen=True)
class SignedUrl:
    url: str
    expires_at: int  # unix seconds


def validate_key(key: str) -> str:
    """Keys are relative, slash-separated, no traversal. Checked at every
    entry point: a key that reaches the local backend becomes a path."""
    if not _KEY_PATTERN.match(key) or ".." in key.split("/") or "//" in key:
        raise InvalidKey(f"invalid storage key: {key!r}")
    return key


def document_key(user_id: object, document_id: object, extension: str) -> str:
    return validate_key(f"users/{user_id}/documents/{document_id}.{extension}")


def user_prefix(user_id: object) -> str:
    return f"users/{user_id}/"


class ObjectStorage(Protocol):
    backend: str

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> int: ...

    def signed_url(self, key: str, *, filename: str, ttl_seconds: int) -> SignedUrl: ...

    async def check(self) -> None:
        """Raise if the backend is unusable (readiness probe)."""


# --- local ---------------------------------------------------------------


def _signing_key(secret: str) -> bytes:
    # A purpose-bound subkey: the raw AUTH_SECRET_KEY signs JWTs, and one
    # secret should never serve two protocols directly.
    return hmac.new(secret.encode("utf-8"), _SIGNING_CONTEXT, hashlib.sha256).digest()


def _local_signature(secret: str, key: str, expires: int, filename: str) -> str:
    message = f"{key}\n{expires}\n{filename}".encode()
    return hmac.new(_signing_key(secret), message, hashlib.sha256).hexdigest()


def verify_local_signature(
    secret: str, key: str, expires: int, filename: str, signature: str, *, now: float | None = None
) -> bool:
    if (now if now is not None else time.time()) > expires:
        return False
    expected = _local_signature(secret, key, expires, filename)
    return hmac.compare_digest(expected, signature)


class LocalStorage:
    backend = "local"

    def __init__(self, root: Path, *, api_base_url: str, secret: str) -> None:
        self.root = root.resolve()
        self._api_base_url = api_base_url.rstrip("/")
        self._secret = secret

    def path_for(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidKey(f"storage key escapes the storage root: {key!r}")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self.path_for(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # atomic: a reader never sees a half-written PDF

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        path = self.path_for(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc

    async def exists(self, key: str) -> bool:
        return self.path_for(key).is_file()

    async def delete(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)

    async def delete_prefix(self, prefix: str) -> int:
        base = self.path_for(prefix.rstrip("/"))

        def remove() -> int:
            if not base.is_dir():
                return 0
            files = [p for p in base.rglob("*") if p.is_file()]
            for p in files:
                p.unlink(missing_ok=True)
            for d in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
                d.rmdir()
            base.rmdir()
            return len(files)

        return await asyncio.to_thread(remove)

    def signed_url(self, key: str, *, filename: str, ttl_seconds: int) -> SignedUrl:
        validate_key(key)
        expires = int(time.time()) + ttl_seconds
        query = urlencode(
            {
                "expires": expires,
                "filename": filename,
                "signature": _local_signature(self._secret, key, expires, filename),
            }
        )
        return SignedUrl(f"{self._api_base_url}/api/v1/files/{quote(key)}?{query}", expires)

    async def check(self) -> None:
        def probe() -> None:
            self.root.mkdir(parents=True, exist_ok=True)
            marker = self.root / ".ready"
            marker.write_bytes(b"ok")
            marker.unlink()

        await asyncio.to_thread(probe)


# --- S3 ------------------------------------------------------------------


class S3Storage:
    backend = "s3"

    def __init__(self, settings: Settings) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = settings.s3_bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
            region_name=settings.s3_region,
            # Path-style works on every S3-compatible provider; virtual-hosted
            # style needs DNS per bucket that MinIO/Supabase don't all offer.
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=validate_key(key),
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self.bucket, Key=validate_key(key)
            )
        except self._client.exceptions.NoSuchKey as exc:
            raise ObjectNotFound(key) from exc
        return await asyncio.to_thread(response["Body"].read)

    async def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            await asyncio.to_thread(
                self._client.head_object, Bucket=self.bucket, Key=validate_key(key)
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self.bucket, Key=validate_key(key)
        )

    async def delete_prefix(self, prefix: str) -> int:
        def remove() -> int:
            deleted = 0
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                # delete_objects takes at most 1,000 keys, which is also the
                # list page size, so one call per page.
                if keys:
                    self._client.delete_objects(
                        Bucket=self.bucket, Delete={"Objects": keys, "Quiet": True}
                    )
                    deleted += len(keys)
            return deleted

        return await asyncio.to_thread(remove)

    def signed_url(self, key: str, *, filename: str, ttl_seconds: int) -> SignedUrl:
        url = self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": validate_key(key),
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=ttl_seconds,
        )
        return SignedUrl(url, int(time.time()) + ttl_seconds)

    async def check(self) -> None:
        await asyncio.to_thread(self._client.head_bucket, Bucket=self.bucket)


# --- selection -----------------------------------------------------------


def build_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    if settings.storage_backend == "local":
        root = (
            Path(settings.local_storage_root)
            if settings.local_storage_root
            else _DEFAULT_LOCAL_ROOT
        )
        return LocalStorage(
            root, api_base_url=settings.api_base_url, secret=settings.auth_secret_key
        )
    raise ValueError(f"Unknown STORAGE_BACKEND: {settings.storage_backend!r}")


@lru_cache
def get_object_storage() -> ObjectStorage:
    return build_storage(get_settings())
