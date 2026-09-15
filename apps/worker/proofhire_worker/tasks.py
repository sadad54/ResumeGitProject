"""Task registration entrypoint for the worker process.

`dramatiq proofhire_worker.tasks` is the process that runs all registered actors.
This module imports every task subpackage so Dramatiq discovers all actors.
"""

from proofhire_worker.broker import broker  # noqa: F401
from proofhire_worker import ingestion, intelligence, render  # noqa: F401
import dramatiq


@dramatiq.actor
def noop() -> str:
    """Proves the queue works end to end (Phase 0). Superseded by real tasks
    (extract_evidence, analyze_job, generate_application, ...) from Phase 1 on."""
    return "ok"
