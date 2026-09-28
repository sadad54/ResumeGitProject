"""Workspace overview: what the signed-in user has, in one request.

Backs the Overview page (where a user lands after sign-in) and tells the UI
whether GitHub is connected, which nothing else exposed: the OAuth callback
redirects to /settings?github=connected, but a page load after that had no
way to ask. One statement with scalar subqueries, so the page costs one
round trip however many counters it shows.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.user import User
from proofhire_api.schemas.overview import OverviewResponse

router = APIRouter(prefix="/api/v1/me", tags=["overview"])

_OVERVIEW_SQL = text(
    """
    SELECT
      (SELECT login FROM github_connections WHERE user_id = :u) AS github_login,
      (SELECT connected_at FROM github_connections WHERE user_id = :u) AS github_connected_at,
      (SELECT last_sync_at FROM github_connections WHERE user_id = :u) AS github_last_sync_at,
      (SELECT count(*) FROM repositories WHERE user_id = :u) AS repositories_total,
      (SELECT count(*) FROM repositories WHERE user_id = :u AND selected) AS repositories_selected,
      (SELECT count(*) FROM repositories
         WHERE user_id = :u AND last_analyzed_sha IS NOT NULL) AS repositories_synced,
      (SELECT count(*) FROM repositories WHERE user_id = :u
         AND sync_status IN ('queued', 'syncing', 'extracting')) AS repositories_in_progress,
      (SELECT count(*) FROM evidence WHERE user_id = :u) AS evidence_total,
      (SELECT count(*) FROM evidence WHERE user_id = :u AND status = 'confirmed')
         AS evidence_confirmed,
      (SELECT count(*) FROM evidence WHERE user_id = :u AND status = 'candidate')
         AS evidence_candidate,
      (SELECT count(*) FROM evidence WHERE user_id = :u AND status = 'stale') AS evidence_stale,
      (SELECT count(*) FROM jobs WHERE user_id = :u) AS jobs_total,
      (SELECT count(*) FROM jobs WHERE user_id = :u AND status = 'ready') AS jobs_ready,
      (SELECT count(*) FROM generated_documents d JOIN jobs j ON j.id = d.job_id
         WHERE j.user_id = :u) AS documents_total,
      (SELECT count(*) FROM generated_documents d JOIN jobs j ON j.id = d.job_id
         WHERE j.user_id = :u AND d.pdf_ref IS NOT NULL) AS documents_exported,
      (SELECT count(*) FROM applications WHERE user_id = :u) AS applications_total,
      (SELECT count(*) FROM applications WHERE user_id = :u
         AND stage IN ('applied', 'screen', 'interview', 'offer')) AS applications_active
    """
)


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    row = (await db.execute(_OVERVIEW_SQL, {"u": current_user.id})).mappings().one()
    return OverviewResponse.model_validate(
        {
            "github": {
                "connected": row["github_login"] is not None,
                "login": row["github_login"],
                "connected_at": row["github_connected_at"],
                "last_sync_at": row["github_last_sync_at"],
            },
            "repositories": {
                "total": row["repositories_total"],
                "selected": row["repositories_selected"],
                "synced": row["repositories_synced"],
                "in_progress": row["repositories_in_progress"],
            },
            "evidence": {
                "total": row["evidence_total"],
                "confirmed": row["evidence_confirmed"],
                "candidate": row["evidence_candidate"],
                "stale": row["evidence_stale"],
            },
            "jobs": {"total": row["jobs_total"], "ready": row["jobs_ready"]},
            "documents": {
                "total": row["documents_total"],
                "exported": row["documents_exported"],
            },
            "applications": {
                "total": row["applications_total"],
                "active": row["applications_active"],
            },
        }
    )
