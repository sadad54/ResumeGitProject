"""Semantic evidence extraction (PRD §15 Stage 4, §34 B2).

Runs as its own Dramatiq actor on the `ai` queue, decoupled from ingestion (the
`ingest` queue) so the two can scale independently (PRD §28 "Scale path") — the
sync task enqueues this rather than calling it inline.

Re-fetches file content from GitHub for the SourceArtifacts a sync already
classified as P0/P1 (bounded set), since V1 doesn't persist raw file content to
object storage yet (that lands in Phase 6). Content is fetched, embedded, and
discarded — never itself stored, only the derived Evidence/EvidenceSource rows are.
"""

import hashlib
import logging
import uuid

import dramatiq
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.repository import Repository
from proofhire_api.models.source_artifact import SourceArtifact
from proofhire_api.repositories.evidence import (
    EvidenceCandidate,
    EvidenceSourceCandidate,
    SQLAlchemyEvidenceRepository,
)
from proofhire_api.security.token_crypto import decrypt_token
from proofhire_api.services.github_client import GitHubClient
from proofhire_api.telemetry import traced_stage
from proofhire_contracts import EvidenceType, RunEventName, SyncStatus
from proofhire_prompts.evidence_extract_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from sqlalchemy import select, update

from proofhire_worker.db import async_session_factory
from proofhire_worker.events import publish_event
from proofhire_worker.intelligence.confidence import combine_confidence
from proofhire_worker.intelligence.embeddings import evidence_embedding_text
from proofhire_worker.intelligence.llm_provider import Message
from proofhire_worker.intelligence.model_selection import config_for
from proofhire_worker.intelligence.provider_factory import get_embedding_provider, get_provider
from proofhire_worker.intelligence.schemas import EvidenceExtractionOutput

logger = logging.getLogger(__name__)

# Bound how many characters go into one LLM call, so a batch of files stays within
# a reasonable context window and cost envelope (PRD §40 "Repository scale/cost").
MAX_GROUP_CHARS = 12000
MAX_FILE_CHARS = 4000


