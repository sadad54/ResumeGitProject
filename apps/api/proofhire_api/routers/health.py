"""Health/readiness endpoints. Not versioned under /api/v1 (PRD §23 versions feature
endpoints, not infra-level health checks)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness gates traffic, so it must reflect every dependency a request
    can fail on. Redis is included because token revocation fails closed
    (security/token_revocation.py): with Redis down, every authenticated
    request returns 503, which is not a state to route traffic into."""
    checks = {"postgres": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["postgres"] = "unavailable"

    try:
        await get_redis().ping()
    except Exception:
        checks["redis"] = "unavailable"

    if any(v != "ok" for v in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", **checks}
    return {"status": "ready", **checks}
