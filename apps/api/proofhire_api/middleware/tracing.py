"""Trace-id middleware.

Every request gets a trace_id (from an incoming X-Trace-Id header if present,
otherwise generated). This id is what ties together API logs, worker task logs,
and GenerationRun records (PRD §29).
"""

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return trace_id_ctx.get()


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        token = trace_id_ctx.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            trace_id_ctx.reset(token)
        response.headers["x-trace-id"] = trace_id
        return response
