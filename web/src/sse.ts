// A fetch-based SSE reader. EventSource cannot change its URL between reconnects, and these
// streams must resume with ?after=<seq>, so reconnection is done here.

export interface SseMessage { event: string | null; data: string; id: string | null }

export async function readSse(
  url: string,
  onMessage: (m: SseMessage) => void,
  signal: AbortSignal,
  onOpen?: () => void,
): Promise<void> {
  const res = await fetch(url, { headers: { accept: "text/event-stream" }, signal, cache: "no-store" });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  if (!res.body) throw new Error("no stream body");
  onOpen?.();
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  let event: string | null = null;
  let id: string | null = null;
  let data: string[] = [];
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += value;
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).replace(/\r$/, "");
      buf = buf.slice(nl + 1);
      if (line === "") {
        if (data.length) onMessage({ event, data: data.join("\n"), id });
        event = null;
        id = null;
        data = [];
      } else if (line.startsWith(":")) {
        // comment / keep-alive
      } else {
        const c = line.indexOf(":");
        const field = c < 0 ? line : line.slice(0, c);
        const val = c < 0 ? "" : line.slice(c + 1).replace(/^ /, "");
        if (field === "data") data.push(val);
        else if (field === "event") event = val;
        else if (field === "id") id = val;
      }
    }
  }
}
