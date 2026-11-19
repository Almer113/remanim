import { useEffect, useRef, useState } from "react";
import type { CameraState, Ghost, LibItem, Obj, TextArg } from "./types";
import { TextEditor } from "./TextEditor";
import { GlyphPicker } from "./GlyphPicker";
import { TransformGhost } from "./TransformGhost";
import { CameraGizmo } from "./CameraGizmo";
import { fixedLines, joinLines, objectLines, snapMove, tidy, type Box, type Lines } from "./guides";

export interface Gesture { obj: Obj; kind: "move" | "scale" | "rotate"; dx: number; dy: number; k: number; deg: number }

interface Props {
  url: string;
  idmapUrl: string | null;
  width: number;
  height: number;
  frameW: number;   // scene units
  frameH: number;
  objects: Obj[];
  selected: string | null;
  others: string[];   // shift-click multi-selection
  onSelect: (o: Obj | null, how: "set" | "toggle") => void;
  onGesture: (g: Gesture) => void;
  onDrop: (item: LibItem, x: number, y: number, on: Obj | null) => void;
  editable: boolean;
  stale: boolean;
  /** Double-click on a text object: edit it in place (null: not possible now). */
  onTextEdit?: ((o: Obj) => void) | null;
  textEdit?: Obj | null;
  onTextDone?: (changes: { span: NonNullable<TextArg["span"]>; value: string }[] | null) => void;
  /** Part colour: pick glyphs of this text (null: not picking). */
  partPick?: Obj | null;
  glyphUrl?: string | null;
  onPartDone?: (pick: { glyphs: number[]; colour: string } | null) => void;
  /** The selected transform clip under the playhead: where it is going (step 8). */
  ghosts?: Ghost[] | null;
  onMatch?: ((index: number, sourceKey: string, targetKey: string) => void) | null;
  /** Camera mode: drags and the wheel move the camera instead of objects. */
  camera?: { cam: CameraState; onCommit: (m: object) => void; onClose: () => void } | null;
}

type Drag = {
  obj: Obj;
  kind: "move" | "scale" | "rotate";
  x0: number; y0: number;   // canvas px at mousedown
  x: number; y: number;     // canvas px now
  started: boolean;
  picked: Obj | null;   // what was clicked (a click selects this; a drag moves `obj`)
  shift: boolean; alt: boolean;
  ghost: HTMLCanvasElement | null;  // the object's own pixels, cut out with the ID map
  hole: HTMLCanvasElement | null;   // a dark mask over where it was
  gx: number | null; gy: number | null;  // guide lines hit (scene units)
  url: string;          // the frame the drag started on: a gesture on another frame is void
};

const HANDLE = 5;     // half-size of a scale handle, canvas px
const ROT_GAP = 22;   // rotate handle above the box
const SNAP_PX = 7;    // snapping distance on screen

/** The real Manim frame, with hover and selection resolved in the browser
 * from the ID map (one colour per selectable object, architecture.md §6),
 * and canvas gestures that become code edits on release. */
