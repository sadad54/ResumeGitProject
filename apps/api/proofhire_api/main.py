"""FastAPI application factory."""

from fastapi import FastAPI

from proofhire_api.config import get_settings
from proofhire_api.logging import configure_logging
from proofhire_api.middleware.tracing import TraceIdMiddleware
from proofhire_api.routers import auth, events, evidence, github, health


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="ProofHire API",
        version="0.1.0",
        description="Evidence-grounded AI career agent — API",
    )

    app.add_middleware(TraceIdMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(github.router)
    app.include_router(events.router)
    app.include_router(evidence.router)
    # Remaining feature routers (profile, jobs, generation, applications) are
    # added under /api/v1 as each phase implements them — see
    # docs/product/PRD.md §23 for the full contract and the build plan for sequencing.

    _ = settings  # settings wired to routers as they're added
    return app


app = create_app()
