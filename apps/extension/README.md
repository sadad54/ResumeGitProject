# ProofHire Chrome extension (Manifest V3)

1. Start the web app at `http://localhost:3000` and the API at `http://localhost:8000`; apply migration 0007.
2. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select this `apps/extension` directory.
3. Sign in to ProofHire in a normal browser tab.
4. Select a job description on a page, right-click **Send selection to ProofHire**, review the captured text, and save.
5. Choose **Open analysis**, then **Analyze captured job**. Existing jobs are available from the Jobs selector.

The second context-menu entry and toolbar popup open a paste fallback when there is no selected text. Arbitrary page scraping would require `scripting` or persistent content-script host permissions, so it is not requested. The V1 manifest has exactly `contextMenus`, `activeTab`, and `storage`.

Selected text, title, page URL and timestamp are held in `chrome.storage.session` for up to ten minutes, consumed after successful capture, and purged when expired on access or the next capture. They are not written to persistent extension storage. No access/refresh token leaves the web app; capture uses the existing web session's bearer-authenticated API. The handoff URL contains only random capture and extension IDs, never selected text or account tokens. A site must match the exact configured web origin to request a capture. Review/save is explicit, preventing silent cross-account submission.

For deployment, change `WEB_ORIGIN` in `config.js` and narrow `externally_connectable.matches` in `manifest.json` to your HTTPS web origin. Never use `<all_urls>`. The API does not need extension-origin CORS because the web app performs the API call.

Run the isolated service-worker/permission tests with `node --test apps/extension/tests/*.test.mjs`. These tests do not replace loading the extension in Chrome and completing the live journey.
