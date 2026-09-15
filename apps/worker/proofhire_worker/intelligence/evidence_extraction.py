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
from proofhire_contracts import EvidenceType, RunEventName
from proofhire_prompts.evidence_extract_v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from sqlalchemy import select

from proofhire_api.db import async_session_factory
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
from proofhire_contracts.embedding import EMBEDDING_MODEL
from proofhire_worker.events import publish_event
from proofhire_worker.intelligence.confidence import combine_confidence
from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
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


async def _extract_for_repository(repository_id_str: str, run_id_str: str) -> None:
    repository_id = uuid.UUID(repository_id_str)
    model_config = ModelConfig(model="claude-sonnet-5")

    async with async_session_factory() as session:
        repository = await session.get(Repository, repository_id)
        if repository is None:
            logger.error("repository_not_found", extra={"repository_id": repository_id_str})
            return

        connection = await session.scalar(
            select(GitHubConnection).where(GitHubConnection.user_id == repository.user_id)
        )
        if connection is None:
            logger.error("github_not_connected", extra={"repository_id": repository_id_str})
            return

        client = GitHubClient(decrypt_token(connection.token_ref))

        artifacts_result = await session.scalars(
            select(SourceArtifact).where(
                SourceArtifact.repository_id == repository_id,
                SourceArtifact.priority.in_(["p0", "p1"]),
            )
        )
        artifacts = list(artifacts_result.all())
        if not artifacts:
            return

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

        for group in _group_files(files):
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

            candidates: list[EvidenceCandidate] = []
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

                embed_text = f"{item.title}. {item.normalized_claim} {item.description}"
                try:
                    [embedding] = await embedding_provider.embed([embed_text], model=EMBEDDING_MODEL)
                except Exception:
                    embedding = None
                    logger.warning("embedding_failed", extra={"repository_id": repository_id_str})

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
            extra={"repository_id": repository_id_str, "evidence_created": total_saved},
        )


@dramatiq.actor(max_retries=1, queue_name="ai", time_limit=600_000)
def extract_evidence(repository_id: str, run_id: str) -> None:
    import asyncio

    asyncio.run(_extract_for_repository(repository_id, run_id))
