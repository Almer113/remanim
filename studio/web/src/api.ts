// WebSocket client with request/reply matching by `seq`.

type Listener = (msg: any) => void;

export class Conn {
  private ws: WebSocket | null = null;
  private seq = 1;
  private waiting = new Map<number, (m: any) => void>();
  private listeners = new Set<Listener>();
  private queue: string[] = [];
  onStatus: (up: boolean) => void = () => {};

  connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws = ws;
    ws.onopen = () => {
      this.onStatus(true);
      for (const q of this.queue.splice(0)) ws.send(q);
    };
    ws.onclose = () => {
      this.onStatus(false);
      setTimeout(() => this.connect(), 1000);
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.seq && this.waiting.has(msg.seq)) {
        this.waiting.get(msg.seq)!(msg);
        this.waiting.delete(msg.seq);
        return;
      }
      for (const l of this.listeners) l(msg);
    };
  }

  on(l: Listener) {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  send(msg: object) {
    const s = JSON.stringify(msg);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(s);
    else this.queue.push(s);
  }

  /** Send and wait for the reply that carries the same seq. */
  request(msg: object): Promise<any> {
    const seq = this.seq++;
    return new Promise((resolve) => {
      this.waiting.set(seq, resolve);
      this.send({ ...msg, seq });
    });
  }
}

export function frameUrl(file: string, scene: string, rev: number, f: number, rest: boolean) {
  const q = new URLSearchParams({ file, scene, rev: String(rev), f: String(f) });
  if (!rest) {
    q.set("size", "half");
    q.set("fmt", "jpeg");
  }
  return `/frame?${q}`;
}

export function query(file: string, scene: string, rev: number, f: number) {
  return new URLSearchParams({ file, scene, rev: String(rev), f: String(f) }).toString();
}
