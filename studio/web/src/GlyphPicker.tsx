import { useEffect, useRef, useState } from "react";
import type { Glyphs, Obj } from "./types";

export const COLORS = ["FG", "MUTED", "ACCENT", "GOOD", "BAD", "WHITE", "BLUE", "TEAL", "GREEN", "YELLOW", "GOLD",
  "RED", "MAROON", "PURPLE", "PINK", "ORANGE", "GREY"];

/** Pick glyphs of a Text / MathTex / Tex over the canvas, then a colour
 * (Phase 5 step 6). The engine's map says which source characters made
 * each glyph; the server writes the colour and checks it by replay.
 * Click or drag across glyphs; Esc cancels. */
export function GlyphPicker({ obj, url, frameW, frameH, frameX = 0, frameY = 0, onDone }: {
  obj: Obj;
  url: string;
  frameW: number;
  frameH: number;
  frameX?: number;
  frameY?: number;
  onDone: (pick: { glyphs: number[]; colour: string } | null) => void;
}) {
  const [g, setG] = useState<Glyphs | null | undefined>(undefined);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const dragging = useRef<null | boolean>(null);   // adding (true) or removing (false)
  useEffect(() => {
    let live = true;
    // 410: the file changed under the picker (an undo, an edit elsewhere): close quietly
    fetch(url).then((r) => (r.status === 410 ? undefined : r.ok ? r.json() : null))
      .then((r) => { if (!live) return; if (r === undefined) onDone(null); else setG(r?.glyphs ?? null); })
      .catch(() => { if (live) setG(null); });
    return () => { live = false; };
  }, [url]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); onDone(null); } };
    const up = () => { dragging.current = null; };
    window.addEventListener("keydown", key, true);
    window.addEventListener("mouseup", up);
    return () => { window.removeEventListener("keydown", key, true); window.removeEventListener("mouseup", up); };
  }, [onDone]);

  // whole pieces: the glyphs of `\vec{v}`, or of a word in a Text, go together
  const pieceOf = (i: number) => g ? g.map.flatMap((m, j) =>
    m[0] === g.map[i][0] && m[1] === g.map[i][1] && m[2] === g.map[i][2] ? [j] : []) : [i];
  const setPiece = (i: number, on: boolean) => setPicked((s) => {
    const n = new Set(s);
    for (const j of pieceOf(i)) { if (on) n.add(j); else n.delete(j); }
    return n;
  });
  const pct = (b: number[]) => ({
    left: `${((b[0] - frameX) / frameW + 0.5) * 100}%`, top: `${(0.5 - (b[3] - frameY) / frameH) * 100}%`,
    width: `${((b[2] - b[0]) / frameW) * 100}%`, height: `${((b[3] - b[1]) / frameH) * 100}%`,
  });
  const sourceOf = () => {
    if (!g || !picked.size) return "";
    const parts = new Map<number, [number, number]>();
    for (const i of picked) {
      const [p, a, b] = g.map[i];
      const r = parts.get(p);
      parts.set(p, r ? [Math.min(r[0], a), Math.max(r[1], b)] : [a, b]);
    }
    return [...parts].map(([p, [a, b]]) => g.parts[p].slice(a, b)).join(" … ");
  };
  const box = g?.boxes.reduce((acc, b) => [Math.min(acc[0], b[0]), Math.min(acc[1], b[1]),
    Math.max(acc[2], b[2]), Math.max(acc[3], b[3])], [Infinity, Infinity, -Infinity, -Infinity]);

  return (
    <div className="glyph-layer" onMouseDown={(e) => { e.stopPropagation(); if (e.target === e.currentTarget && !picked.size) onDone(null); }}
      onDoubleClick={(e) => e.stopPropagation()}>
      {g === undefined && <div className="glyph-msg">Matching {obj.name ?? obj.class}'s glyphs to its source… (a formula's first time takes a LaTeX run)</div>}
      {g === null && <div className="glyph-msg">The studio can't match this text's glyphs to its source; colour it in the code. <button onClick={() => onDone(null)}>Close</button></div>}
      {g && g.boxes.map((b, i) => (
        <div key={i} className={`glyph ${picked.has(i) ? "on" : ""}`} style={pct(b)}
          title={g.parts[g.map[i][0]].slice(g.map[i][1], g.map[i][2])}
          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); const on = !picked.has(i); dragging.current = on; setPiece(i, on); }}
          onMouseEnter={() => { if (dragging.current !== null) setPiece(i, dragging.current); }} />
      ))}
      {g && box && (
        <div className="glyph-bar" style={{ left: `${((box[0] - frameX) / frameW + 0.5) * 100}%`, top: `${(0.5 - (box[1] - frameY) / frameH) * 100}%` }}
          onMouseDown={(e) => e.stopPropagation()}>
          <div className="gb-head">{picked.size ? <>Colour <code>{sourceOf()}</code></> : "Click or drag across glyphs"}</div>
          <div className="gb-swatches">
            {COLORS.map((c) => (
              <button key={c} disabled={!picked.size} title={c}
                onClick={() => onDone({ glyphs: [...picked].sort((a, b) => a - b), colour: c })}>{c}</button>
            ))}
          </div>
          <div className="te-hint">Esc to cancel</div>
        </div>
      )}
    </div>
  );
}
