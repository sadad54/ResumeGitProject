"""The worker process emits structured JSON logs with their extra fields.

Run in a subprocess because the property is about the real worker entry
module's import-time setup, which other tests (the API's create_app also
configures logging) would otherwise mask.
"""

import json
import subprocess
import sys

SCRIPT = """
import logging
import proofhire_worker.tasks  # configures logging at import, as under dramatiq
logging.getLogger("proofhire_worker.intelligence.coverage").info(
    "llm_call_completed", extra={"task": "rerank", "model": "m", "input_tokens": 812}
)
"""


def test_worker_logs_keep_structured_fields():
    out = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True,
                         timeout=120, check=True).stdout
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    usage = next(e for e in events if e.get("message") == "llm_call_completed")
    assert (usage["task"], usage["input_tokens"]) == ("rerank", 812)
