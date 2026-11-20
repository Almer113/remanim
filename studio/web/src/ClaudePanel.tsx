// The Claude panel (Phase 6, optional): ask Claude Code about the open file.
// The server runs the user's own `claude -p` in the project root; Claude edits
// the .py file with its own tools and the studio reloads it like any save.
// A follow-up continues the same Claude Code session until "New chat".
import { useEffect, useRef, useState } from "react";
import type { Conn } from "./api";

export interface ClaudeContext { file: string; scene: string | null; t: number; selection: { label: string; line: number | null } | null }

type Item =
  | { kind: "you"; text: string; where: string }
  | { kind: "text"; text: string }
  | { kind: "tool"; tool: string; what: string }
  | { kind: "result"; ok: boolean; text?: string | null; s?: number; cost?: number | null; stopped?: boolean };

const TOOL_WORDS: Record<string, string> = { Read: "read", Edit: "edited", Write: "wrote", Glob: "looked for", Grep: "searched" };

function load(): { items: Item[]; session: string | null } {
  try {
    const v = JSON.parse(sessionStorage.getItem("studio.claude") ?? "null");
    if (v && Array.isArray(v.items)) return { items: v.items.slice(-200), session: v.session ?? null };
  } catch { /* storage off */ }
  return { items: [], session: null };
}

// stays mounted once opened (hidden when closed), so an answer keeps arriving while it is closed
export function ClaudePanel({ conn, ctx, open, onClose }: { conn: Conn; ctx: ClaudeContext; open: boolean; onClose: () => void }) {
  const first = useRef(load());
  const [items, setItems] = useState<Item[]>(first.current.items);
  const [session, setSession] = useState<string | null>(first.current.session);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ available: boolean; why: string | null } | null>(null);
  const [text, setText] = useState("");
  const runRef = useRef<number | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    conn.request({ type: "claude.status" }).then((r) => {
      if (r.type === "claude.status") { setStatus({ available: r.available, why: r.why }); setBusy(!!r.busy); }
    });
    return conn.on((m) => {
      if (m.type !== "claude.event" || (runRef.current != null && m.id !== runRef.current)) return;
      if (m.kind === "session") { if (m.session) setSession(m.session); return; }
      if (m.kind === "result") {
        setBusy(false);
        if (m.session) setSession(m.session);
      }
      const { type: _t, id: _i, ...item } = m;
      setItems((xs) => [...xs, item as Item]);
    });
  }, [conn]);

  useEffect(() => {
    try { sessionStorage.setItem("studio.claude", JSON.stringify({ items: items.slice(-200), session })); } catch { /* */ }
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [items, session]);

  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  const where = [ctx.file, ctx.scene, `${ctx.t.toFixed(2)} s`, ctx.selection?.label].filter(Boolean).join(" · ");

  const ask = () => {
    const q = text.trim();
    if (!q || busy) return;
    setItems((xs) => [...xs, { kind: "you", text: q, where }]);
    setText("");
    setBusy(true);
    conn.request({ type: "claude.ask", prompt: q, session, context: ctx }).then((r) => {
      if (r.type === "claude.started") runRef.current = r.id;
      else {
        setBusy(false);
        setItems((xs) => [...xs, { kind: "result", ok: false, text: r.message ?? r.why ?? "couldn't ask" }]);
      }
    });
  };

  return (
    <aside className="claude" aria-label="Claude panel" hidden={!open}>
      <div className="claude-head">
        <strong>Claude</strong>
        <span className="muted" title="Claude Code runs in the project folder: it reads CLAUDE.md and may edit files">Claude Code · project folder</span>
        <span className="grow" />
        <button disabled={busy || (!items.length && !session)} onClick={() => { setItems([]); setSession(null); }}
          title="Start a new conversation">New chat</button>
        <button onClick={onClose} aria-label="Close the Claude panel" title="Close (Esc)">✕</button>
      </div>
      <div className="claude-log" ref={logRef}>
        {status && !status.available && <div className="claude-note bad">{status.why}</div>}
        {!items.length && status?.available && (
          <div className="claude-note">
            Ask about the open file, or ask for a change: "make the circle blue and slower", "why does the
            label jump at 3 s?". Claude edits the .py file and the studio reloads it. Undo in the studio
            doesn't cover Claude's edits; git does.
          </div>
        )}
        {items.map((it, i) => it.kind === "you" ? (
          <div key={i} className="claude-you"><div className="claude-where">{it.where}</div>{it.text}</div>
        ) : it.kind === "text" ? (
          <div key={i} className="claude-text">{it.text}</div>
        ) : it.kind === "tool" ? (
          <div key={i} className="claude-tool">{TOOL_WORDS[it.tool] ?? it.tool} {it.what}</div>
        ) : (
          <div key={i} className={`claude-result ${it.ok ? "" : "bad"}`}>
            {it.ok ? "done" : it.stopped ? "stopped" : "didn't finish"}
            {it.s != null && ` · ${it.s} s`}
            {it.cost != null && ` · $${it.cost.toFixed(2)}`}
            {!it.ok && it.text && !it.stopped && <pre>{it.text}</pre>}
          </div>
        ))}
        {busy && <div className="claude-tool">thinking…</div>}
      </div>
      <div className="claude-ask">
        <textarea ref={inputRef} value={text} rows={3} disabled={!status?.available}
          placeholder={session ? "Follow up…" : "Ask Claude about this file…"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); }
            if (e.key === "Escape") { e.preventDefault(); onClose(); }
          }} />
        {busy
          ? <button onClick={() => conn.request({ type: "claude.stop" })} title="Stop Claude">■ Stop</button>
          : <button disabled={!text.trim() || !status?.available} onClick={ask} title="Send (Enter; Shift+Enter for a new line)">Send</button>}
      </div>
    </aside>
  );
}
