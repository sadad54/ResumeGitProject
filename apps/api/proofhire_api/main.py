"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from proofhire_api.config import get_settings
from proofhire_api.logging import configure_logging
from proofhire_api.middleware.security_headers import SecurityHeadersMiddleware
from proofhire_api.middleware.tracing import TraceIdMiddleware
from proofhire_api.routers import (
    applications,
    auth,
    events,
    evidence,
    generation,
    github,
    health,
    jobs,
    profile,
)
from proofhire_api.telemetry import configure_tracing


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    configure_tracing("proofhire-api", settings.otel_exporter_otlp_endpoint)

    app = FastAPI(
        title="ProofHire API",
        version="0.1.0",
        description="Evidence-grounded AI career agent — API",
    )
    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)

    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    # The web app (localhost:3000) and API (localhost:8000) are different
    # origins in local dev, so the browser sends CORS preflight OPTIONS
    # requests before any cross-origin POST/PATCH/etc. Without this, every
    # mutating request from the actual browser UI fails with 405 on the
    # preflight — direct HTTP-client testing (PowerShell, curl) never hits
    # this since those don't do CORS preflight, which is why it went
    # unnoticed until real browser testing.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request, exc):
        # Validation errors must not echo potentially sensitive request input.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(e["loc"]), "type": e["type"], "msg": "Invalid value"}
                    for e in exc.errors()
                ]
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(github.router)
    app.include_router(events.router)
    app.include_router(evidence.router)
    app.include_router(jobs.router)
    app.include_router(profile.router)
    app.include_router(generation.router)
    app.include_router(applications.router)

    return app


app = create_app()
