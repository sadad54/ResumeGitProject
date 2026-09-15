# apps/extension

Manifest V3 browser extension (PRD §22). Built in Phase 8, after the web app's
paste-based JD capture flow (`POST /jobs/capture`) already works, since the
extension is a second entry point into the same endpoint.

Minimal permissions only: `contextMenus`, `activeTab`, `storage`. No broad
`<all_urls>` content-script access without a demonstrated need.
