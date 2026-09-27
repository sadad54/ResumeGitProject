const MESSAGES: Record<string, { text: string; tone: "ok" | "warn" }> = {
  connected: { text: "GitHub connected. Choose the repositories to analyze below.", tone: "ok" },
  denied: { text: "GitHub access wasn't granted, so nothing was connected.", tone: "warn" },
  expired: {
    text: "That GitHub sign-in link expired or didn't match your session. Try connecting again.",
    tone: "warn",
  },
  error: { text: "GitHub couldn't complete the connection. Try again in a moment.", tone: "warn" },
};

/** The OAuth callback redirects here with ?github=<outcome> (routers/github.py). */
export function GitHubCallbackNotice({ outcome }: { outcome?: string }) {
  const message = outcome ? MESSAGES[outcome] : undefined;
  if (!message) return null;
  return (
    <div
      className={`ph-banner ${message.tone === "warn" ? "ph-banner-warn" : "ph-banner-ok"}`}
      role={message.tone === "warn" ? "alert" : "status"}
    >
      <span>{message.text}</span>
    </div>
  );
}
