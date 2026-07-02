/** Shared live-price feed.
 *
 * One EventSource to /api/stream carries ALL pairs' quotes (server pushes on
 * change, ~1/s) and is shared by every chart on the page — replacing the old
 * 2s-per-chart polling. If SSE can't connect (proxy buffering, 503 stream cap,
 * old browser), subscribers transparently fall back to polling /api/live.
 */

export type LiveMode = "push" | "poll";
type Quotes = Record<string, number>;
type Listener = (quotes: Quotes, connected: boolean) => void;

let es: EventSource | null = null;
const listeners = new Set<Listener>();
let lastQuotes: Quotes = {};
let failures = 0;
let sseDead = false; // repeated failures → give up and let pollers take over

function ensureStream(): void {
  if (es || sseDead || typeof window === "undefined") return;
  try {
    es = new EventSource("/api/stream");
  } catch {
    sseDead = true;
    return;
  }
  es.addEventListener("quotes", (ev) => {
    failures = 0;
    try {
      const d = JSON.parse((ev as MessageEvent).data);
      lastQuotes = d.quotes || {};
      listeners.forEach((l) => l(lastQuotes, !!d.connected));
    } catch {
      /* malformed frame — skip */
    }
  });
  es.onerror = () => {
    es?.close();
    es = null;
    failures += 1;
    if (failures >= 3) {
      sseDead = true; // pollers cover from here on
      return;
    }
    if (listeners.size) setTimeout(ensureStream, 2000 * failures);
  };
}

/** Subscribe to one pair's live price. Returns an unsubscribe function.
 *  cb receives (price, mode) — mode tells the UI whether it's push or poll. */
export function subscribeLivePrice(
  pair: string,
  cb: (price: number, mode: LiveMode) => void,
): () => void {
  let stopped = false;

  const listener: Listener = (quotes) => {
    const p = quotes[pair];
    if (!stopped && p != null) cb(p, "push");
  };
  listeners.add(listener);
  ensureStream();
  if (lastQuotes[pair] != null) cb(lastQuotes[pair], "push");

  // Polling fallback — only fires while the shared stream is down.
  const poll = async () => {
    if (stopped || (es && !sseDead)) return;
    try {
      const r = await fetch(`/api/live?pair=${pair}`, { cache: "no-store" });
      const d = await r.json();
      if (!stopped && d.price != null) cb(d.price, "poll");
    } catch {
      /* transient */
    }
  };
  const pollTimer = setInterval(poll, 2000);

  return () => {
    stopped = true;
    clearInterval(pollTimer);
    listeners.delete(listener);
    if (listeners.size === 0 && es) {
      es.close(); // no charts mounted — release the server's stream slot
      es = null;
    }
  };
}