export function Canvas(p: Props) {
  const { url, idmapUrl, width, height, frameW, frameH, objects, selected, others, editable, stale } = p;
  const [shown, setShown] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const [hover, setHover] = useState<Obj | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [dropAt, setDropAt] = useState<[number, number] | null>(null);
  // the last gesture stays drawn until the edited frame comes back
  const [held, setHeld] = useState<Drag | null>(null);
  const ids = useRef<ImageData | null>(null);
  const img = useRef<HTMLImageElement>(null);
  const overlay = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);

  // swap images only once the next one has loaded: no flashing while scrubbing
  useEffect(() => {
    let gone = false;
    setFailed(null);
    const slowTimer = window.setTimeout(() => { if (!gone) setSlow(true); }, 700);
    const im = new Image();
    im.onload = () => {
      if (gone) return;
      clearTimeout(slowTimer);
      setSlow(false);
      setShown(url);
    };
    im.onerror = () => {
      if (gone) return;
      clearTimeout(slowTimer);
      setSlow(false);
      // 410 = an edit or reload made a new revision; the new frame follows
      fetch(url).then((r) => r.status === 410 ? null : r.text().then((t) => t || `HTTP ${r.status}`))
        .then((why) => { if (!gone && why) setFailed(why.slice(0, 160)); })
        .catch(() => { if (!gone) setFailed("the studio server isn't answering"); });
    };
    im.src = url;
    return () => { gone = true; clearTimeout(slowTimer); };
  }, [url]);

  useEffect(() => {
    ids.current = null;
    if (!idmapUrl) return;
    let gone = false;
    const im = new Image();
    im.onload = () => {
      if (gone) return;
      const c = document.createElement("canvas");
      c.width = im.width;
      c.height = im.height;
      const ctx = c.getContext("2d", { willReadFrequently: true })!;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(im, 0, 0);
      ids.current = ctx.getImageData(0, 0, im.width, im.height);
    };
    im.src = idmapUrl;
    return () => { gone = true; };
  }, [idmapUrl]);

  // the ghost of the last gesture stays until the edited frame is on screen;
  // a refused edit leaves the frame as it was, so the ghost goes with the reply
  useEffect(() => { setHeld(null); }, [shown]);
  useEffect(() => { if (editable) setHeld((h) => (h && h.url === url ? null : h)); }, [editable, url]);

  // -- coordinates ----------------------------------------------------------------
  const toCanvas = (e: { clientX: number; clientY: number }): [number, number] => {
    const r = wrap.current!.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * width, ((e.clientY - r.top) / r.height) * height];
  };
  const pxPerUnit = width / frameW;
  const toUnits = (x: number, y: number): [number, number] => [(x / width - 0.5) * frameW, (0.5 - y / height) * frameH];
  const screenScale = () => {
    const r = wrap.current?.getBoundingClientRect();
    return r && r.width ? width / r.width : 1;  // canvas px per screen px
  };
  // the exact centre (scene units) where known; the drawn box's otherwise
  const centreOf = (o: Obj): [number, number] => {
    if (o.center) return o.center;
    const b = unitsBox(o)!;
    return [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2];
  };
  const unitsBox = (o: Obj): Box | null => {
    if (!o.box) return null;
    const [a, b] = toUnits(o.box[0], o.box[1]);
    const [c, d] = toUnits(o.box[2], o.box[3]);
    return { x0: a, x1: c, y0: d, y1: b };
  };

  // the drawn objects an object stands for (a user group: its children)
  const members = (o: Obj): number[] => {
    const i = objects.indexOf(o);
    if (i < 0) return [];
    const out: number[] = o.virtual ? [] : [i];
    objects.forEach((x, j) => {
      let q = x.parent;
      let n = 0;
      while (q !== undefined && n++ < 8) {
        if (q === i) { if (!x.virtual) out.push(j); break; }
        q = objects[q]?.parent;
      }
    });
    return out;
  };
  const ancestorsOf = (o: Obj): Set<number> => {
    const s = new Set<number>();
    let q = o.parent;
    while (q !== undefined && !s.has(q)) { s.add(q); q = objects[q]?.parent; }
    return s;
  };

  // a part made inside library code (a glyph of a Tex) stands for its owner
  const ownerOf = (o: Obj): Obj => {
    let u = o, n = 0;
    while (!u.site && u.parent !== undefined && objects[u.parent] && n++ < 8) u = objects[u.parent];
    return u.site ? u : o;
  };

  const pickAt = (x: number, y: number): Obj | null => {
    const d = ids.current;
    // the ID map belongs to `url`; while an older image is still shown, clicks resolve to nothing
    if (!d || shown !== url) return null;
    const px0 = Math.floor((x / width) * d.width);
    const py0 = Math.floor((y / height) * d.height);
    // exact pixel first, then the nearest object within 4 px (thin lines)
    for (let rad = 0; rad <= 4; rad++) {
      for (let dy = -rad; dy <= rad; dy++) {
        for (let dx = -rad; dx <= rad; dx++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== rad) continue;
          const px = px0 + dx, py = py0 + dy;
          if (px < 0 || py < 0 || px >= d.width || py >= d.height) continue;
          const i = (py * d.width + px) * 4;
          const idx = (d.data[i] << 16) | (d.data[i + 1] << 8) | d.data[i + 2];
          if (idx > 0 && idx <= objects.length) return ownerOf(objects[idx - 1]);
        }
      }
    }
    return null;
  };

  const sel = objects.find((o) => o.id === selected) ?? null;

  // which handle of the selection is under (x, y)
  const handleAt = (x: number, y: number): "scale" | "rotate" | null => {
    if (!sel?.box || !editable) return null;
    const [x0, y0, x1, y1] = sel.box;
    const tol = HANDLE + 2 * screenScale();
    // a small object (a Dot) is mostly corners: a press on its own pixels moves it
    const small = x1 - x0 < 4 * tol || y1 - y0 < 4 * tol;
    const onIt = small && x >= x0 && x <= x1 && y >= y0 && y <= y1;
    for (const [hx, hy] of [[x0, y0], [x1, y0], [x0, y1], [x1, y1]]) {
      if (!onIt && Math.abs(x - hx) <= tol && Math.abs(y - hy) <= tol) return "scale";
    }
    if (Math.hypot(x - (x0 + x1) / 2, y - (y0 - ROT_GAP * screenScale())) <= tol + 2) return "rotate";
    return null;
  };

  // -- the object's own pixels, for the ghost --------------------------------------
  const cutOut = (o: Obj): [HTMLCanvasElement, HTMLCanvasElement] | [null, null] => {
    const d = ids.current, im = img.current;
    if (!d || !im || !o.box) return [null, null];
    const want = new Set(members(o).map((i) => i + 1));
    if (!want.size) return [null, null];
    const sx = d.width / width, sy = d.height / height;
    const bx0 = Math.max(0, Math.floor((o.box[0] - 3) * sx)), by0 = Math.max(0, Math.floor((o.box[1] - 3) * sy));
    const bx1 = Math.min(d.width, Math.ceil((o.box[2] + 3) * sx)), by1 = Math.min(d.height, Math.ceil((o.box[3] + 3) * sy));
    const w = bx1 - bx0, h = by1 - by0;
    if (w <= 0 || h <= 0) return [null, null];
    const src = document.createElement("canvas");
    src.width = d.width;
    src.height = d.height;
    const sctx = src.getContext("2d", { willReadFrequently: true })!;
    sctx.drawImage(im, 0, 0, d.width, d.height);
    const frame = sctx.getImageData(bx0, by0, w, h);
    const ghost = document.createElement("canvas"), hole = document.createElement("canvas");
    ghost.width = hole.width = w;
    ghost.height = hole.height = h;
    const g = ghost.getContext("2d")!.createImageData(w, h);
    const m = hole.getContext("2d")!.createImageData(w, h);
    for (let yy = 0; yy < h; yy++) {
      for (let xx = 0; xx < w; xx++) {
        // grow the mask by one pixel: the ID map drops antialiased edges
        let mine = false;
        for (let ky = -1; ky <= 1 && !mine; ky++) {
          for (let kx = -1; kx <= 1 && !mine; kx++) {
            const X = bx0 + xx + kx, Y = by0 + yy + ky;
            if (X < 0 || Y < 0 || X >= d.width || Y >= d.height) continue;
            const i = (Y * d.width + X) * 4;
            mine = want.has((d.data[i] << 16) | (d.data[i + 1] << 8) | d.data[i + 2]);
          }
        }
        if (!mine) continue;
        const j = (yy * w + xx) * 4;
        g.data[j] = frame.data[j];
        g.data[j + 1] = frame.data[j + 1];
        g.data[j + 2] = frame.data[j + 2];
        g.data[j + 3] = 235;
        m.data[j + 3] = 150;
      }
    }
    ghost.getContext("2d")!.putImageData(g, 0, 0);
    hole.getContext("2d")!.putImageData(m, 0, 0);
    // remember where the cut-out sits, in canvas px
    (ghost as any).at = [bx0 / sx, by0 / sy, w / sx, h / sy];
    return [ghost, hole];
  };

  // -- what a drag means -------------------------------------------------------------
  const lines = (o: Obj): Lines => {
    const fixed = fixedLines();
    const skip = new Set([...members(o), objects.indexOf(o), ...ancestorsOf(o)]);
    const items = objects.filter((x, i) => !skip.has(i) && !x.virtual && x.box && !ancestorsOf(x).has(objects.indexOf(o)))
      .map((x) => ({ box: unitsBox(x)!, c: centreOf(x) }));
    return joinLines(fixed, objectLines(items));
  };

  const solve = (dr: Drag): Gesture & { gx: number | null; gy: number | null } => {
    const o = dr.obj;
    const base = { obj: o, kind: dr.kind, dx: 0, dy: 0, k: 1, deg: 0, gx: null, gy: null };
    if (!o.box) return base;
    const cx = (o.box[0] + o.box[2]) / 2, cy = (o.box[1] + o.box[3]) / 2;
    if (dr.kind === "move" && o.proj) {
      // 3D: the drag moves it on the world's floor (x-y), solved through the camera
      const sx = (dr.x - dr.x0) / pxPerUnit, sy = -(dr.y - dr.y0) / pxPerUnit;
      const [a, b] = o.proj.ex, [c, d] = o.proj.ey, det = a * d - b * c;
      if (Math.abs(det) < 0.05) return base;  // the floor is seen edge-on
      let wx = (sx * d - sy * c) / det, wy = (a * sy - b * sx) / det;
      if (dr.shift) { if (Math.abs(wx) > Math.abs(wy)) wy = 0; else wx = 0; }
      return { ...base, dx: tidy.dist(wx), dy: tidy.dist(wy) };
    }
    if (dr.kind === "move") {
      let ddx = (dr.x - dr.x0) / pxPerUnit, ddy = -(dr.y - dr.y0) / pxPerUnit;
      if (dr.shift) { if (Math.abs(ddx) > Math.abs(ddy)) ddy = 0; else ddx = 0; }
      if (!dr.alt) {
        const b = unitsBox(o)!;
        const tol = (SNAP_PX * screenScale()) / pxPerUnit;
        const s = snapMove(b, centreOf(o), ddx, ddy, lines(o), tol, !dr.shift ? "xy" : ddy === 0 ? "x" : "y");
        return { ...base, dx: s.gx === null ? tidy.dist(s.dx) : tidy.snapped(s.dx),
          dy: s.gy === null ? tidy.dist(s.dy) : tidy.snapped(s.dy), gx: s.gx, gy: s.gy };
      }
      return { ...base, dx: ddx, dy: ddy };
    }
    if (dr.kind === "scale") {
      const d0 = Math.hypot(dr.x0 - cx, dr.y0 - cy), d1 = Math.hypot(dr.x - cx, dr.y - cy);
      return { ...base, k: d0 > 1 ? tidy.k(d1 / d0, dr.alt) : 1 };
    }
    const a0 = Math.atan2(-(dr.y0 - cy), dr.x0 - cx), a1 = Math.atan2(-(dr.y - cy), dr.x - cx);
    let deg = ((a1 - a0) * 180) / Math.PI;
    deg = ((deg + 540) % 360) - 180;
    return { ...base, deg: tidy.deg(deg, dr.alt) };
  };

  // -- drawing -----------------------------------------------------------------------
  useEffect(() => {
    const c = overlay.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, c.width, c.height);
    const s = screenScale();
    const strokeBox = (o: Obj, color: string, dash: number[]) => {
      if (!o.box) return;
      const [x0, y0, x1, y1] = o.box;
      ctx.setLineDash(dash.map((v) => v * s));
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5 * s;
      ctx.strokeRect(x0 - 2.5 * s, y0 - 2.5 * s, x1 - x0 + 5 * s, y1 - y0 + 5 * s);
      ctx.setLineDash([]);
    };
    const active = drag?.started ? drag : held;
    if (active) {
      const g = solve(active);
      const o = active.obj;
      const at = active.ghost ? (active.ghost as any).at as number[] : null;
      if (active.hole && at) ctx.drawImage(active.hole, at[0], at[1], at[2], at[3]);
      if (o.box) {
        const cx = (o.box[0] + o.box[2]) / 2, cy = (o.box[1] + o.box[3]) / 2;
        ctx.save();
        ctx.translate(cx + g.dx * pxPerUnit, cy - g.dy * pxPerUnit);
        ctx.rotate((-g.deg * Math.PI) / 180);
        ctx.scale(g.k, g.k);
        if (active.ghost && at) ctx.drawImage(active.ghost, at[0] - cx, at[1] - cy, at[2], at[3]);
        ctx.setLineDash([5 * s, 3 * s]);
        ctx.strokeStyle = "#3b8cff";
        ctx.lineWidth = (1.5 * s) / g.k;
        ctx.strokeRect(o.box[0] - cx, o.box[1] - cy, o.box[2] - o.box[0], o.box[3] - o.box[1]);
        ctx.restore();
        // guides
        ctx.strokeStyle = "rgba(255, 90, 160, 0.9)";
        ctx.lineWidth = 1 * s;
        ctx.setLineDash([]);
        if (g.gx !== null) { const X = (g.gx / frameW + 0.5) * width; ctx.beginPath(); ctx.moveTo(X, 0); ctx.lineTo(X, height); ctx.stroke(); }
        if (g.gy !== null) { const Y = (0.5 - g.gy / frameH) * height; ctx.beginPath(); ctx.moveTo(0, Y); ctx.lineTo(width, Y); ctx.stroke(); }
        // readout
        const label = g.kind === "move" ? `Δx ${g.dx.toFixed(2)}  Δy ${g.dy.toFixed(2)}`
          : g.kind === "scale" ? `× ${g.k.toFixed(2)}` : `${g.deg.toFixed(0)}°`;
        ctx.font = `${12 * s}px system-ui`;
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(16, 18, 22, 0.85)";
        ctx.fillRect(active.x + 12 * s, active.y + 10 * s, tw + 10 * s, 18 * s);
        ctx.fillStyle = "#e6e8eb";
        ctx.fillText(label, active.x + 17 * s, active.y + 23 * s);
      }
      return;
    }
    for (const id of others) {
      const o = objects.find((x) => x.id === id);
      if (o && o.id !== selected) strokeBox(o, "#7fb2ff", [2, 2]);
    }
    if (hover && hover.id !== selected) strokeBox(hover, "rgba(120,180,255,0.8)", [4, 3]);
    if (sel) {
      strokeBox(sel, "#2f7de1", []);
      if (sel.box) {
        const [x0, y0, x1, y1] = sel.box;
        ctx.fillStyle = "#2f7de1";
        ctx.font = `${11 * s}px system-ui`;
        ctx.fillText(`${sel.name ?? sel.class} · ${sel.class}`, x0, Math.max(11 * s, y0 - ROT_GAP - 10 * s));
        if (editable) {
          const h = HANDLE * s;
          ctx.fillStyle = "#fff";
          ctx.strokeStyle = "#2f7de1";
          ctx.lineWidth = 1.2 * s;
          for (const [hx, hy] of [[x0, y0], [x1, y0], [x0, y1], [x1, y1]]) {
            ctx.fillRect(hx - h, hy - h, 2 * h, 2 * h);
            ctx.strokeRect(hx - h, hy - h, 2 * h, 2 * h);
          }
          const mx = (x0 + x1) / 2;
          ctx.beginPath(); ctx.moveTo(mx, y0 - 2.5 * s); ctx.lineTo(mx, y0 - ROT_GAP * s + h); ctx.stroke();
          ctx.beginPath(); ctx.arc(mx, y0 - ROT_GAP * s, h, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
        }
      }
    }
    if (dropAt) {
      const [x, y] = dropAt;
      ctx.strokeStyle = "#4fb878";
      ctx.lineWidth = 1.5 * s;
      ctx.beginPath(); ctx.moveTo(x - 9 * s, y); ctx.lineTo(x + 9 * s, y); ctx.moveTo(x, y - 9 * s); ctx.lineTo(x, y + 9 * s); ctx.stroke();
    }
  }, [objects, selected, others, hover, drag, held, dropAt, editable]); // eslint-disable-line react-hooks/exhaustive-deps

  // -- mouse -------------------------------------------------------------------------
  const onDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    const [x, y] = toCanvas(e);
    const h = handleAt(x, y);
    if (h && sel) {
      e.preventDefault();
      setDrag({ obj: sel, picked: sel, kind: h, x0: x, y0: y, x, y, started: false, shift: e.shiftKey,
        alt: e.altKey, ghost: null, hole: null, gx: null, gy: null, url });
      return;
    }
    let o = pickAt(x, y);
    // inside the selection's box, a press drags the selection (a hollow Square
    // has no pixels inside it), unless another object is under the pointer
    const inSel = !!(sel?.box && editable && x >= sel.box[0] && x <= sel.box[2] && y >= sel.box[1] && y <= sel.box[3]);
    if (inSel && (!o || o === sel || members(sel!).includes(objects.indexOf(o)))) o = o ?? sel;
    // dragging an object inside the selected group moves the group
    const target = o && sel && (o === sel || sel.virtual && members(sel).includes(objects.indexOf(o))) ? sel : o;
    if (o) e.preventDefault();
    setDrag({ obj: target as Obj, picked: o, kind: "move", x0: x, y0: y, x, y, started: false, shift: e.shiftKey,
      alt: e.altKey, ghost: null, hole: null, gx: null, gy: null, url });
  };

  useEffect(() => {
    if (!drag) return;
    const cancel = () => setDrag(null);   // nothing is sent
    const move = (e: MouseEvent) => {
      // the button came up outside the window (Alt-Tab): the drag is over
      if ((e.buttons & 1) === 0) { cancel(); return; }
      const [x, y] = toCanvas(e);
      const d = drag;
      if (!d.started) {
        const far = Math.hypot(x - d.x0, y - d.y0) > 3 * screenScale();
        if (!far || !d.obj || !editable) return;
        const [ghost, hole] = cutOut(d.obj);
        if (d.obj.id !== selected) p.onSelect(d.obj, "set");
        setDrag({ ...d, x, y, started: true, ghost, hole, shift: e.shiftKey, alt: e.altKey });
        return;
      }
      setDrag({ ...d, x, y, shift: e.shiftKey, alt: e.altKey });
    };
    // Shift and Alt pressed or let go without moving the mouse change the ghost too
    const keys = (e: KeyboardEvent) => {
      // (App's Escape, which clears the selection, listens on window too)
      if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); cancel(); return; }
      if ((e.key === "Shift" || e.key === "Alt") && drag.started) {
        if (e.key === "Alt") e.preventDefault();  // no menu bar focus on Windows
        setDrag({ ...drag, shift: e.shiftKey, alt: e.altKey });
      }
    };
    const up = (e: MouseEvent) => {
      const d = drag;
      setDrag(null);
      if (!d.started) {
        // a click: select, shift-click adds, alt-click goes up to the group
        const o = d.picked;
        if (!o) { if (!e.shiftKey) p.onSelect(null, "set"); return; }
        if (e.altKey) {
          let up = o;
          if (sel && ancestorsOf(o).has(objects.indexOf(sel)) || sel === o) up = sel ?? o;
          const q = up.parent !== undefined ? objects[up.parent] : null;
          p.onSelect(q ?? up, "set");   // already at the top: stay there
        } else p.onSelect(o, e.shiftKey ? "toggle" : "set");
        return;
      }
      // the frame changed under the drag (playback, a seek, an undo, a reload),
      // or editing stopped: the gesture belongs to a picture that is gone
      if (d.url !== url || !editable) return;
      // what was drawn is what is sent: the modifiers of the last move or key
      const g = solve(d);
      const nothing = g.kind === "move" ? Math.abs(g.dx) < 1e-3 && Math.abs(g.dy) < 1e-3
        : g.kind === "scale" ? Math.abs(g.k - 1) < 1e-3 : Math.abs(g.deg) < 0.01;
      if (nothing) return;
      setHeld(d);
      p.onGesture(g);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    window.addEventListener("keydown", keys, true);
    window.addEventListener("keyup", keys, true);
    window.addEventListener("blur", cancel);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("keydown", keys, true);
      window.removeEventListener("keyup", keys, true);
      window.removeEventListener("blur", cancel);
    };
  }, [drag, objects, selected, editable, url]); // eslint-disable-line react-hooks/exhaustive-deps

  const onHover = (e: React.MouseEvent) => {
    if (drag) return;
    const [x, y] = toCanvas(e);
    const h = handleAt(x, y);
    const o = h ? null : pickAt(x, y);
    setHover(o);
    const el = wrap.current;
    if (el) el.style.cursor = h === "scale" ? "nwse-resize" : h === "rotate" ? "grab" : o && editable ? "move" : "default";
  };

  // -- library drops -----------------------------------------------------------------
  const libItem = (e: React.DragEvent): LibItem | null => {
    try {
      const t = e.dataTransfer.getData("application/x-studio");
      return t ? JSON.parse(t) : null;
    } catch { return null; }
  };
  const onDragOver = (e: React.DragEvent) => {
    // while editing is off the drop is still taken, and App says why nothing happens
    if (!e.dataTransfer.types.includes("application/x-studio")) return;
    e.preventDefault();
    if (!editable) { setDropAt(null); return; }
    e.dataTransfer.dropEffect = "copy";
    const [x, y] = toCanvas(e);
    const o = pickAt(x, y);
    setHover(o);
    setDropAt([x, y]);
  };
  const onDrop = (e: React.DragEvent) => {
    const item = libItem(e);
    setDropAt(null);
    if (!item) return;
    e.preventDefault();
    const [x, y] = toCanvas(e);
    let [ux, uy] = toUnits(x, y);
    if (item.kind === "shape" && !e.altKey) {
      // a drop near a guide lands on it
      const tol = (SNAP_PX * screenScale()) / pxPerUnit;
      const s = snapMove({ x0: ux, x1: ux, y0: uy, y1: uy }, [ux, uy], 0, 0, fixedLines(), tol);
      ux = s.gx === null ? tidy.dist(ux) : tidy.snapped(ux + s.dx);
      uy = s.gy === null ? tidy.dist(uy) : tidy.snapped(uy + s.dy);
    }
    const on = pickAt(x, y);
    const target = on && sel?.virtual && members(sel).includes(objects.indexOf(on)) ? sel : on;
    p.onDrop(item, Math.round(ux * 1e4) / 1e4, Math.round(uy * 1e4) / 1e4, target);
  };

  return (
    // the box takes the stage's free space; the canvas is the largest
    // width/height rectangle inside it, so the frame is never stretched
    <div className="canvas-box">
    <div className={`canvas ${stale ? "stale" : ""}`} ref={wrap}
      style={{ "--ar": `${width / height}` } as React.CSSProperties}
      onMouseDown={onDown}
      onDoubleClick={() => {
        // the first click of the two already selected the owner (a glyph picks its Text)
        const o = objects.find((x) => x.id === selected);
        if (o && p.onTextEdit && o.texts?.some((t) => t.editable)) p.onTextEdit(o);
      }}
      onMouseMove={onHover}
      onMouseLeave={() => setHover(null)}
      onDragOver={onDragOver}
      onDragLeave={() => { setDropAt(null); setHover(null); }}
      onDrop={onDrop}>
      {shown && <img ref={img} src={shown} alt="frame" draggable={false} />}
      <canvas ref={overlay} width={width} height={height} />
      {p.textEdit && p.onTextDone && (() => {
        const b = p.textEdit.box;
        const style: React.CSSProperties = b
          ? { left: `${(b[0] / width) * 100}%`, top: `${(b[3] / height) * 100}%`, minWidth: `${((b[2] - b[0]) / width) * 100}%` }
          : { left: "10%", top: "10%" };
        return <TextEditor key={p.textEdit.id} obj={p.textEdit} style={style} onDone={p.onTextDone} />;
      })()}
      {p.camera && !p.partPick && !p.textEdit && (
        <CameraGizmo cam={p.camera.cam} img={img} onCommit={p.camera.onCommit} onClose={p.camera.onClose} />
      )}
      {p.ghosts && p.ghosts.length > 0 && !drag && !p.partPick && !p.textEdit && (
        <TransformGhost ghosts={p.ghosts} frameW={frameW} frameH={frameH} onMatch={p.onMatch ?? null} />
      )}
      {p.partPick && p.glyphUrl && p.onPartDone && (
        <GlyphPicker key={p.glyphUrl} obj={p.partPick} url={p.glyphUrl} frameW={frameW} frameH={frameH} onDone={p.onPartDone} />
      )}
      {hover && !drag && <div className="hover-tag">{hover.name ?? hover.class}{hover.tier === 3 ? " 🔒" : ""}</div>}
      {failed ? <div className="frame-msg">⚠ This frame didn't render: {failed}</div>
        : slow ? <div className="frame-msg">Rendering this frame…</div> : null}
    </div>
    </div>
  );
}
