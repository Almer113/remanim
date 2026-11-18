// WebSocket client with request/reply matching by `seq`.

type Listener = (msg: any) => void;

/** Longest an edit may take to verify before the UI gives up waiting
 * (a 3D scene replays slowly; the server keeps its own deadlines). */
const REPLY_TIMEOUT_MS = 240_000;

export class Conn {
  private ws: WebSocket | null = null;
  private seq = 1;
  private waiting = new Map<number, { resolve: (m: any) => void; timer: number }>();
  private listeners = new Set<Listener>();
  private queue: string[] = [];
  onStatus: (up: boolean) => void = () => {};
  /** Called after every (re)connect, before queued messages are sent:
   * the server may have restarted and forgotten which files are open. */
  onOpen: () => void = () => {};

  connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws = ws;
    ws.onopen = () => {
      this.onStatus(true);
      this.onOpen();
      for (const q of this.queue.splice(0)) ws.send(q);
    };
    ws.onclose = () => {
      this.onStatus(false);
      // replies to anything in flight will never come
      for (const [seq, w] of this.waiting) {
        clearTimeout(w.timer);
        w.resolve({ type: "error", seq, message: "Lost the connection to the studio server; check the file and try again" });
      }
      this.waiting.clear();
      setTimeout(() => this.connect(), 1000);
    };
    ws.onmessage = (ev) => {
      let msg: any;
      try { msg = JSON.parse(ev.data); } catch { return; }
      const w = msg.seq ? this.waiting.get(msg.seq) : undefined;
      if (w) {
        clearTimeout(w.timer);
        this.waiting.delete(msg.seq);
        w.resolve(msg);
        return;
      }
      for (const l of this.listeners) l(msg);
    };
  }

  on(l: Listener) {
    this.listeners.add(l);
    return () => { this.listeners.delete(l); };
  }

  send(msg: object) {
    const s = JSON.stringify(msg);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(s);
    else this.queue.push(s);
  }

  /** Send and wait for the reply that carries the same seq. Always settles:
   * with the reply, or with an error message on disconnect or timeout. */
  request(msg: object): Promise<any> {
    const seq = this.seq++;
    return new Promise((resolve) => {
      const timer = window.setTimeout(() => {
        this.waiting.delete(seq);
        resolve({ type: "error", seq, message: "No answer from the studio server in time" });
      }, REPLY_TIMEOUT_MS);
      this.waiting.set(seq, { resolve, timer });
      this.send({ ...msg, seq });
    });
  }
}

export function frameUrl(file: string, scene: string, rev: number, f: number, rest: boolean, session = "") {
  const q = new URLSearchParams({ file, scene, rev: String(rev), f: String(f) });
  if (!rest) {
    q.set("size", "half");
    q.set("fmt", "jpeg");
  }
  if (session) q.set("s", session);
  return `/frame?${q}`;
}

export function query(file: string, scene: string, rev: number, f: number, session = "") {
  const q = new URLSearchParams({ file, scene, rev: String(rev), f: String(f) });
  if (session) q.set("s", session);
  return q.toString();
}
