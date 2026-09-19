"""Baseline security response headers (PRD §27, Phase 10 hardening).

The API only ever serves JSON/PDF to the web app's own fetch calls — never
rendered in a browser as a page — so this is a narrow, low-risk hardening
pass rather than a full CSP (which belongs on the web app, see
apps/web/next.config.ts).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # No third-party embedding of API responses, and no caching of
        # anything by default — individual endpoints (e.g. static exports)
        # can override this if they ever need to be cacheable.
        response.headers.setdefault("Cache-Control", "no-store")
        return response
