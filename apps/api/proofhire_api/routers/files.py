"""Serves signed download URLs minted by the local storage backend.

S3 deployments never reach this: their signed URLs point at the bucket. For
the local backend this plays the bucket's part — no bearer token, the HMAC
signature over (key, expiry, filename) is the whole authorization, so it can
be an ordinary link the browser navigates to. The signature is only ever
issued by GET /documents/{id}/download, after the ownership check.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from proofhire_api.config import get_settings
from proofhire_api.services.object_storage import (
    InvalidKey,
    LocalStorage,
    get_object_storage,
    verify_local_signature,
)

router = APIRouter(prefix="/api/v1/files", tags=["files"])

_MEDIA_TYPES = {"pdf": "application/pdf", "txt": "text/plain; charset=utf-8"}


@router.get("/{key:path}", include_in_schema=False)
async def get_signed_file(key: str, expires: int, filename: str, signature: str) -> FileResponse:
    storage = get_object_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    # One response for a bad signature, an expired link and a traversal
    # attempt alike: nothing here should help someone probe for valid keys.
    denied = HTTPException(
        status.HTTP_403_FORBIDDEN, "This download link is invalid or has expired"
    )
    secret = get_settings().auth_secret_key
    if not verify_local_signature(secret, key, expires, filename, signature):
        raise denied
    try:
        path = storage.path_for(key)
    except InvalidKey as exc:
        raise denied from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_410_GONE, "This export has expired — export it again")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(path.suffix.lstrip("."), "application/octet-stream"),
        filename=filename,
        # Attachment + no caching: a signed link is a one-off capability.
        headers={"Cache-Control": "private, no-store"},
    )
