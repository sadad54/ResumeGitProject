"""Object storage for rendered documents (PRD §12.3 "S3-compatible object
storage"). No MinIO/S3 instance is available in this dev environment, so this
is a local-disk stand-in behind the same shape of interface (save -> ref,
ref -> bytes) that a real S3 client would have. Swap the implementation for a
boto3-backed one when deploying somewhere S3/MinIO is actually available —
callers (export task, API) only depend on save_bytes/read_bytes, not on how
storage actually works.
"""

import os
import uuid
from pathlib import Path

# infra/storage/ is already gitignored (Phase 0) precisely for this purpose.
_DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "infra" / "storage"
STORAGE_ROOT = Path(os.environ.get("LOCAL_STORAGE_ROOT", str(_DEFAULT_ROOT)))


def save_bytes(subdir: str, extension: str, data: bytes) -> str:
    """Returns a storage_ref (absolute local path) suitable for storing in
    GeneratedDocument.pdf_ref/html_ref/plaintext_ref."""
    target_dir = STORAGE_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.{extension}"
    path = target_dir / filename
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return str(path)


def read_bytes(storage_ref: str) -> bytes:
    return Path(storage_ref).read_bytes()
