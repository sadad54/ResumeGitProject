"""Regression test for a real production bug: `ruff --fix`'s import sort once
reordered tasks.py so `ingestion`/`intelligence`/`render` (which declare every
real actor via @dramatiq.actor) were imported *before* proofhire_worker.broker
(which calls dramatiq.set_broker(...)). Every actor except the one defined
directly in tasks.py after that import ended up registered on a stray default
broker instead of the real RedisBroker — so `dramatiq proofhire_worker.tasks`
started, looked healthy, and silently never consumed the ingest/ai/render
queues. Run in a subprocess for a genuinely fresh import, matching what the
`dramatiq` CLI actually does.
"""

import subprocess
import sys

_CHECK_SCRIPT = """
import dramatiq
import proofhire_worker.tasks as tasks

broker = dramatiq.get_broker()
for actor_name in ("sync_repositories", "extract_evidence", "analyze_job",
                    "compute_coverage", "generate_document"):
    actor = broker.actors.get(actor_name)
    assert actor is not None, f"{actor_name} not registered on the real broker"
print("OK")
"""


def test_every_pipeline_actor_registers_on_the_real_broker():
    result = subprocess.run(
        [sys.executable, "-c", _CHECK_SCRIPT],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
