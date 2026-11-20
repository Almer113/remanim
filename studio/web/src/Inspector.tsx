import { useEffect, useState } from "react";
import { tip } from "./keymap";
import type { CameraState, Model, SceneModel } from "./types";
import type { Selection } from "./App";
import { EasingPicker } from "./Easing";

import { COLORS } from "./GlyphPicker";

const TEXT_KINDS = new Set(["Text", "MathTex", "Tex"]);

interface Props {
  sel: Selection;
  scene: SceneModel | null;
  model: Model | null;
  busy: boolean;
  f: number;
  onScreen: boolean;
  sendEdit: (msg: object) => void;
  /** the camera at the playhead, when it can be edited (2D moving camera or 3D) */
  camera?: CameraState | null;
  /** the camera at the end of the scene before, when this is a 3D scene's first frame */
  prevCamera?: { scene: string; cam: CameraState } | null;
  /** drag the camera on the canvas */
  camCanvas?: { on: boolean; toggle: () => void } | null;
  actions: { remove: () => void; duplicate: () => void; group: () => void; count: number; partColour?: (() => void) | null };
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

/** Camera at the playhead (Phase 5 steps 9, 10): edits the camera move before
 * it, or the 3D orientation, as the code writes them. */
function CameraPanel({ cam, busy, f, sendEdit, scene, prev, canvas }: {
  cam: CameraState; busy: boolean; f: number; sendEdit: (m: object) => void;
  scene: SceneModel | null; prev?: { scene: string; cam: CameraState } | null; canvas?: { on: boolean; toggle: () => void } | null;
}) {
  const go = (m: object) => sendEdit({ type: "edit.camera", f, ...m });
  const onCanvas = canvas && (
    <div className="btns-row"><button className={canvas.on ? "on" : ""} disabled={busy} onClick={canvas.toggle}
      title={cam.kind === "2d" ? "Drag the frame to pan, scroll to zoom" : "Drag to orbit, scroll to zoom"}>
      {canvas.on ? "Done moving the camera" : "Move on canvas"}</button></div>
  );
  if (cam.kind === "2d") {
    return (
      <div>
        <h4>Camera</h4>
        {onCanvas}
        <Field label="centre x" value={cam.center[0].toFixed(2)} disabled={busy}
          onCommit={(v) => num(v, (n) => { go({ center: [n, cam.center[1]] }); })} />
        <Field label="centre y" value={cam.center[1].toFixed(2)} disabled={busy}
          onCommit={(v) => num(v, (n) => { go({ center: [cam.center[0], n] }); })} />
        <Field label="width" value={cam.width.toFixed(2)} disabled={busy} title="Smaller is closer"
          onCommit={(v) => num(v, (n) => n > 0 ? go({ width: n }) : "more than 0")} />
      </div>
    );
  }
  return (
    <div>
      <h4>Camera (3D)</h4>
      {onCanvas}
      {(["phi", "theta", "zoom"] as const).map((k) => (
        <Field key={k} label={k === "zoom" ? "zoom" : `${k} °`} value={cam[k].toFixed(k === "zoom" ? 2 : 1)} disabled={busy}
          onCommit={(v) => num(v, (n) => k === "zoom" && n <= 0 ? "more than 0" : go({ [k]: n }))} />
      ))}
      {prev && prev.cam.kind === "3d" && (() => {
        const p = prev.cam;
        const off = (["phi", "theta"] as const).filter((k) => Math.abs(((cam[k] - p[k] + 540) % 360) - 180) > 1);
        const z = Math.abs(cam.zoom - p.zoom) > 0.01;
        if (!off.length && !z) return null;
        return (
          <div className="warn small-gap" title="A cut between scenes jumps when the camera doesn't start where the last scene ended">
            ⚠ {prev.scene} ends at {off.map((k) => `${k} ${p[k].toFixed(1)}°`).concat(z ? [`zoom ${p.zoom.toFixed(2)}`] : []).join(", ")}.
            {" "}<button disabled={busy} onClick={() => go({ phi: p.phi, theta: p.theta, ...(z ? { zoom: p.zoom } : {}) })}>Start here instead</button>
          </div>
        );
      })()}
      {(scene?.ambient ?? []).map((a, i) => (
        <Field key={`amb${i}`} label="ambient rate" title={`begin_ambient_camera_rotation on line ${a.line}: radians per second`}
          value={a.value !== null ? String(a.value) : a.text} disabled={busy || !a.span}
          onCommit={(v) => num(v, (n) => { sendEdit({ type: "edit.literal", span: a.span, value: { number: n } }); })} />
      ))}
    </div>
  );
}

export function Inspector({ sel, scene, model, busy, f, onScreen, sendEdit, actions, camera, prevCamera, camCanvas }: Props) {
  const [newProp, setNewProp] = useState("");
  const [newVal, setNewVal] = useState("");
  const [newErr, setNewErr] = useState<string | null>(null);
  if (!sel || !scene || !model) {
    return (
      <div>
        <h3>Inspector</h3>
        <div className="muted">Click an object on the canvas or in Layers, or a clip on the timeline.</div>
        <div className="muted small-gap">Edits are written to the .py file only after a replay shows they do exactly what you asked. Undo restores the file byte for byte.</div>
        {camera && <CameraPanel cam={camera} busy={busy} f={f} sendEdit={sendEdit} scene={scene} prev={prevCamera} canvas={camCanvas} />}
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
            <EasingPicker key={`${c.index}:${sel.anim}`} value={rate} fallback={a ? a.default_rate_func : c.anims[0]?.default_rate_func ?? null}
              disabled={!!locked || busy} onPick={(name) => edit("rate_func", name)} />
          </div>
        )}
        {(c.transforms ?? []).map((t, k) => t && (
          <div className="row" key={k} title="What is on screen afterwards differs: Transform keeps the source, Replacement/Fade show the target, FromCopy both">
            <label>{t.source} → {t.target}</label>
            <select value={t.kind} disabled={!!locked || busy}
              onChange={(e) => sendEdit({ type: "edit.transform_kind", clip: c.index, arg: k, kind: e.target.value })}>
              {t.kinds.map((x) => <option key={x}>{x}</option>)}
            </select>
          </div>
        ))}
        {a && (a.offset ?? 0) > 0 && (
          <div className="row"><label>Starts in group</label><span className="mono">+{(a.offset ?? 0).toFixed(2)} s</span></div>
        )}
        <div className="btns-row"><button disabled={!!locked || busy} onClick={actions.remove}
          title={tip("delete", "Delete")}>Delete {sel.anim !== null ? "this animation" : c.kind === "wait" ? "pause" : "clip"}</button></div>
        {c.kind === "play" && !a && c.anims.length > 1 && (
          <div className="muted small-gap">{c.anims.length} animations in this play(). Select one on its row to edit it alone.</div>
        )}
      </div>
    );
  }

  const o = sel.obj;
  const locked = !o.site ? (o.curve ? "drawn by the plot call on its line: edit its formula above; move or copy its axes" : "made inside library code: select its owner") : o.tier === 3 ? "tier 3 code: edit it in the code" : null;
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
        <button disabled={!!locked || busy || off || !!o.virtual} onClick={actions.duplicate} title={tip("duplicate")}>Duplicate</button>
        <button disabled={busy || off || actions.count < 2} onClick={actions.group}
          title={tip("group")}>Group{actions.count > 1 ? ` ${actions.count}` : ""}</button>
        <button disabled={!!locked || busy} onClick={actions.remove} title={tip("delete", "Delete")}>Delete</button>
        {TEXT_KINDS.has(o.class) && (
          <button disabled={!!locked || busy || off || !actions.partColour} onClick={() => actions.partColour?.()}
            title="Colour some letters or symbols of this text">Colour part…</button>
        )}
      </div>
      {(o.ranges ?? []).map((r) => (
        <div key={r.kw}>
          <h4>{r.kw}</h4>
          {r.parts.map((pt, j) => (
            <Field key={j} label={pt.label} value={pt.text} disabled={busy || !pt.span}
              title={pt.span ? "Enter to apply" : "computed in the code: change it there"}
              onCommit={(v) => num(v, (n) => { sendEdit({ type: "edit.literal", span: pt.span, value: { number: n } }); })} />
          ))}
        </div>
      ))}
      {o.curve && (
        <Field label={`f(${o.curve.params.join(", ")}) =`} value={o.curve.expr} disabled={busy}
          title="The curve's formula, as Python (np.sin(x), x**2). Checked, then replayed"
          onCommit={(v) => { sendEdit({ type: "edit.curve", object: o, expr: v }); return null; }} />
      )}
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
