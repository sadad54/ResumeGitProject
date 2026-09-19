import { apiBaseUrl, getAccessToken } from "./api";

/** SSE over fetch keeps bearer tokens out of URLs, browser history and access logs. */
export function openRunEvents(runId: string) {
  const events = new EventTarget();
  const controller = new AbortController();
  const source = Object.assign(events, { close: () => controller.abort() });
  void (async () => {
    try {
      const response = await fetch(
        `${apiBaseUrl()}/api/v1/events/runs/${encodeURIComponent(runId)}`,
        {
          headers: {
            Authorization: `Bearer ${getAccessToken()}`,
            Accept: "text/event-stream",
          },
          signal: controller.signal,
        },
      );
      if (!response.ok || !response.body)
        throw new Error("Could not open progress stream");
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      let buffer = "";
      while (!controller.signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += value;
        buffer = buffer.replace(/\r\n/g, "\n");
        let end: number;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);
          let name = "message";
          const data: string[] = [];
          for (const line of frame.split("\n")) {
            if (line.startsWith("event:")) name = line.slice(6).trim();
            if (line.startsWith("data:"))
              data.push(line.slice(5).replace(/^ /, ""));
          }
          if (data.length)
            source.dispatchEvent(
              new MessageEvent(name, { data: data.join("\n") }),
            );
        }
      }
    } catch {
      if (!controller.signal.aborted) source.dispatchEvent(new Event("error"));
    }
  })();
  return source;
}
