import { useEffect, useMemo, useRef, useState } from "react";
import type { Clip, SceneModel, SoundWave, VoiceLine } from "./types";
import type { Selection } from "./App";

interface Props {
  scene: SceneModel;
  file: string;
  rev: number;
  session?: string;
  f: number;
  fps: number;
  nFrames: number;
  sel: Selection;
  selectedObjectId: string | null;
  editable: boolean;
  onSeek: (f: number, rest: boolean) => void;
  onSelectClip: (clip: number, anim: number | null) => void;
  onTrim: (clip: number, anim: number | null, duration: number) => void;
  /** a timeline edit (edit.shift, edit.voice, ...): file, scene and rev are added by the app */
  onEdit: (msg: object) => Promise<any> | null;
  onBlocked: (why: string) => void;
}

const LABEL = 150;
const SNAP_PX = 7;

type Drag =
  | { kind: "trim"; clip: number; anim: number | null; x0: number; base: number; d: number }
  | { kind: "play"; clip: number; x0: number; dt: number; over: number | null; after: boolean; reorder: boolean; moved: boolean }
  | { kind: "anim"; clip: number; anim: number; x0: number; dt: number; split: boolean; moved: boolean }
  | { kind: "line"; line: number; x0: number; dt: number; moved: boolean }
  | { kind: "box"; x0: number; x1: number };

interface Picked { plays: number[]; lines: number[] }
type Pop = { kind: "line"; line: number } | { kind: "newline"; t: number } | { kind: "section"; index: number | null; t: number } | null;

function markersKey(file: string, scene: string) { return `studio.markers.${file}.${scene}`; }
function loadMarkers(file: string, scene: string): { t: number; name: string }[] {
  try { return JSON.parse(localStorage.getItem(markersKey(file, scene)) ?? "[]"); } catch { return []; }
}
function saveMarkers(file: string, scene: string, m: { t: number; name: string }[]) {
  try { localStorage.setItem(markersKey(file, scene), JSON.stringify(m)); } catch { /* private window */ }
}

/** The timeline, linked to code (code_spec.md §4.4). Rows: sections and
 * markers, play()/wait() groups, narration with its waveform, captions,
 * other sounds, then one row per animated object. Every gesture is an
 * intent; the server writes and verifies the code. */
