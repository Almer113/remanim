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
  onScreen: boolean;
  sendEdit: (msg: object) => void;
  actions: { remove: () => void; duplicate: () => void; group: () => void; count: number };
}

/** Parse a typed number and run `go`; returns the reason when it isn't one. */
function num(v: string, go: (n: number) => void | string): string | null {
  const n = Number(v.trim());
  if (!v.trim() || !Number.isFinite(n)) return "A number";
  const r = go(n);
  return typeof r === "string" ? r : null;
}

const BAD_VALUE = "Type a number (2, -0.5, 1e-3), a name (ACCENT, BLUE) or a \"string\"";

/** A value typed by the user: number, name (ACCENT, smooth) or "string". */
function parseValue(text: string): object | null {
  const t = text.trim();
  if (/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(t)) {
    const n = Number(t);
    return Number.isFinite(n) ? { number: n } : null;
  }
  if (/^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$/.test(t)) return { name: t };
  const m = t.match(/^[rR]?(["'])(.*)\1$/s);
  if (m) return { string: m[2] };
  return null;
}

/** An input that commits on Enter. Leaving it undoes the change (an edit
 * replays the scene, so it never fires by accident); a wrong value stays
 * in the box, marked, with the reason. */
function Field({ label, value, onCommit, disabled, title }: {
  label: string; value: string; onCommit: (v: string) => string | null; disabled?: boolean; title?: string;
}) {
  const [v, setV] = useState(value);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setV(value); setErr(null); }, [value]);
  const dirty = v !== value;
  return (
    <div className="row" title={err ?? title}>
      <label>{label}</label>
      <input value={v} disabled={disabled} className={err ? "bad" : dirty ? "dirty" : ""}
        onChange={(e) => { setV(e.target.value); setErr(null); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && dirty) setErr(onCommit(v));
          if (e.key === "Escape") { setV(value); setErr(null); }
        }}
        onBlur={() => { if (dirty && !err) setV(value); }} />
      {err && <span className="field-err">{err}</span>}
      {dirty && !err && <span className="field-hint">↵ to apply</span>}
    </div>
  );
}

