"""Structured JSON logging setup.

Every request/task should log with a `trace_id` bound (see middleware/tracing.py).
Never log raw private source code or secrets (PRD §27, §29).
"""

import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
