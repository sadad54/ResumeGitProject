"""Error monitoring via Sentry (checklist Track C "Error monitoring").

Opt-in on SENTRY_DSN, like tracing on OTEL_EXPORTER_OTLP_ENDPOINT: with no DSN
configured this is a no-op, so tests and local dev never ship events anywhere.

Two things are deliberate here and worth not "simplifying" away:

- `send_default_pii=False` and the `before_send` scrubber. PRD §27 forbids raw
  private source code and secrets in logs; an error tracker is a log with a
  nicer UI, and a stack trace from evidence extraction has the user's file
  contents in local variables. Local variables are stripped from every frame,
  and request bodies are never attached.
- The trace_id from `middleware/tracing.py` is attached as a tag, so an event
  in Sentry can be joined to the structured-log lines and the OTel span for
  the same request rather than being an orphaned stack trace.
"""

from __future__ import annotations

import logging

from proofhire_api.middleware.tracing import get_trace_id

logger = logging.getLogger(__name__)

# Header/variable names whose values must never leave the process. Matched
# against the key with `-`/`_` removed, so X-Api-Key, api_key and apikey all
# hit the same entry — a test caught the hyphenated form slipping through.
_SENSITIVE_KEYS = ("authorization", "cookie", "token", "secret", "password", "apikey")


def _is_sensitive(key: str) -> bool:
    flat = key.lower().replace("-", "").replace("_", "")
    return any(s in flat for s in _SENSITIVE_KEYS)


def _scrub(event: dict, _hint: dict) -> dict | None:
    for exc in event.get("exception", {}).get("values", []) or []:
        for frame in exc.get("stacktrace", {}).get("frames", []) or []:
            frame.pop("vars", None)

    request = event.get("request")
    if request:
        request.pop("data", None)
        headers = request.get("headers") or {}
        for key in list(headers):
            if _is_sensitive(key):
                headers[key] = "[redacted]"

    event.setdefault("tags", {})["trace_id"] = get_trace_id()
    return event


def configure_error_monitoring(dsn: str, *, environment: str, service: str) -> bool:
    """Returns True if monitoring was enabled."""
    if not dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=None,
        send_default_pii=False,
        include_local_variables=False,
        before_send=_scrub,
        # Errors only. Performance data goes through OpenTelemetry (telemetry.py)
        # so there's one tracing system, not two disagreeing ones.
        traces_sample_rate=0.0,
    )
    sentry_sdk.set_tag("service", service)
    logger.info("error_monitoring_enabled", extra={"service": service, "environment": environment})
    return True