export function Inspector({ sel, scene, model, busy, f, onScreen, sendEdit, actions }: Props) {
  const [newProp, setNewProp] = useState("");
  const [newVal, setNewVal] = useState("");
  const [newErr, setNewErr] = useState<string | null>(null);
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
          onCommit={(v) => {
            const n = Number(v.trim());
            if (!v.trim() || !Number.isFinite(n) || n <= 0) return "A length in seconds, more than 0";
            edit("duration", n);
            return null;
          }} />
        {c.kind === "play" && (
          <div className="row">
            <label>Easing</label>
            <select value={rate ?? ""} disabled={!!locked || busy}
              onChange={(e) => edit("rate_func", e.target.value || (a ? a.default_rate_func : c.anims[0]?.default_rate_func) || "smooth")}>
              {!rate && <option value="">(default)</option>}
              {[...new Set([...(rate ? [rate] : []), ...RATE_FUNCS])].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        )}
        <div className="btns-row"><button disabled={!!locked || busy} onClick={actions.remove}
          title="Delete (Del)">Delete {sel.anim !== null ? "this animation" : c.kind === "wait" ? "pause" : "clip"}</button></div>
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
  const send = (prop: string, value: object | null): string | null => {
    if (!value) return BAD_VALUE;
    if (!/^[A-Za-z_]\w*$/.test(prop)) return "A property is a keyword name, like fill_opacity";
    sendEdit({ type: "edit.prop", object: o, prop, value, f });
    return null;
  };
  const off = !onScreen;
  return (
    <div>
      <h3>{o.name ?? o.class} <small>{o.class}</small></h3>
      <div className="row"><label>Tier</label><span>{o.tier === 1 ? "1 · fully editable" : o.tier === 2 ? "2 · computed (≈)" : "3 · code only 🔒"}</span></div>
      <div className="row"><label>Made at</label><span className="mono">line {(o.site ?? o.user_site)?.[0]}{o.func && o.func !== "construct" ? ` in ${o.func}()` : ""}</span></div>
      {o.center && (locked || off || busy) && <div className="row"><label>Position</label><span className="mono">x {o.center[0].toFixed(2)} · y {o.center[1].toFixed(2)}</span></div>}
      {o.center && !locked && !off && !busy && (
        <>
          <Field label="x" value={o.center[0].toFixed(2)} title="Where its centre is; Enter writes the move into the code"
            onCommit={(v) => num(v, (n) => sendEdit({ type: "edit.move", object: o, f, dx: n - o.center![0], dy: 0 }))} />
          <Field label="y" value={o.center[1].toFixed(2)}
            onCommit={(v) => num(v, (n) => sendEdit({ type: "edit.move", object: o, f, dx: 0, dy: n - o.center![1] }))} />
          <Field label="scale ×" value="1" title="Scale about its centre, e.g. 1.5"
            onCommit={(v) => num(v, (n) => n > 0 ? sendEdit({ type: "edit.scale", object: o, f, k: n }) : "more than 0")} />
          <Field label="turn °" value="0" title="Turn anticlockwise by this many degrees"
            onCommit={(v) => num(v, (n) => sendEdit({ type: "edit.rotate", object: o, f, deg: n }))} />
        </>
      )}
      <div className="btns-row">
        <button disabled={!!locked || busy || off || !!o.virtual} onClick={actions.duplicate} title="Duplicate (Ctrl+D)">Duplicate</button>
        <button disabled={busy || off || actions.count < 2} onClick={actions.group}
          title="Group the selection (Ctrl+G); Shift-click to add objects">Group{actions.count > 1 ? ` ${actions.count}` : ""}</button>
        <button disabled={!!locked || busy} onClick={actions.remove} title="Delete (Del)">Delete</button>
      </div>
      {o.color && <div className="row"><label>Colour now</label><span><span className="swatch" style={{ background: o.color }} /> {o.color}</span></div>}
      {locked && <div className="note">🔒 {locked}</div>}
      {!locked && off && <div className="note">Not on screen at this frame: move the playhead to where it shows to edit it.</div>}
      {o.in_helper && !locked && <div className="note">Made inside {o.func}(): edits here change every object that helper makes (you'll be asked first).</div>}
      {o.call_text && <div className="code tiny">{o.call_text}</div>}
      {!locked && (
        <>
          <h4>Arguments</h4>
          {positional.map(([p, v]) => (
            <Field key={p} label={p} value={v} disabled={busy || off} onCommit={(nv) => send(p, parseValue(nv))} />
          ))}
          {Object.entries(kwargs).map(([k, v]) => (
            <div key={k} className="kwrow">
              <Field label={k} value={v} disabled={busy || off} onCommit={(nv) => send(k, parseValue(nv))} />
              {k.includes("color") && (
                <select value="" disabled={busy || off} onChange={(e) => send(k, { name: e.target.value })} title="Palette">
                  <option value="">palette…</option>
                  {COLORS.map((c) => <option key={c}>{c}</option>)}
                </select>
              )}
              <button className="x" disabled={busy || off} title="Remove: back to the default" onClick={() => send(k, { default: true })}>×</button>
            </div>
          ))}
          <div className="row add">
            <input placeholder="property" value={newProp} disabled={off} onChange={(e) => { setNewProp(e.target.value); setNewErr(null); }} list="params" />
            <datalist id="params">{["color", "fill_opacity", "stroke_width", "font_size", ...params].map((p) => <option key={p} value={p} />)}</datalist>
            <input placeholder="value" value={newVal} disabled={off} className={newErr ? "bad" : ""}
              onChange={(e) => { setNewVal(e.target.value); setNewErr(null); }}
              onKeyDown={(e) => {
                if (e.key !== "Enter" || !newProp.trim()) return;
                const why = send(newProp.trim(), parseValue(newVal));
                setNewErr(why);
                if (!why) { setNewProp(""); setNewVal(""); }
              }} />
          </div>
          <div className={newErr ? "field-err small-gap" : "muted small-gap"}>{newErr ?? "Type a number, a name (ACCENT, BLUE) or a \"string\", then Enter."}</div>
        </>
      )}
    </div>
  );
}
