"""Task registration entrypoint for the worker process.

`dramatiq proofhire_worker.tasks` is the process that runs all registered actors.
This module imports every task subpackage so Dramatiq discovers all actors.
"""

import dramatiq
from proofhire_api.config import get_settings
from proofhire_api.error_monitoring import configure_error_monitoring
from proofhire_api.telemetry import configure_tracing

# Must run before the actor-declaring imports below: dramatiq.actor() reads the
# globally-set broker at decoration time, and this module sets it as a side
# effect. A straight `import` (rather than `from ... import broker`) keeps this
# ordering intact under ruff's isort, which sorts straight imports as their own
# block ahead of `from` imports regardless of alphabetical module path.
import proofhire_worker.broker  # noqa: F401
from proofhire_worker import ingestion, intelligence, render  # noqa: F401

configure_tracing("proofhire-worker", get_settings().otel_exporter_otlp_endpoint)
configure_error_monitoring(
    get_settings().sentry_dsn, environment=get_settings().environment, service="proofhire-worker"
)


@dramatiq.actor
def noop() -> str:
    """Proves the queue works end to end (Phase 0). Superseded by real tasks
    (extract_evidence, analyze_job, generate_application, ...) from Phase 1 on."""
    return "ok"