def _group_files(files: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    groups: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_size = 0

    for path, content in files:
        truncated = content[:MAX_FILE_CHARS]
        if current and current_size + len(truncated) > MAX_GROUP_CHARS:
            groups.append(current)
            current = []
            current_size = 0
        current.append((path, truncated))
        current_size += len(truncated)

    if current:
        groups.append(current)
    return groups


async def _settle_repository(repository_id: uuid.UUID, status: SyncStatus) -> None:
    async with async_session_factory() as session:
        await session.execute(
            update(Repository).where(Repository.id == repository_id).values(sync_status=status)
        )
        await session.commit()


@traced_stage("evidence_extraction")
async def _extract_for_repository(
    repository_id_str: str, run_id_str: str, artifact_ids: list[str] | None = None
) -> None:
    """Extract, then always settle the repository out of `extracting` (set by
    sync.py when it queued this run), so the UI and anyone polling learn that
    extraction ended however it ended: COMPLETED, or FAILED when it couldn't
    run or no LLM call succeeded. Settled from a fresh session, since the
    working session may be unusable after whatever failed."""
    repository_id = uuid.UUID(repository_id_str)
    outcome = SyncStatus.FAILED
    try:
        outcome = await _extract(repository_id, run_id_str, artifact_ids)
    finally:
        await _settle_repository(repository_id, outcome)


async def _extract(
    repository_id: uuid.UUID, run_id_str: str, artifact_ids: list[str] | None
) -> SyncStatus:
    repository_id_str = str(repository_id)
    model_config = config_for("evidence_extract")

    async with async_session_factory() as session:
        repository = await session.get(Repository, repository_id)
        if repository is None:
            logger.error("repository_not_found", extra={"repository_id": repository_id_str})
            return SyncStatus.FAILED

        connection = await session.scalar(
            select(GitHubConnection).where(GitHubConnection.user_id == repository.user_id)
        )
        if connection is None:
            logger.error("github_not_connected", extra={"repository_id": repository_id_str})
            return SyncStatus.FAILED

        client = GitHubClient(decrypt_token(connection.token_ref))

        stmt = select(SourceArtifact).where(
            SourceArtifact.repository_id == repository_id,
            SourceArtifact.priority.in_(["p0", "p1"]),
        )
        if artifact_ids:
            # Incremental re-sync: only artifacts whose content actually changed.
            # Absent (None) means a full extraction — the first sync of a
            # repository, or an explicit re-extract.
            stmt = stmt.where(SourceArtifact.id.in_([uuid.UUID(a) for a in artifact_ids]))
        artifacts_result = await session.scalars(stmt)
        artifacts = list(artifacts_result.all())
        if not artifacts:
            return SyncStatus.COMPLETED  # only P2 files changed: nothing to extract

        files: list[tuple[str, str]] = []
        artifact_by_path: dict[str, SourceArtifact] = {}
        for artifact in artifacts:
            content = await client.get_file_content(
                repository.owner, repository.name, artifact.path, artifact.commit_sha
            )
            if content is None:
                continue
            files.append((artifact.path, content))
            artifact_by_path[artifact.path] = artifact

        provider = get_provider()
        embedding_provider = get_embedding_provider()
        evidence_repo = SQLAlchemyEvidenceRepository(session)

        repo_full_name = f"{repository.owner}/{repository.name}"
        total_saved = 0

        # Deterministic signal from Phase 1's tech_extraction (dependencies,
        # frameworks) — used to modestly boost confidence when the LLM's claimed
        # skill overlaps with what static parsing of manifests already confirmed.
        deterministic_tech: set[str] = set()
        for key in ("dependencies", "frameworks"):
            deterministic_tech.update(
                str(v).strip().lower() for v in (repository.language_summary or {}).get(key, [])
            )

        groups = _group_files(files)
        failed_groups = 0
        for group in groups:
            user_message = build_user_message(repo_full_name, group)
            try:
                result = await provider.structured_generate(
                    task="evidence_extract",
                    messages=[
                        Message(role="system", content=SYSTEM_PROMPT),
                        Message(role="user", content=user_message),
                    ],
                    schema=EvidenceExtractionOutput,
                    model_config=model_config,
                )
            except Exception:
                failed_groups += 1
                logger.exception(
                    "evidence_extraction_failed",
                    extra={"repository_id": repository_id_str, "group_paths": [p for p, _ in group]},
                )
                continue

            # Observability seeded from this phase onward (PRD §29) rather than
            # bolted on later — Phase 9's eval cost/latency reports and Phase 10's
            # dashboards both need this history to already exist by then.
            logger.info(
                "llm_call_completed",
                extra={
                    "task": "evidence_extract",
                    "prompt_version": PROMPT_VERSION,
                    "provider": result.usage.provider,
                    "model": result.usage.model,
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "latency_ms": result.usage.latency_ms,
                    "estimated_cost_usd": result.usage.estimated_cost_usd,
                    "repository_id": repository_id_str,
                    "run_id": run_id_str,
                },
            )

            accepted = []
            for item in result.value.evidence:
                try:
                    evidence_type = EvidenceType(item.evidence_type)
                except ValueError:
                    continue  # LLM returned a type outside our enum — drop, don't guess

                sources: list[EvidenceSourceCandidate] = []
                for path in item.source_paths:
                    artifact = artifact_by_path.get(path)
                    if artifact is None:
                        continue  # citation to a file we didn't actually provide — drop
                    content_for_hash = next((c for p, c in group if p == path), "")
                    sources.append(
                        EvidenceSourceCandidate(
                            source_artifact_id=artifact.id,
                            locator=path,
                            snippet_hash=hashlib.sha256(content_for_hash.encode()).hexdigest(),
                            commit_sha=artifact.commit_sha,
                            relevance=1.0,
                        )
                    )
                if not sources:
                    continue  # PRD §14: no provenance, no evidence
                accepted.append((item, evidence_type, sources))

            # One embedding call per file group rather than one per item.
            # A failure leaves the vectors empty (lexical and skill retrieval
            # still work) and the re-embedding backfill fills them later.
            embeddings: list[list[float] | None] = [None] * len(accepted)
            if accepted:
                try:
                    embeddings = await embedding_provider.embed(
                        [
                            evidence_embedding_text(i.title, i.normalized_claim, i.description)
                            for i, _t, _s in accepted
                        ]
                    )
                except Exception:
                    logger.warning("embedding_failed", extra={"repository_id": repository_id_str})

            candidates: list[EvidenceCandidate] = []
            for (item, evidence_type, sources), embedding in zip(accepted, embeddings, strict=True):
                confidence = combine_confidence(
                    semantic_confidence=item.confidence,
                    source_count=len(sources),
                    skill_names=item.skills,
                    deterministic_tech=deterministic_tech,
                )

                candidates.append(
                    EvidenceCandidate(
                        user_id=repository.user_id,
                        repository_id=repository.id,
                        evidence_type=evidence_type,
                        title=item.title,
                        normalized_claim=item.normalized_claim,
                        description=item.description,
                        confidence=confidence,
                        extraction_method=PROMPT_VERSION,
                        sources=sources,
                        skill_names=item.skills,
                        embedding=embedding,
                        embedding_model=embedding_provider.model_id if embedding else None,
                    )
                )

            if candidates:
                saved = await evidence_repo.save_candidates(candidates)
                total_saved += len(saved)
                for evidence in saved:
                    await publish_event(
                        run_id_str,
                        RunEventName.EVIDENCE_CREATED,
                        {"evidence_id": str(evidence.id), "title": evidence.title},
                    )

        logger.info(
            "evidence_extraction_completed",
            extra={
                "repository_id": repository_id_str,
                "evidence_created": total_saved,
                "groups": len(groups),
                "failed_groups": failed_groups,
            },
        )
        if groups and failed_groups == len(groups):
            return SyncStatus.FAILED
        return SyncStatus.COMPLETED


# One LLM call per file group, sequentially. On Groq's free tier (8K tokens
# per minute per model, ~5K tokens per call) that is about one call a minute
# once two repositories extract at once, so a 20-group repository needs ~20
# minutes; the previous 10-minute limit killed it partway with no record.
@dramatiq.actor(max_retries=1, queue_name="ai", time_limit=3_600_000)
def extract_evidence(repository_id: str, run_id: str, artifact_ids: list[str] | None = None) -> None:
    import asyncio

    asyncio.run(_extract_for_repository(repository_id, run_id, artifact_ids))
