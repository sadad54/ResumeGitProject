# ADR-0017: CSRF posture and session transport

## Status

Accepted.

## Context

The checklist (§17 "CSRF/XSS/CSP protections") and PRD §27 call for a CSRF
review. The review needed to be recorded, because the answer is "there is no
CSRF middleware" and an undocumented absence looks identical to an oversight.

## Decision

**Sessions are bearer tokens in the `Authorization` header, never cookies.**

The web app stores the access/refresh JWTs in `localStorage`
(`apps/web/src/lib/api.ts`) and attaches them explicitly per request. The API
sets no session cookie and `CORSMiddleware` allows only the configured web
origin (`WEB_BASE_URL`).

Classic CSRF works because the browser attaches credentials *automatically* to
any request aimed at the target origin, including one triggered from an
attacker's page. A bearer header is only sent when our own JavaScript adds it,
and cross-origin JavaScript on another site cannot read our `localStorage` or
set our header. The attack has no ambient credential to ride on, so
synchronizer tokens / double-submit cookies would be protecting against a
vector that does not exist here. **CSRF is not applicable by construction, and
we deliberately do not add anti-CSRF machinery that would imply otherwise.**

Two things make that claim hold and are therefore load-bearing:

1. `CORSMiddleware` is configured with an explicit origin allowlist, not `*`,
   so a cross-origin page cannot make credentialed requests with our header
   even if it somehow obtained the token.
2. No endpoint reads authentication from cookies or query strings. The
   previous SSE query-token fallback (`get_current_user_sse`) was removed for
   exactly this reason in ADR-0015; SSE now uses the same bearer header via a
   fetch-based stream.

## The tradeoff we are accepting instead

Bearer-in-`localStorage` moves the risk from CSRF to **XSS**: any script that
runs on our origin can read the token. That is the standard tradeoff of this
design, and it is mitigated rather than eliminated:

- Content-Security-Policy on every web response (`apps/web/next.config.ts`):
  `script-src 'self'` plus `'unsafe-inline'` only for Next.js's own bootstrap;
  no third-party script origins at all; `frame-ancestors 'none'`;
  `object-src` falls under `default-src 'self'`.
- React's default escaping for all rendered user content; no
  `dangerouslySetInnerHTML` in the codebase.
- Access tokens are short-lived (`AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`), and both
  token types are individually revocable by `jti` (ADR-0016 / `POST
  /auth/logout`), so a stolen token has a bounded window.
- `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` on both the
  API and web responses.

## Why not httpOnly cookies

httpOnly cookies would remove the XSS-readable token but reintroduce CSRF,
requiring SameSite plus a synchronizer token, *and* would break the browser
extension's session handoff (ADR-0015), which relies on the web app holding the
token in a place the extension's handoff page can read. Given the CSP above and
the extension constraint, bearer tokens were judged the better of the two
positions for V1. This should be revisited if the extension moves to its own
OAuth flow, at which point cookies become viable.

## Consequences

- Adding **any** cookie-authenticated endpoint, or any endpoint that accepts a
  token from a query parameter, silently invalidates this ADR and reintroduces
  CSRF. Reviewers should treat such a change as requiring CSRF protection to
  land in the same PR.
- The CSP `'unsafe-inline'` allowance for scripts is the weakest point of the
  XSS mitigation. Next.js nonce support would let it be removed; tracked as a
  hardening follow-up in `docs/product/BUILD_STATUS.md`.
