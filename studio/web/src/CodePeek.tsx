import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { DiffHunk, Literal, Span } from "./types";

type Props = {
  source: string;
  span: Span | null;
  diff: DiffHunk[] | null;
  file: string;
  /** Values that can be edited in place (tier 1-2 code). */
  literals?: Literal[];
  /** Sends edit.literal; null when editing isn't possible right now. */
  onLiteral?: ((lit: Literal, value: object) => Promise<any> | null) | null;
};

/** The code behind the selection, with the last edit highlighted. Numbers,
 * strings and constant names in editable code can be clicked and changed. */
// memo: re-renders only when the code, selection or diff changes, not on every playback frame
export const CodePeek = memo(function CodePeek({ source, span, diff, file, literals, onLiteral }: Props) {
  const lines = useMemo(() => source.split(/\r?\n/), [source]);
  const byLine = useMemo(() => {
    const m = new Map<number, Literal[]>();
    for (const l of literals ?? []) {
      if (l.span[0] !== l.span[2]) continue;
      const a = m.get(l.line) ?? [];
      a.push(l);
      m.set(l.line, a);
    }
    for (const a of m.values()) a.sort((x, y) => x.cols[0] - y.cols[0]);
    return m;
  }, [literals]);
  const [editing, setEditing] = useState<Literal | null>(null);
  useEffect(() => setEditing(null), [source]);
  const box = useRef<HTMLDivElement>(null);
  const added = new Set<number>();
  for (const h of diff ?? []) h.after.forEach((_, j) => added.add(h.line + j));
  const focus = diff?.length ? diff[0].line : span ? span[0] : null;
  useEffect(() => {
    const el = box.current?.querySelector(".focus") as HTMLElement | null;
    if (el && box.current) box.current.scrollTop = el.offsetTop - box.current.clientHeight / 3;
  }, [focus, source]);

  const render = (text: string, n: number) => {
    const ls = byLine.get(n);
    if (!ls || !onLiteral) return text || " ";
    const parts: React.ReactNode[] = [];
    let at = 0;
    for (const l of ls) {
      const [a, b] = l.cols;
      if (a < at || b > text.length || text.slice(a, b) !== l.text) continue;  // stale: skip
      parts.push(text.slice(at, a));
      if (editing && editing.span.join() === l.span.join()) {
        parts.push(<LiteralInput key={a} lit={l} onDone={(v) => {
          setEditing(null);
          if (v !== null) onLiteral(l, v);
        }} />);
      } else {
        parts.push(
          <span key={a} className={`lit lit-${l.kind}`} role="button" tabIndex={0}
            title={l.scope === "constant" ? "A constant: click to change it everywhere it's used"
              : l.scope === "helper" ? "Inside a helper: click to change it for every use" : "Click to change"}
            onClick={() => setEditing(l)}
            onKeyDown={(e) => { if (e.key === "Enter") setEditing(l); }}>{l.text}</span>);
      }
      at = b;
    }
    parts.push(text.slice(at));
    return parts;
  };

  return (
    <div className="codepeek">
      <h3>Code <small>{file}{span ? ` · line ${span[0]}` : ""}</small></h3>
      <div className="code" ref={box}>
        {lines.map((l, i) => {
          const n = i + 1;
          const inSpan = span && n >= span[0] && n <= span[2];
          const cls = added.has(n) ? "add" : inSpan ? "hl" : "";
          return (
            <div key={i} className={`${cls} ${n === focus ? "focus" : ""}`}>
              <span className="ln">{n}</span>{render(l, n)}
            </div>
          );
        })}
      </div>
    </div>
  );
});

/** The editor for one value: Enter writes, Escape or leaving cancels. */
function LiteralInput({ lit, onDone }: { lit: Literal; onDone: (v: object | null) => void }) {
  const start = lit.kind === "string" ? lit.value ?? "" : lit.text;
  const [v, setV] = useState(start);
  const [bad, setBad] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const done = useRef(false);
  useEffect(() => { ref.current?.focus(); ref.current?.select(); }, []);
  const finish = (commit: boolean) => {
    if (done.current) return;
    if (!commit || v === start) { done.current = true; onDone(null); return; }
    if (lit.kind === "number") {
      const x = Number(v.trim());
      if (v.trim() === "" || !Number.isFinite(x)) { setBad(true); return; }
      done.current = true;
      onDone({ number: x });
    } else if (lit.kind === "name") {
      if (!/^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$/.test(v.trim())) { setBad(true); return; }
      done.current = true;
      onDone({ name: v.trim() });
    } else {
      done.current = true;
      onDone({ string: v });
    }
  };
  return (
    <input ref={ref} className={`lit-edit ${bad ? "bad" : ""}`} value={v}
      size={Math.max(3, Math.min(60, v.length + 1))}
      aria-label={`New ${lit.kind}`}
      onChange={(e) => { setV(e.target.value); setBad(false); }}
      onKeyDown={(e) => {
        e.stopPropagation();  // keys belong to the field, not the timeline shortcuts
        if (e.key === "Enter") finish(true);
        if (e.key === "Escape") finish(false);
      }}
      onBlur={() => finish(false)} />
  );
}
