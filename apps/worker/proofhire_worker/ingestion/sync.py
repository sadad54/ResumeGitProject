"""Repository sync task: GitHub tree inventory -> classification -> secret scan ->
deterministic tech extraction -> idempotent SourceArtifact persistence
(PRD §15 Stages 1-3, 8).

Runs as a Dramatiq actor. Async work is driven via asyncio.run() since Dramatiq
actors are synchronous entrypoints.
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC

import dramatiq
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.repository import Repository
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.models.sync_run import SyncRun
from proofhire_api.security.token_crypto import decrypt_token
from proofhire_api.telemetry import traced_stage
from proofhire_contracts import RunEventName, SyncStatus
from sqlalchemy import select

from proofhire_worker.db import async_session_factory
from proofhire_worker.events import publish_event
from proofhire_worker.ingestion.classifier import classify, is_excluded
from proofhire_worker.ingestion.secret_scanner import contains_secret
from proofhire_worker.ingestion.staleness import mark_evidence_stale_for_artifacts
from proofhire_worker.ingestion.tech_extraction import extract

logger = logging.getLogger(__name__)

# Bound how many files get their content fetched per repo per sync, so a huge
# monorepo doesn't blow up sync time/cost on a single run (PRD §40 "Repository
# scale/cost" risk mitigation). P0/P1 are always fetched (typically small in
# count); P2 is capped.
MAX_P2_FILES = 60


async def _sync_one_repository(
    session, client, repository: Repository, run_id: uuid.UUID
) -> list[uuid.UUID]:
    """Sync one repository. Returns the ids of artifacts whose content is new or
    changed, so extraction can run over only those."""
    repository.sync_status = SyncStatus.SYNCING
    await session.commit()
    await publish_event(
        str(run_id),
        RunEventName.GITHUB_REPO_ANALYZING,
        {"repository_id": str(repository.id), "owner": repository.owner, "name": repository.name},
    )

    sha = await client.get_default_branch_sha(repository.owner, repository.name, repository.default_branch)
    tree = await client.get_repository_tree(repository.owner, repository.name, sha)

    candidates = []
    p2_count = 0
    for item in tree:
        path = item["path"]
        if is_excluded(path):
            continue
        artifact_type, priority = classify(path)
        if priority.value == "p2":
            if p2_count >= MAX_P2_FILES:
                continue
            p2_count += 1
        candidates.append((path, artifact_type, priority))

    language_summary: dict = dict(repository.language_summary or {})
    created_count = 0
    # Artifacts whose content is new or changed this sync. Only these need
    # re-extraction — re-running the LLM over every unchanged P0/P1 file on each
    # sync is the dominant avoidable cost (PRD §40 "repository scale/cost").
    changed_artifact_ids: list[uuid.UUID] = []
    superseded_artifact_ids: list[uuid.UUID] = []

    for path, artifact_type, priority in candidates:
        content = await client.get_file_content(repository.owner, repository.name, path, sha)
        if content is None:
            continue
        if contains_secret(content):
            logger.warning("secret_scan_flagged", extra={"repository_id": str(repository.id), "path": path})
            continue

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        prior_at_path = list(
            (
                await session.scalars(
                    select(SourceArtifact).where(
                        SourceArtifact.repository_id == repository.id,
                        SourceArtifact.path == path,
                    )
                )
            ).all()
        )
        if any(a.content_hash == content_hash for a in prior_at_path):
            continue  # unchanged since last sync — idempotent skip

        # Reached only when this path is new, or its content actually changed.
        # Any earlier rows for the path are now superseded, so evidence citing
        # them no longer describes what is at this commit.
        superseded_artifact_ids.extend(a.id for a in prior_at_path)

        deterministic_metadata = extract(path, content)
        if deterministic_metadata:
            for key in ("dependencies", "frameworks", "ci_provider", "base_images"):
                if key in deterministic_metadata:
                    language_summary.setdefault(key, [])
                    if isinstance(deterministic_metadata[key], list):
                        merged = set(language_summary[key]) | set(deterministic_metadata[key])
                        language_summary[key] = sorted(merged)

        artifact = SourceArtifact(
            repository_id=repository.id,
            type=artifact_type,
            path=path,
            commit_sha=sha,
            content_hash=content_hash,
            priority=priority,
            metadata_json=deterministic_metadata,
        )
        session.add(artifact)
        await session.flush()  # assigns artifact.id
        changed_artifact_ids.append(artifact.id)
        created_count += 1

    stale_count = await mark_evidence_stale_for_artifacts(session, superseded_artifact_ids)

    repository.last_commit_sha = sha
    repository.last_analyzed_sha = sha
    repository.language_summary = language_summary
    repository.sync_status = SyncStatus.COMPLETED
    await session.commit()

    await publish_event(
        str(run_id),
        RunEventName.GITHUB_REPO_COMPLETED,
        {
            "repository_id": str(repository.id),
            "artifacts_created": created_count,
            "files_scanned": len(candidates),
            "evidence_marked_stale": stale_count,
        },
    )

    return changed_artifact_ids


@traced_stage("repository_sync")
async def _run(run_id_str: str, repository_ids: list[str]) -> None:
    from proofhire_api.services.github_client import GitHubClient

    run_id = uuid.UUID(run_id_str)

    async with async_session_factory() as session:
        sync_run = await session.get(SyncRun, run_id)
        if sync_run is None:
            logger.error("sync_run_not_found", extra={"run_id": run_id_str})
            return

        sync_run.status = SyncStatus.SYNCING
        await session.commit()
        await publish_event(run_id_str, RunEventName.GITHUB_SYNC_STARTED, {"run_id": run_id_str})

        try:
            for repo_id_str in repository_ids:
                repo_id = uuid.UUID(repo_id_str)
                repository = await session.get(Repository, repo_id)
                if repository is None:
                    continue

                connection = await session.scalar(
                    select(GitHubConnection).where(GitHubConnection.user_id == repository.user_id)
                )
                if connection is None:
                    repository.sync_status = SyncStatus.FAILED
                    await session.commit()
                    continue

                token = decrypt_token(connection.token_ref)
                client = GitHubClient(token)
                changed_artifact_ids = await _sync_one_repository(
                    session, client, repository, run_id
                )

                if not changed_artifact_ids:
                    # Nothing changed since the last sync, so there is nothing new
                    # to extract. Skipping here is what makes a re-sync cheap
                    # instead of re-running the LLM over the whole repository.
                    logger.info(
                        "extraction_skipped_no_changes",
                        extra={"repository_id": str(repository.id), "run_id": run_id_str},
                    )
                    continue

                # Enqueued on the separate `ai` queue rather than called inline —
                # keeps ingestion (this module) and intelligence (Phase 2+) scaling
                # independently per PRD §28, and means a slow/failed LLM call can't
                # block the rest of this sync run.
                from proofhire_worker.intelligence.evidence_extraction import extract_evidence

                extract_evidence.send(
                    str(repository.id),
                    run_id_str,
                    [str(a) for a in changed_artifact_ids],
                )

            sync_run.status = SyncStatus.COMPLETED
        except Exception as exc:
            sync_run.status = SyncStatus.FAILED
            sync_run.error = str(exc)
            logger.exception("sync_run_failed", extra={"run_id": run_id_str})
        finally:
            from datetime import datetime

            sync_run.completed_at = datetime.now(UTC)
            await session.commit()


@dramatiq.actor(max_retries=2, queue_name="ingest")
def sync_repositories(run_id: str, repository_ids: list[str]) -> None:
    asyncio.run(_run(run_id, repository_ids))
