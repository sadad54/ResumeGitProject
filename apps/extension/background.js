import { WEB_ORIGIN } from "./config.js";

const TTL_MS = 10 * 60 * 1000;
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "selection", title: "Send selection to ProofHire", contexts: ["selection"] });
    chrome.contextMenus.create({ id: "page", title: "Analyze this job with ProofHire", contexts: ["page"] });
  });
});

async function capture(text, pageUrl, title) {
  const id = crypto.randomUUID();
  const entries = await chrome.storage.session.get(null);
  const expired = Object.entries(entries).filter(([, value]) => !value.expires || value.expires < Date.now()).map(([key]) => key);
  if (expired.length) await chrome.storage.session.remove(expired);
  // No long-lived account tokens, credentials, or page data in local storage.
  await chrome.storage.session.set({ [id]: {
    capture_id: id, selected_text: (text || "").slice(0, 60000),
    page_url: /^https?:\/\//.test(pageUrl || "") ? pageUrl.slice(0, 2048) : null,
    title: (title || "").slice(0, 500), captured_at: new Date().toISOString(),
    expires: Date.now() + TTL_MS,
  } });
  await chrome.tabs.create({ url: `${WEB_ORIGIN}/capture?extension=${chrome.runtime.id}&capture=${id}` });
}
chrome.contextMenus.onClicked.addListener((info, tab) => {
  void capture(info.selectionText, info.pageUrl, tab?.title).catch(() => {
    void chrome.action.setBadgeText({ text: "!" });
    void chrome.action.setTitle({ title: "Capture failed. Open ProofHire and paste the job description." });
  });
});
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || message?.type !== "capture-active") return;
  chrome.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
    await capture("", tab?.url, tab?.title); respond({ ok: true });
  }).catch(() => respond({ ok: false }));
  return true;
});
chrome.runtime.onMessageExternal.addListener((message, sender, respond) => {
  let origin;
  try { origin = new URL(sender.url).origin; } catch { return; }
  if (origin !== WEB_ORIGIN || !/^[0-9a-f-]{36}$/.test(message?.capture_id || "")) return;
  const id = message.capture_id;
  if (message.type === "read-capture") {
    chrome.storage.session.get(id).then(async result => {
      const item = result[id];
      if (!item || item.expires < Date.now()) {
        await chrome.storage.session.remove(id); respond({ error: "Capture expired. Select the job again." }); return;
      }
      const { expires, ...payload } = item;
      respond({ payload });
    }).catch(() => respond({ error: "Could not read capture." }));
    return true;
  }
  if (message.type === "finish-capture") {
    chrome.storage.session.remove(id).then(() => respond({ ok: true })); return true;
  }
});
