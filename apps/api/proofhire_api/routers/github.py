import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from proofhire_contracts import SyncStatus
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from proofhire_api.config import get_settings
from proofhire_api.db import get_db
from proofhire_api.dependencies import get_current_user
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.repository import Repository
from proofhire_api.models.sync_run import SyncRun
from proofhire_api.models.user import User
from proofhire_api.schemas.github import (
    ConnectResponse,
    RepositoryPatch,
    RepositoryPublic,
    SyncStatusResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
)
from proofhire_api.security.rate_limit import sync_rate_limit
from proofhire_api.security.token_crypto import decrypt_token, encrypt_token
from proofhire_api.services.github_client import GitHubClient
from proofhire_api.services.github_oauth import (
    GitHubOAuthError,
    build_authorize_url,
    exchange_code_for_token,
    fetch_github_user,
    verify_oauth_state,
)

router = APIRouter(prefix="/api/v1/github", tags=["github"])


@router.post("/connect", response_model=ConnectResponse)
async def connect(current_user: User = Depends(get_current_user)) -> ConnectResponse:
    return ConnectResponse(authorize_url=build_authorize_url(current_user.id))


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect GitHub: drop the stored OAuth token and the repositories it
    gave access to.

    Evidence already extracted is deliberately kept — it belongs to the user's
    profile, not to the connection, and silently destroying a reviewed evidence
    graph because a token was disconnected would be a nasty surprise. Use
    account deletion to erase everything.
    """
    connection = await db.scalar(
        select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    )
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No GitHub connection")

    await db.execute(delete(Repository).where(Repository.user_id == current_user.id))
    await db.delete(connection)
    await db.commit()


@router.get("/callback")
async def callback(code: str, state: str, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    settings = get_settings()
    try:
        user_id = verify_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        access_token = await exchange_code_for_token(code)
        github_user = await fetch_github_user(access_token)
    except GitHubOAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    connection = await db.scalar(
        select(GitHubConnection).where(GitHubConnection.user_id == user_id)
    )
    encrypted = encrypt_token(access_token)
    if connection is None:
        connection = GitHubConnection(
            user_id=user_id,
            github_user_id=github_user["id"],
            login=github_user["login"],
            token_ref=encrypted,
            scopes=[],
        )
        db.add(connection)
    else:
        connection.github_user_id = github_user["id"]
        connection.login = github_user["login"]
        connection.token_ref = encrypted

    await db.commit()

    return RedirectResponse(url=f"{settings.web_base_url}/settings?github=connected")


@router.get("/repositories", response_model=list[RepositoryPublic])
async def list_repositories(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Repository]:
    """Lists repositories already known to ProofHire. Call POST /github/repositories/refresh
    first (or after connecting) to pull the latest list from GitHub."""
    result = await db.scalars(
        select(Repository).where(Repository.user_id == current_user.id).order_by(Repository.name)
    )
    return list(result.all())


@router.post("/repositories/refresh", response_model=list[RepositoryPublic])
async def refresh_repositories(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Repository]:
    """Pulls the user's repository list from GitHub and upserts local rows.
    Does not fetch file content — that happens in POST /github/sync."""
    connection = await db.scalar(
        select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    )
    if connection is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub is not connected")

    client = GitHubClient(decrypt_token(connection.token_ref))
    remote_repos = await client.list_user_repositories()

    existing = await db.scalars(
        select(Repository).where(Repository.user_id == current_user.id)
    )
    by_provider_id = {r.provider_repo_id: r for r in existing.all()}

    for remote in remote_repos:
        repo = by_provider_id.get(remote["id"])
        if repo is None:
            repo = Repository(
                user_id=current_user.id,
                provider_repo_id=remote["id"],
                owner=remote["owner"]["login"],
                name=remote["name"],
                url=remote["html_url"],
                visibility="private" if remote.get("private") else "public",
                default_branch=remote.get("default_branch", "main"),
                stars=remote.get("stargazers_count", 0),
            )
            db.add(repo)
        else:
            repo.stars = remote.get("stargazers_count", 0)
            repo.default_branch = remote.get("default_branch", "main")
            repo.visibility = "private" if remote.get("private") else "public"

    await db.commit()

    result = await db.scalars(
        select(Repository).where(Repository.user_id == current_user.id).order_by(Repository.name)
    )
    return list(result.all())


@router.patch("/repositories/{repository_id}", response_model=RepositoryPublic)
async def patch_repository(
    repository_id: uuid.UUID,
    body: RepositoryPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Repository:
    repo = await db.get(Repository, repository_id)
    if repo is None or repo.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found")
    repo.selected = body.selected
    await db.commit()
    await db.refresh(repo)
    return repo


@router.post(
    "/sync",
    response_model=SyncTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(sync_rate_limit)],
)
async def trigger_sync(
    body: SyncTriggerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncTriggerResponse:
    from proofhire_worker.broker import broker  # noqa: F401  (configures the Redis broker)
    from proofhire_worker.ingestion.sync import sync_repositories

    repos = await db.scalars(
        select(Repository).where(
            Repository.id.in_(body.repository_ids), Repository.user_id == current_user.id
        )
    )
    repo_ids = [str(r.id) for r in repos.all()]
    if not repo_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No matching repositories")

    sync_run = SyncRun(user_id=current_user.id, repository_ids=repo_ids, status=SyncStatus.QUEUED)
    db.add(sync_run)
    await db.commit()
    await db.refresh(sync_run)

    sync_repositories.send(str(sync_run.id), repo_ids)

    return SyncTriggerResponse(run_id=sync_run.id, status=sync_run.status)


@router.get("/sync/{run_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    sync_run = await db.get(SyncRun, run_id)
    if sync_run is None or sync_run.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sync run not found")
    return SyncStatusResponse(
        run_id=sync_run.id,
        status=sync_run.status,
        repository_ids=sync_run.repository_ids,
        error=sync_run.error,
    )
