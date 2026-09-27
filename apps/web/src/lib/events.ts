import { apiBaseUrl, authFetch } from "./api";

/**
 * Run-progress events over SSE (GET /api/v1/events/runs/{id}).
 *
 * fetch rather than EventSource: EventSource can't send an Authorization
 * header, and putting the bearer token in the URL would leak it into
 * browser history and access logs. authFetch also renews an expired session
 * before the stream opens, like every other call.
 *
 * Returns an EventTarget that dispatches one MessageEvent per SSE frame,
 * named by the frame's `event:` field, plus "error" if the stream fails.
 */
export function openRunEvents(runId: string) {
  const events = new EventTarget();
  const controller = new AbortController();
  const source = Object.assign(events, { close: () => controller.abort() });
  void (async () => {
    try {
      const response = await authFetch(
        `${apiBaseUrl()}/api/v1/events/runs/${encodeURIComponent(runId)}`,
        { headers: { Accept: "text/event-stream" }, signal: controller.signal },
      );
      if (!response.ok || !response.body) throw new Error("Could not open progress stream");
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      while (!controller.signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer = (buffer + value).replace(/\r\n/g, "\n");
        let end: number;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);
          let name = "message";
          const data: string[] = [];
          for (const line of frame.split("\n")) {
            if (line.startsWith("event:")) name = line.slice(6).trim();
            if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
          }
          if (data.length) source.dispatchEvent(new MessageEvent(name, { data: data.join("\n") }));
        }
      }
      // The server closed the stream. After a terminal event the consumer
      // has already closed it (so this doesn't fire); otherwise the run's
      // outcome is unknown and the consumer should go and look.
      if (!controller.signal.aborted) source.dispatchEvent(new Event("end"));
    } catch {
      if (!controller.signal.aborted) source.dispatchEvent(new Event("error"));
    }
  })();
  return source;
}
