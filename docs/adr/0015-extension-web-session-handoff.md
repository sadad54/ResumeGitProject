# ADR-0015: Capture handoff uses the existing web session

Status: Accepted for phase 8 implementation.

The Manifest V3 extension has only `contextMenus`, `activeTab`, and `storage`. Selected text, page title/URL and timestamp are placed in extension session storage under a random UUID with a ten-minute expiry. A web tab receives only that UUID and the extension ID in its URL. The extension responds to external messages only from the exact configured web origin. Captures are removed on acknowledgement, expired reads or the next capture. No application access/refresh token is copied into extension storage.

The web capture page reviews the selection and calls `POST /api/v1/jobs/capture` with its existing bearer session. A stable capture UUID makes retries idempotent while preserving tenant isolation. Input is bounded, whitespace validated, scanned for known secrets, and restricted to HTTP(S) source URLs without credentials. Capture does not fetch its source URL. A nullable `source_title` column is added by migration 0007; `captured_at` records the supplied timezone-aware timestamp. The returned job can be reopened and analyzed from Jobs.

A page capture without selection opens the paste fallback. Automatic DOM extraction is not implemented because it would require additional scripting/content-script permission. This is an explicit remaining acceptance detail if full extraction is required; the fallback remains usable with the three approved permissions.

SSE is also hardened in this increment: the web client uses fetch with the bearer token in the header, and the SSE endpoint verifies ownership of the requested Job/SyncRun/GenerationRun before subscribing. The old query-token SSE route behavior is removed; API and frontend must be deployed together. Existing event names are unchanged.

References: PRD §§23, 27; https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
