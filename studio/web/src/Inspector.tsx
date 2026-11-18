import { useEffect, useState } from "react";
import type { Model, SceneModel } from "./types";
import type { Selection } from "./App";

const RATE_FUNCS = ["smooth", "linear", "rush_into", "rush_from", "there_and_back", "double_smooth",
  "ease_in_sine", "ease_out_sine", "ease_in_out_sine", "ease_in_out_cubic", "ease_out_back", "wiggle"];
const COLORS = ["FG", "MUTED", "ACCENT", "GOOD", "BAD", "WHITE", "BLUE", "TEAL", "GREEN", "YELLOW", "GOLD",
  "RED", "MAROON", "PURPLE", "PINK", "ORANGE", "GREY"];

interface Props {
  sel: Selection;
  scene: SceneModel | null;
  model: Model | null;
  busy: boolean;
  f: number;
  sendEdit: (msg: object) => void;
}

/** A value typed by the user: number, name (ACCENT, smooth) or "string". */
function parseValue(text: string): object | null {
  const t = text.trim();
  if (/^[-+]?(\d+\.?\d*|\.\d+)$/.test(t)) return { number: Number(t) };
  if (/^[A-Za-z_][\w.]*$/.test(t)) return { name: t };
  const m = t.match(/^[rR]?(["'])(.*)\1$/s);
  if (m) return { string: m[2] };
  return null;
}

function Field({ label, value, onCommit, disabled, title }: {
  label: string; value: string; onCommit: (v: string) => void; disabled?: boolean; title?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <div className="row" title={title}>
      <label>{label}</label>
      <input value={v} disabled={disabled} onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && v !== value) onCommit(v); if (e.key === "Escape") setV(value); }}
        onBlur={() => { if (v !== value) setV(value); }} />
    </div>
  );
}

export function Inspector({ sel, scene, model, busy, f, sendEdit }: Props) {
  const [newProp, setNewProp] = useState("");
  const [newVal, setNewVal] = useState("");
  if (!sel || !scene || !model) {
    return (
      <div>
        <h3>Inspector</h3>
        <div className="muted">Click an object on the canvas or in Layers, or a clip on the timeline.</div>
        <div className="muted small-gap">Edits are written to the .py file only after a replay shows they do exactly what you asked. Undo restores the file byte for byte.</div>
      </div>
    );
  }

  if (sel.kind === "clip") {
    const c = scene.clips[sel.clip];
    if (!c) return null;
    const a = sel.anim !== null ? c.anims[sel.anim] : null;
    const locked = c.lock ?? (c.tier === 3 ? "tier 3 code: edit it in the code" : null);
    const dur = a ? a.run_time : c.duration;
    const rate = a ? a.rate_func : c.anims[0]?.rate_func;
    const edit = (fieldName: string, value: unknown) =>
      sendEdit({ type: "edit.timing", clip: c.index, anim: sel.anim, field: fieldName, value });
    return (
      <div>
        <h3>{a ? a.class.replace("_MethodAnimation", ".animate") : c.kind === "wait" ? "Pause" : "play()"} <small>line {c.line}</small></h3>
        {locked && <div className="note">🔒 {locked}</div>}
        <div className="code tiny">{c.text}</div>
        <div className="row"><label>Starts</label><span className="mono">{c.start.toFixed(3)} s</span></div>
        <Field label={c.kind === "wait" ? (c.call_name === "at" ? "Pause" : "wait") : "run_time"}
          value={dur.toFixed(3).replace(/\.?0+$/, "")} disabled={!!locked || busy}
          title={c.call_name === "at" ? "changes the at() time that ends this pause" : "Enter to apply"}
          onCommit={(v) => { const n = Number(v); if (n > 0) edit("duration", n); }} />
        {c.kind === "play" && (
          <div className="row">
            <label>Easing</label>
            <select value={rate ?? ""} disabled={!!locked || busy} onChange={(e) => edit("rate_func", e.target.value)}>
              {[...new Set([rate ?? "smooth", ...RATE_FUNCS])].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        )}
        {c.kind === "play" && !a && c.anims.length > 1 && (
          <div className="muted small-gap">{c.anims.length} animations in this play(). Select one on its row to edit it alone.</div>
        )}
      </div>
    );
  }

  const o = sel.obj;
  const locked = !o.site ? "made inside library code: select its owner" : o.tier === 3 ? "tier 3 code: edit it in the code" : null;
  const kwargs = o.kwargs ?? {};
  const params = o.params ?? [];
  const positional = (o.args ?? []).map((v, i) => [params[i] ?? `arg ${i}`, v] as const)
    .filter(([p]) => !p.startsWith("arg ") && !p.startsWith("*"));
  const send = (prop: string, value: object | null) => {
    if (!value) return;
    sendEdit({ type: "edit.prop", object: o, prop, value, f });
  };
  return (
    <div>
      <h3>{o.name ?? o.class} <small>{o.class}</small></h3>
      <div className="row"><label>Tier</label><span>{o.tier === 1 ? "1 · fully editable" : o.tier === 2 ? "2 · computed (≈)" : "3 · code only 🔒"}</span></div>
      <div className="row"><label>Made at</label><span className="mono">line {(o.site ?? o.user_site)?.[0]}{o.func && o.func !== "construct" ? ` in ${o.func}()` : ""}</span></div>
      {o.center && <div className="row"><label>Position</label><span className="mono">x {o.center[0].toFixed(2)} · y {o.center[1].toFixed(2)}</span></div>}
      {o.color && <div className="row"><label>Colour now</label><span><span className="swatch" style={{ background: o.color }} /> {o.color}</span></div>}
      {locked && <div className="note">🔒 {locked}</div>}
      {o.in_helper && !locked && <div className="note">Made inside {o.func}(): edits here change every object that helper makes (you'll be asked first).</div>}
      {o.call_text && <div className="code tiny">{o.call_text}</div>}
      {!locked && (
        <>
          <h4>Arguments</h4>
          {positional.map(([p, v]) => (
            <Field key={p} label={p} value={v} disabled={busy} onCommit={(nv) => send(p, parseValue(nv))} />
          ))}
          {Object.entries(kwargs).map(([k, v]) => (
            <div key={k} className="kwrow">
              <Field label={k} value={v} disabled={busy} onCommit={(nv) => send(k, parseValue(nv))} />
              {k.includes("color") && (
                <select value="" disabled={busy} onChange={(e) => send(k, { name: e.target.value })} title="Palette">
                  <option value="">palette…</option>
                  {COLORS.map((c) => <option key={c}>{c}</option>)}
                </select>
              )}
              <button className="x" disabled={busy} title="Remove: back to the default" onClick={() => send(k, { default: true })}>×</button>
            </div>
          ))}
          <div className="row add">
            <input placeholder="property" value={newProp} onChange={(e) => setNewProp(e.target.value)} list="params" />
            <datalist id="params">{["color", "fill_opacity", "stroke_width", "font_size", ...params].map((p) => <option key={p} value={p} />)}</datalist>
            <input placeholder="value" value={newVal} onChange={(e) => setNewVal(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && newProp) { send(newProp, parseValue(newVal)); setNewProp(""); setNewVal(""); } }} />
          </div>
          <div className="muted small-gap">Type a number, a name (ACCENT, BLUE) or a "string", then Enter.</div>
        </>
      )}
    </div>
  );
}