export function Timeline(p: Props) {
  const { scene, f, fps, nFrames, sel, selectedObjectId, editable } = p;
  const lane = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [zoom, setZoom] = useState(1);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [ripple, setRipple] = useState(true);
  const [picked, setPicked] = useState<Picked>({ plays: [], lines: [] });
  const [pop, setPop] = useState<Pop>(null);
  const [waves, setWaves] = useState<SoundWave[]>([]);
  const [markers, setMarkers] = useState(() => loadMarkers(p.file, scene.name));
  const dur = Math.max(scene.duration, 1 / fps);
  const voice = scene.voice ?? [];
  const plays = scene.clips.filter((c) => c.kind === "play");

  useEffect(() => {
    const el = lane.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => { setMarkers(loadMarkers(p.file, scene.name)); }, [p.file, scene.name]);

  // narration waveforms for this revision
  useEffect(() => {
    if (!voice.length && !(scene.sounds ?? []).length) { setWaves([]); return; }
    let gone = false;
    fetch(`/audio/peaks?file=${encodeURIComponent(p.file)}&scene=${encodeURIComponent(scene.name)}&rev=${p.rev}`)
      .then((r) => (r.ok ? r.json() : { sounds: [] })).then((j) => { if (!gone) setWaves(j.sounds ?? []); })
      .catch(() => {});
    return () => { gone = true; };
  }, [p.file, scene.name, p.rev]); // eslint-disable-line react-hooks/exhaustive-deps

  // a new model ends any gesture planned against the old one
  useEffect(() => { setDrag(null); setPicked({ plays: [], lines: [] }); }, [scene]);

  const pps = Math.max(1e-3, ((width - LABEL - 12) / dur) * zoom);
  const x = (t: number) => LABEL + t * pps;

  // snapping: clip edges, line starts, markers, the playhead, sections
  const snapPoints = useMemo(() => {
    const s: number[] = [0, dur];
    for (const c of scene.clips) { s.push(c.start, c.start + c.duration); }
    for (const v of voice) s.push(v.start, v.start + v.duration);
    for (const m of markers) s.push(m.t);
    for (const sec of scene.sections ?? []) s.push(sec.start);
    return s;
  }, [scene, markers]); // eslint-disable-line react-hooks/exhaustive-deps
  const snapT = (t: number, free: boolean, skip: number[] = []) => {
    if (free) return Math.round(t * 100) / 100;
    let best = Math.round(t * 20) / 20, bestPx = SNAP_PX + 1;
    const pts = [...snapPoints.filter((q) => !skip.some((k) => Math.abs(k - q) < 1e-6)), f / fps];
    for (const q of pts) {
      const d = Math.abs(q - t) * pps;
      if (d < bestPx) { best = q; bestPx = d; }
    }
    return Math.round(best * 100) / 100;
  };

  // -- gestures ---------------------------------------------------------------------
  const dragRef = useRef(drag);
  dragRef.current = drag;
  const live = useRef({ pps, p, ripple, picked, scene, snapT });
  live.current = { pps, p, ripple, picked, scene, snapT };
  const dragging = !!drag;
  useEffect(() => {
    if (!dragging) return;
    const move = (e: MouseEvent) => {
      const d = dragRef.current;
      if (!d) return;
      if (e.buttons === 0) { setDrag(null); return; }
      const L = live.current;
      const raw = (e.clientX - (d.kind === "box" ? 0 : d.x0)) / L.pps;
      const free = e.ctrlKey || e.metaKey;
      if (d.kind === "trim") {
        setDrag({ ...d, d: Math.max(0.05, Math.round((d.base + raw) * 20) / 20) });
      } else if (d.kind === "box") {
        setDrag({ ...d, x1: e.clientX });
      } else if (d.kind === "play") {
        const c = L.scene.clips[d.clip];
        const dt = L.snapT(c.start + raw, free, [c.start]) - c.start;
        let over: number | null = null, after = false;
        if (e.altKey) {
          const t = c.start + raw;
          const hit = L.scene.clips.find((o) => o.kind === "play" && o.index !== d.clip && t >= o.start && t < o.start + Math.max(o.duration, 0.1));
          if (hit) { over = hit.index; after = t > hit.start + hit.duration / 2; }
        }
        setDrag({ ...d, dt, over, after, reorder: e.altKey, moved: d.moved || Math.abs(e.clientX - d.x0) > 3 });
      } else if (d.kind === "anim") {
        const c = L.scene.clips[d.clip];
        const a0 = c.start + (c.anims[d.anim].offset ?? 0);
        const dt = L.snapT(a0 + raw, free, [a0]) - a0;
        setDrag({ ...d, dt, split: e.altKey, moved: d.moved || Math.abs(e.clientX - d.x0) > 3 });
      } else if (d.kind === "line") {
        const v = (L.scene.voice ?? [])[d.line];
        const dt = L.snapT(v.start + raw, free, [v.start]) - v.start;
        setDrag({ ...d, dt, moved: d.moved || Math.abs(e.clientX - d.x0) > 3 });
      }
    };
    const up = () => {
      const d = dragRef.current;
      setDrag(null);
      if (!d) return;
      const L = live.current;
      const sc = L.scene;
      if (d.kind === "trim") {
        if (Math.abs(d.d - d.base) > 1e-6) L.p.onTrim(d.clip, d.anim, Number(d.d.toFixed(4)));
        return;
      }
      if (d.kind === "box") {
        const el = lane.current!;
        const r = el.getBoundingClientRect();
        const t0 = (Math.min(d.x0, d.x1) - r.left + el.scrollLeft - LABEL) / L.pps;
        const t1 = (Math.max(d.x0, d.x1) - r.left + el.scrollLeft - LABEL) / L.pps;
        const ps = sc.clips.filter((c) => c.kind === "play" && c.start < t1 && c.start + c.duration > t0).map((c) => c.play_index!);
        const ls = (sc.voice ?? []).filter((v) => v.start < t1 && v.start + v.duration > t0).map((v) => v.index);
        setPicked({ plays: ps, lines: ls });
        return;
      }
      if (!d.moved || (d.kind !== "play" || !d.reorder) && Math.abs(d.dt) < 0.5 / fps) return;
      if (!L.p.editable) { L.p.onBlocked("Pause and wait for the current edit first"); return; }
      if (d.kind === "play") {
        const c = sc.clips[d.clip];
        if (d.reorder) {
          if (d.over === null) { L.p.onBlocked("Alt-drag a group onto another group to swap their order"); return; }
          L.p.onEdit({ type: "edit.reorder", play: c.play_index, target: sc.clips[d.over].play_index, after: d.after });
          return;
        }
        const inSel = L.picked.plays.includes(c.play_index!);
        const ps = inSel ? L.picked.plays : [c.play_index!];
        const ls = inSel ? L.picked.lines : [];
        L.p.onEdit({ type: "edit.shift", plays: ps, lines: ls, dt: Number(d.dt.toFixed(2)), ripple: L.ripple });
      } else if (d.kind === "anim") {
        const c = sc.clips[d.clip];
        const off = c.anims[d.anim].offset ?? 0;
        const t = c.start + off + d.dt;
        if (d.split) {
          L.p.onEdit({ type: "edit.split", clip: c.index, anim: d.anim, t: Number(t.toFixed(2)) });
        } else if (t < c.start - 1e-6) {
          const into = sc.clips.find((o) => o.kind === "play" && o.index < c.index && t >= o.start - 1e-6 && t < o.start + o.duration);
          if (!into) { L.p.onBlocked("A clip can't start before its group. Drop it on an earlier group to overlap them, or move the group"); return; }
          L.p.onEdit({ type: "edit.merge", clip: c.index, anim: d.anim, into: into.index, start: Number((t - into.start).toFixed(2)) });
        } else {
          L.p.onEdit({ type: "edit.offset", clip: c.index, anim: d.anim, start: Number((off + d.dt).toFixed(2)) });
        }
      } else if (d.kind === "line") {
        const v = (sc.voice ?? [])[d.line];
        if (!v.movable) { L.p.onBlocked(v.lock ?? "This line can't be moved on the timeline"); return; }
        const inSel = L.picked.lines.includes(v.index);
        L.p.onEdit({ type: "edit.shift", plays: inSel ? L.picked.plays : [], lines: inSel ? L.picked.lines : [v.index],
          dt: Number(d.dt.toFixed(2)), ripple: L.ripple });
      }
    };
    const cancel = () => setDrag(null);
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopImmediatePropagation(); cancel(); } };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    window.addEventListener("blur", cancel);
    window.addEventListener("keydown", key, true);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("blur", cancel);
      window.removeEventListener("keydown", key, true);
    };
  }, [dragging]); // eslint-disable-line react-hooks/exhaustive-deps

  // R toggles ripple, M drops a marker at the playhead (when no field has focus)
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const tag = (document.activeElement?.tagName ?? "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (e.key === "r" || e.key === "R") setRipple((v) => !v);
      else if (e.key === "m" || e.key === "M") addMarker();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  });

  const addMarker = () => {
    const t = Math.round((f / fps) * 100) / 100;
    if (markers.some((m) => Math.abs(m.t - t) < 1e-6)) return;
    const next = [...markers, { t, name: `M${markers.length + 1}` }].sort((a, b) => a.t - b.t);
    setMarkers(next);
    saveMarkers(p.file, scene.name, next);
  };
  const dropMarker = (t: number) => {
    const next = markers.filter((m) => m.t !== t);
    setMarkers(next);
    saveMarkers(p.file, scene.name, next);
  };

  const scrubFrom = (e: React.MouseEvent) => {
    const el = lane.current!;
    if (e.shiftKey) { setDrag({ kind: "box", x0: e.clientX, x1: e.clientX }); return; }
    if (picked.plays.length || picked.lines.length) setPicked({ plays: [], lines: [] });
    const r = el.getBoundingClientRect();
    const at = (cx: number) => ((cx - r.left + el.scrollLeft - LABEL) / pps) * fps;
    p.onSeek(at(e.clientX), false);
    const mv = (ev: MouseEvent) => p.onSeek(at(ev.clientX), false);
    const stop = () => {
      window.removeEventListener("mousemove", mv);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("blur", stop);
    };
    const up = (ev: MouseEvent) => { p.onSeek(at(ev.clientX), true); stop(); };
    window.addEventListener("mousemove", mv);
    window.addEventListener("mouseup", up);
    window.addEventListener("blur", stop);
  };

  const togglePick = (kind: "plays" | "lines", i: number) =>
    setPicked((pk) => ({ ...pk, [kind]: pk[kind].includes(i) ? pk[kind].filter((k) => k !== i) : [...pk[kind], i] }));

  const ticks: number[] = [];
  const step = pps > 120 ? 0.5 : pps > 40 ? 1 : pps > 15 ? 2 : 5;
  for (let t = 0; t <= dur + 1e-9; t += step) ticks.push(t);

  const isSel = (clip: number, anim: number | null) => sel?.kind === "clip" && sel.clip === clip && sel.anim === anim;
  const lockOf = (c: Clip) => !!c.lock || c.tier === 3;
  const trimHandle = (clip: number, anim: number | null, base: number, locked: boolean) =>
    locked ? null : (
      <span className="trim" title="Drag to change the length"
        onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setDrag({ kind: "trim", clip, anim, x0: e.clientX, base, d: base }); }} />
    );

  const shiftOf = (c: Clip) => {
    if (!drag || drag.kind !== "play" || !drag.moved) return 0;
    if (!drag.reorder) {
      const ps = picked.plays.includes(scene.clips[drag.clip].play_index!) ? picked.plays : [scene.clips[drag.clip].play_index];
      if (ps.includes(c.play_index)) return drag.dt;
    }
    return 0;
  };
  const lineShift = (v: VoiceLine) => {
    if (!drag || (drag.kind !== "play" && drag.kind !== "line") || !drag.moved) return 0;
    if (drag.kind === "line" && (drag.line === v.index || (picked.lines.includes(drag.line) && picked.lines.includes(v.index)))) return drag.dt;
    if (drag.kind === "play" && !drag.reorder && picked.plays.includes(scene.clips[drag.clip].play_index!) && picked.lines.includes(v.index)) return drag.dt;
    return 0;
  };

  const inner = LABEL + dur * pps + 20;
  const t0 = f / fps;
  const wavesFor = (v: VoiceLine) => waves.find((w) => Math.abs(w.start - v.start) < 0.02);
  const otherWaves = waves.filter((w) => !voice.some((v) => Math.abs(w.start - v.start) < 0.02));
  const canNarrate = !!scene.timed;
  const box = drag?.kind === "box" ? drag : null;

  return (
    <div className="timeline">
      <div className="tl-tools">
        <label className="chk" title="R: moving a group also moves every later at() and TARGET">
          <input type="checkbox" checked={ripple} onChange={(e) => setRipple(e.target.checked)} /> ripple
        </label>
        <button disabled={!editable || !canNarrate} title={canNarrate ? "Add a narration line at the playhead" : "Narration lines need a TimedScene"}
          onClick={() => setPop({ kind: "newline", t: Math.round(t0 * 100) / 100 })}>＋ line</button>
        <button disabled={!editable} title="Start a section (self.next_section) at the playhead"
          onClick={() => setPop({ kind: "section", index: null, t: Math.round(t0 * 100) / 100 })}>＋ section</button>
        <button title="M: a marker at the playhead (kept in this browser, not in the file)" onClick={addMarker}>＋ marker</button>
        {(picked.plays.length + picked.lines.length) > 0 && (
          <span className="muted">{picked.plays.length + picked.lines.length} selected · drag one to move them all</span>
        )}
        <span className="grow" />
        <span className="muted hint">drag = move · edge = trim · Alt-drag = swap / split · Shift-drag = select · Ctrl = no snap</span>
        <label className="muted">zoom <input type="range" min={1} max={8} step={0.25} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label>
      </div>
      {pop && <PopEditor pop={pop} scene={scene} editable={editable} onClose={() => setPop(null)}
        onEdit={(m) => { const r = p.onEdit(m); if (r) r.then((x) => { if (x?.type === "edit.done") setPop(null); }); }} />}
      <div className="tl-scroll" ref={lane}>
        <div style={{ width: Math.max(inner, width - 2), position: "relative" }}>
          <div className="ruler" onMouseDown={scrubFrom}>
            {ticks.map((t) => <span key={t} style={{ left: x(t) }}>{t.toFixed(step < 1 ? 1 : 0)}s</span>)}
            {(scene.sections ?? []).map((s) => (
              <span key={`s${s.index}`} className="section-flag" style={{ left: x(s.start) }} title={`section ${s.name} · line ${s.line}\nclick to rename`}
                onMouseDown={(e) => { e.stopPropagation(); setPop({ kind: "section", index: s.index, t: s.start }); }}>§ {s.name}</span>
            ))}
            {markers.map((m) => (
              <span key={`m${m.t}`} className="marker" style={{ left: x(m.t) }} title={`${m.name} at ${m.t.toFixed(2)} s\ndouble-click to remove`}
                onMouseDown={(e) => { e.stopPropagation(); p.onSeek(m.t * fps, true); }}
                onDoubleClick={(e) => { e.stopPropagation(); dropMarker(m.t); }}>▾</span>
            ))}
          </div>
          {(scene.sections ?? []).map((s, i, all) => (
            <div key={`band${s.index}`} className="section-band" style={{ left: x(s.start), width: ((all[i + 1]?.start ?? dur) - s.start) * pps }} />
          ))}

          <div className="track">
            <div className="tname">play / wait</div>
            <div className="lane" onMouseDown={scrubFrom}>
              {scene.clips.map((c) => {
                const d = drag?.kind === "trim" && drag.clip === c.index && drag.anim === null ? drag.d : c.duration;
                const locked = lockOf(c);
                const label = c.kind === "wait"
                  ? (c.call_name === "at" ? `at → ${(c.start + d).toFixed(2)}` : `wait ${d.toFixed(2)}`)
                  : (c.anims.map((a) => a.class.replace("_MethodAnimation", ".animate")).join(" · "));
                const pk = c.kind === "play" && picked.plays.includes(c.play_index!);
                const target = drag?.kind === "play" && drag.reorder && drag.over === c.index;
                return (
                  <div key={c.index}
                    className={`clip ${c.kind} ${locked ? "locked" : ""} ${isSel(c.index, null) ? "sel" : ""} ${pk ? "picked" : ""} ${target ? (drag.after ? "drop-after" : "drop-before") : ""}`}
                    style={{ left: x(c.start + shiftOf(c)) - LABEL, width: Math.max(3, d * pps - 2) }}
                    title={`${c.text ?? ""}\nline ${c.line ?? "?"}${c.lock ? `\n🔒 ${c.lock}` : ""}`}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      if (c.kind === "play" && (e.shiftKey || e.ctrlKey || e.metaKey)) { togglePick("plays", c.play_index!); return; }
                      p.onSelectClip(c.index, null);
                      p.onSeek(c.start * fps, true);
                      if (c.kind === "play")
                        setDrag({ kind: "play", clip: c.index, x0: e.clientX, dt: 0, over: null, after: false, reorder: e.altKey, moved: false });
                    }}>
                    {locked && <span className="lock">🔒</span>}{label}
                    {trimHandle(c.index, null, c.duration, locked)}
                  </div>
                );
              })}
            </div>
          </div>

          {voice.length > 0 && (
            <div className="track voice-track">
              <div className="tname">narration</div>
              <div className="lane" onMouseDown={scrubFrom}>
                {voice.map((v) => {
                  const w = wavesFor(v);
                  const sh = lineShift(v);
                  const pk = picked.lines.includes(v.index);
                  return (
                    <div key={v.index} className={`clip voice ${v.movable ? "" : "locked"} ${pk ? "picked" : ""} ${pop?.kind === "line" && pop.line === v.index ? "sel" : ""}`}
                      style={{ left: x(v.start + sh) - LABEL, width: Math.max(4, v.duration * pps - 2) }}
                      title={`“${v.text}”\nline ${v.line ?? "?"} · ${v.start.toFixed(2)}–${(v.start + v.duration).toFixed(2)} s${v.lock ? `\n🔒 ${v.lock}` : ""}\ndouble-click to edit`}
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        if (e.shiftKey || e.ctrlKey || e.metaKey) { togglePick("lines", v.index); return; }
                        p.onSeek(v.start * fps, true);
                        setDrag({ kind: "line", line: v.index, x0: e.clientX, dt: 0, moved: false });
                      }}
                      onDoubleClick={(e) => { e.stopPropagation(); setPop({ kind: "line", line: v.index }); }}>
                      {w && <Wave peaks={w.peaks} width={Math.max(4, v.duration * pps - 2)} />}
                      <span className="vtext">{v.warnings.length ? "⚠ " : ""}{v.text.replace(/<bookmark[^>]*\/>/g, "")}</span>
                      {v.bookmarks.map((b) => (
                        <span key={b.name} className="bookmark" style={{ left: (b.t - v.start) * pps }} title={`bookmark ${b.name}`} />
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {(scene.captions ?? []).length > 0 && (
            <div className="track caption-track">
              <div className="tname">captions{scene.burned_captions ? " (in frame)" : " (.srt)"}</div>
              <div className="lane" onMouseDown={scrubFrom}>
                {(scene.captions ?? []).map((c, i) => {
                  const v = c.line !== null ? voice[c.line] : undefined;
                  const warn = v?.warnings.length ? v.warnings.join("; ") : "";
                  return (
                    <div key={i} className={`clip caption ${warn ? "warn" : ""}`}
                      style={{ left: x(c.start + (v ? lineShift(v) : 0)) - LABEL, width: Math.max(4, (c.end - c.start) * pps - 2) }}
                      title={`${c.text}${warn ? `\n⚠ ${warn}` : ""}\ndouble-click to edit`}
                      onMouseDown={(e) => { e.stopPropagation(); p.onSeek(c.start * fps, true); }}
                      onDoubleClick={(e) => { e.stopPropagation(); if (v) setPop({ kind: "line", line: v.index }); }}>
                      {c.text}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {otherWaves.length > 0 && (
            <div className="track">
              <div className="tname">sounds</div>
              <div className="lane" onMouseDown={scrubFrom}>
                {otherWaves.map((w, i) => (
                  <div key={i} className="clip sound locked" style={{ left: x(w.start) - LABEL, width: Math.max(4, w.duration * pps - 2) }}
                    title={`${w.file.split(/[\\/]/).pop()} · ${w.start.toFixed(2)} s`}>
                    <Wave peaks={w.peaks} width={Math.max(4, w.duration * pps - 2)} />
                    <span className="vtext">{w.file.split(/[\\/]/).pop()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {scene.rows.map((row, ri) => (
            <div className={`track ${row.id && row.id === selectedObjectId ? "hi" : ""}`} key={ri}>
              <div className="tname" title={row.id ?? ""}>{row.label}</div>
              <div className="lane" onMouseDown={scrubFrom}>
                {row.clips.map(({ clip, anim }) => {
                  const c = scene.clips[clip];
                  const a = c.anims[anim];
                  const off = a.offset ?? 0;
                  const own = drag?.kind === "trim" && drag.clip === clip && drag.anim === anim ? drag.d : Math.min(a.run_time, c.duration);
                  const multi = c.anims.length > 1;
                  const locked = lockOf(c);
                  const dx = drag?.kind === "anim" && drag.clip === clip && drag.anim === anim && drag.moved ? drag.dt : shiftOf(c);
                  return (
                    <div key={`${clip}-${anim}`}
                      className={`clip anim ${locked ? "locked" : ""} ${isSel(clip, multi ? anim : null) ? "sel" : ""} ${drag?.kind === "anim" && drag.clip === clip && drag.anim === anim && drag.split ? "splitting" : ""}`}
                      style={{ left: x(c.start + off + dx) - LABEL, width: Math.max(3, own * pps - 2) }}
                      title={`${a.class} · ${a.run_time.toFixed(2)} s · ${a.rate_func}${off ? ` · +${off.toFixed(2)} s in its group` : ""}\nline ${c.line}`}
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        p.onSelectClip(clip, multi ? anim : null);
                        p.onSeek((c.start + off) * fps, true);
                        if (!locked) setDrag({ kind: "anim", clip, anim, x0: e.clientX, dt: 0, split: e.altKey, moved: false });
                      }}>
                      {a.class.replace("_MethodAnimation", ".animate")}
                      {trimHandle(clip, multi ? anim : null, multi ? a.run_time : c.duration, locked)}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          {box && (() => {
            const el = lane.current;
            const r = el?.getBoundingClientRect();
            if (!el || !r) return null;
            const a = Math.min(box.x0, box.x1) - r.left + el.scrollLeft, b = Math.max(box.x0, box.x1) - r.left + el.scrollLeft;
            return <div className="boxsel" style={{ left: a, width: b - a }} />;
          })()}
          <div className="playhead" style={{ left: x(Math.min(f, nFrames - 1) / fps) }} />
        </div>
      </div>
    </div>
  );
}

function Wave({ peaks, width }: { peaks: number[]; width: number }) {
  const h = 16;
  const n = peaks.length;
  if (!n) return null;
  let d = "";
  const cols = Math.max(1, Math.floor(width));
  for (let i = 0; i < cols; i++) {
    const a = Math.floor((i / cols) * n), b = Math.max(a + 1, Math.floor(((i + 1) / cols) * n));
    let m = 0;
    for (let k = a; k < b && k < n; k++) m = Math.max(m, peaks[k]);
    const y = Math.max(0.5, Math.min(1, m * 1.6) * (h / 2));
    d += `M${i + 0.5},${h / 2 - y}V${h / 2 + y}`;
  }
  return <svg className="wave" width={width} height={h} viewBox={`0 0 ${width} ${h}`}><path d={d} /></svg>;
}

/** Small editors that open over the timeline: a narration line, a new line, a section. */
function PopEditor({ pop, scene, editable, onClose, onEdit }: {
  pop: NonNullable<Pop>; scene: SceneModel; editable: boolean; onClose: () => void; onEdit: (m: object) => void;
}) {
  const v = pop.kind === "line" ? (scene.voice ?? [])[pop.line] : undefined;
  const sec = pop.kind === "section" && pop.index !== null ? (scene.sections ?? [])[pop.index] : undefined;
  const [text, setText] = useState(v?.text ?? "");
  const [cap, setCap] = useState(v?.caption ?? "");
  const [name, setName] = useState(sec?.name ?? "");
  useEffect(() => { setText(v?.text ?? ""); setCap(v?.caption ?? ""); setName(sec?.name ?? ""); }, [v?.text, v?.caption, sec?.name]);
  const keys = (e: React.KeyboardEvent, go: () => void) => {
    if (e.key === "Escape") { e.stopPropagation(); onClose(); }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); }
  };
  if (pop.kind === "line" && !v) return null;
  const capLen = (cap || text).length;
  return (
    <div className="tl-pop" role="dialog">
      {pop.kind === "line" && v && (
        <>
          <div className="pop-head">Narration · line {v.line} · {v.start.toFixed(2)} s · {v.duration.toFixed(2)} s spoken
            {v.kind === "voiceover" ? " · voiceover() (words only)" : ""}</div>
          {v.lock && <div className="note">🔒 {v.lock}</div>}
          <label>Spoken <span className="muted">(sent to Edge TTS when changed)</span></label>
          <textarea rows={2} value={text} disabled={!editable || !!v.lock} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => keys(e, () => text.trim() !== v.text && onEdit({ type: "edit.voice", action: "text", line: v.index, value: text }))} />
          <label>Caption <span className={capLen > 70 ? "bad" : "muted"}>({capLen}/70; empty = the spoken text)</span></label>
          <input value={cap} disabled={!editable || !!v.lock} placeholder={v.text.replace(/<bookmark[^>]*\/>/g, "")}
            onChange={(e) => setCap(e.target.value)}
            onKeyDown={(e) => keys(e, () => onEdit({ type: "edit.voice", action: "caption", line: v.index, value: cap || null }))} />
          {v.warnings.map((w) => <div key={w} className="note">⚠ {w}</div>)}
          <div className="btns-row">
            <button onClick={onClose}>Close</button>
            <button disabled={!editable || !!v.lock} onClick={() => onEdit({ type: "edit.voice", action: "delete", line: v.index })}
              title="Removes the narration; the clips inside its with block stay">Delete line</button>
            <button disabled={!editable || !!v.lock || (cap || null) === (v.caption || null)}
              onClick={() => onEdit({ type: "edit.voice", action: "caption", line: v.index, value: cap || null })}>Set caption</button>
            <button className="pri" disabled={!editable || !!v.lock || !text.trim() || text.trim() === v.text}
              onClick={() => onEdit({ type: "edit.voice", action: "text", line: v.index, value: text })}>Change words</button>
          </div>
        </>
      )}
      {pop.kind === "newline" && (
        <>
          <div className="pop-head">New narration line at {pop.t.toFixed(2)} s <span className="muted">(self.line(...); the words go to Edge TTS)</span></div>
          <textarea rows={2} autoFocus value={text} onChange={(e) => setText(e.target.value)} placeholder="What the narrator says"
            onKeyDown={(e) => keys(e, () => text.trim() && onEdit({ type: "edit.voice", action: "add", t: pop.t, value: text }))} />
          <div className="btns-row">
            <button onClick={onClose}>Cancel</button>
            <button className="pri" disabled={!editable || !text.trim()} onClick={() => onEdit({ type: "edit.voice", action: "add", t: pop.t, value: text })}>Add line</button>
          </div>
        </>
      )}
      {pop.kind === "section" && (
        <>
          <div className="pop-head">{sec ? `Section at ${sec.start.toFixed(2)} s · line ${sec.line}` : `New section at ${pop.t.toFixed(2)} s`}
            <span className="muted"> (self.next_section)</span></div>
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Section name"
            onKeyDown={(e) => keys(e, () => name.trim() && onEdit(sec ? { type: "edit.section", action: "rename", section: sec.index, name }
              : { type: "edit.section", action: "add", t: pop.t, name }))} />
          <div className="btns-row">
            <button onClick={onClose}>Cancel</button>
            {sec && <button disabled={!editable} onClick={() => onEdit({ type: "edit.section", action: "delete", section: sec.index })}>Delete section</button>}
            <button className="pri" disabled={!editable || !name.trim() || name === sec?.name}
              onClick={() => onEdit(sec ? { type: "edit.section", action: "rename", section: sec.index, name } : { type: "edit.section", action: "add", t: pop.t, name })}>
              {sec ? "Rename" : "Add section"}</button>
          </div>
        </>
      )}
    </div>
  );
}
