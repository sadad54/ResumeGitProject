"""Re-embed evidence whose vector is missing or from another model (ADR-0018).

Idempotent and resumable: each batch selects rows still out of date, so an
interrupted run picks up where it stopped and a second run is a no-op. Runs
after migrations on container start (in the background, so boot isn't
delayed) and can be run by hand after changing EMBEDDING_PROVIDER or
EMBEDDING_MODEL:

    python -m proofhire_worker.intelligence.reembed [--batch-size 64]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import uuid

from proofhire_api.models.evidence import Evidence
from sqlalchemy import or_, select, update

from proofhire_worker.db import async_session_factory
from proofhire_worker.intelligence.embeddings import EmbeddingProvider, evidence_embedding_text
from proofhire_worker.intelligence.provider_factory import get_embedding_provider

logger = logging.getLogger(__name__)


async def reembed_stale_evidence(
    provider: EmbeddingProvider | None = None,
    *,
    batch_size: int = 64,
    user_id: uuid.UUID | None = None,
) -> int:
    provider = provider or get_embedding_provider()
    model_id = provider.model_id
    total = 0
    started = time.perf_counter()
    stale = or_(
        Evidence.embedding.is_(None),
        Evidence.embedding_model.is_(None),
        Evidence.embedding_model != model_id,
    )
    while True:
        async with async_session_factory() as session:
            query = select(
                Evidence.id, Evidence.title, Evidence.normalized_claim, Evidence.description
            ).where(stale)
            if user_id is not None:
                query = query.where(Evidence.user_id == user_id)
            rows = (await session.execute(query.order_by(Evidence.id).limit(batch_size))).all()
            if not rows:
                break
            vectors = await provider.embed(
                [evidence_embedding_text(r.title, r.normalized_claim, r.description) for r in rows]
            )
            # ORM bulk UPDATE by primary key: one executemany per batch.
            await session.execute(
                update(Evidence),
                [
                    {"id": row.id, "embedding": vector, "embedding_model": model_id}
                    for row, vector in zip(rows, vectors, strict=True)
                ],
            )
            await session.commit()
            total += len(rows)
    logger.info(
        "evidence_reembedded",
        extra={
            "model": model_id,
            "rows": total,
            "seconds": round(time.perf_counter() - started, 2),
        },
    )
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    count = asyncio.run(reembed_stale_evidence(batch_size=args.batch_size))
    print(f"re-embedded {count} evidence rows with {get_embedding_provider().model_id}")


if __name__ == "__main__":
    main()
