import { useEffect, useRef, useState } from "react";
import type { SceneModel } from "./types";
import type { Selection } from "./App";

interface Props {
  scene: SceneModel;
  f: number;
  fps: number;
  nFrames: number;
  sel: Selection;
  selectedObjectId: string | null;
  onSeek: (f: number, rest: boolean) => void;
  onSelectClip: (clip: number, anim: number | null) => void;
  onTrim: (clip: number, anim: number | null, duration: number) => void;
}

const LABEL = 150;

/** Clips linked to code. Top row: every play()/wait() in order. Below: one
 * row per animated object. Drag a clip's right edge to change its length:
 * that writes run_time / the wait / the at() time (code_spec.md §4.4). */
export function Timeline({ scene, f, fps, nFrames, sel, selectedObjectId, onSeek, onSelectClip, onTrim }: Props) {
  const lane = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [zoom, setZoom] = useState(1);
  const [trim, setTrim] = useState<{ clip: number; anim: number | null; start: number; base: number; d: number } | null>(null);
  const dur = Math.max(scene.duration, 1 / fps);

  useEffect(() => {
    const el = lane.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pps = Math.max(1e-3, ((width - LABEL - 12) / dur) * zoom); // pixels per second
  const x = (t: number) => LABEL + t * pps;
  const snap = (t: number) => Math.max(0.05, Math.round(t * 20) / 20); // clean numbers in the code

  // trimming with the mouse. The latest trim, pps and onTrim live in refs,
  // so a model update mid-drag never sends an edit against an old state.
  const trimRef = useRef(trim);
  trimRef.current = trim;
  const live = useRef({ pps, onTrim });
  live.current = { pps, onTrim };
  const dragging = !!trim;
  useEffect(() => {
    if (!dragging) return;
    const move = (e: MouseEvent) => {
      const tr = trimRef.current;
      if (tr) setTrim({ ...tr, d: snap(tr.base + (e.clientX - tr.start) / live.current.pps) });
    };
    const up = () => {
      const tr = trimRef.current;
      setTrim(null);
      if (tr && Math.abs(tr.d - tr.base) > 1e-6) live.current.onTrim(tr.clip, tr.anim, Number(tr.d.toFixed(4)));
    };
    const cancel = () => setTrim(null);  // left the window mid-drag: don't commit later by surprise
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") cancel(); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    window.addEventListener("blur", cancel);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("blur", cancel);
      window.removeEventListener("keydown", key);
    };
  }, [dragging]); // eslint-disable-line react-hooks/exhaustive-deps

  // a new model (edit, reload) ends any drag that was based on the old one
  useEffect(() => { setTrim(null); }, [scene]);

  const scrubFrom = (e: React.MouseEvent) => {
    const el = lane.current!;
    const r = el.getBoundingClientRect();
    const at = (cx: number) => ((cx - r.left + el.scrollLeft - LABEL) / pps) * fps;
    onSeek(at(e.clientX), false);
    const move = (ev: MouseEvent) => onSeek(at(ev.clientX), false);
    const stop = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      window.removeEventListener("blur", stop);
    };
    const up = (ev: MouseEvent) => {
      onSeek(at(ev.clientX), true);
      stop();
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    window.addEventListener("blur", stop);
  };

  const ticks: number[] = [];
  const step = pps > 120 ? 0.5 : pps > 40 ? 1 : pps > 15 ? 2 : 5;
  for (let t = 0; t <= dur + 1e-9; t += step) ticks.push(t);

  const isSel = (clip: number, anim: number | null) =>
    sel?.kind === "clip" && sel.clip === clip && sel.anim === anim;

  const handle = (clip: number, anim: number | null, base: number, locked: boolean) =>
    locked ? null : (
      <span className="trim" title="Drag to change the length"
        onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setTrim({ clip, anim, start: e.clientX, base, d: base }); }} />
    );

  const inner = LABEL + dur * pps + 20;

  return (
    <div className="timeline">
      <div className="tl-tools">
        <span className="muted">Timeline · drag a clip's right edge to retime it · click a clip to inspect it</span>
        <span className="grow" />
        <label className="muted">zoom <input type="range" min={1} max={8} step={0.25} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label>
      </div>
      <div className="tl-scroll" ref={lane}>
        <div style={{ width: Math.max(inner, width - 2), position: "relative" }}>
          <div className="ruler" onMouseDown={scrubFrom}>
            {ticks.map((t) => <span key={t} style={{ left: x(t) }}>{t.toFixed(step < 1 ? 1 : 0)}s</span>)}
          </div>
          <div className="track">
            <div className="tname">play / wait</div>
            <div className="lane" onMouseDown={scrubFrom}>
              {scene.clips.map((c) => {
                const d = trim && trim.clip === c.index && trim.anim === null ? trim.d : c.duration;
                const locked = !!c.lock || c.tier === 3;
                const label = c.kind === "wait"
                  ? (c.call_name === "at" ? `at → ${(c.start + d).toFixed(2)}` : `wait ${d.toFixed(2)}`)
                  : (c.anims.map((a) => a.class.replace("_MethodAnimation", ".animate")).join(" · "));
                return (
                  <div key={c.index}
                    className={`clip ${c.kind} ${locked ? "locked" : ""} ${isSel(c.index, null) ? "sel" : ""}`}
                    style={{ left: x(c.start) - LABEL, width: Math.max(3, d * pps - 2) }}
                    title={`${c.text ?? ""}\nline ${c.line ?? "?"}${c.lock ? `\n🔒 ${c.lock}` : ""}`}
                    onMouseDown={(e) => { e.stopPropagation(); onSelectClip(c.index, null); onSeek(c.start * fps, true); }}>
                    {locked && <span className="lock">🔒</span>}{label}
                    {handle(c.index, null, c.duration, locked)}
                  </div>
                );
              })}
            </div>
          </div>
          {scene.rows.map((row, ri) => (
            <div className={`track ${row.id && row.id === selectedObjectId ? "hi" : ""}`} key={ri}>
              <div className="tname" title={row.id ?? ""}>{row.label}</div>
              <div className="lane" onMouseDown={scrubFrom}>
                {row.clips.map(({ clip, anim }) => {
                  const c = scene.clips[clip];
                  const a = c.anims[anim];
                  const own = trim && trim.clip === clip && trim.anim === anim ? trim.d : Math.min(a.run_time, c.duration);
                  const multi = c.anims.length > 1;
                  const locked = !!c.lock || c.tier === 3 || (multi && !!c.play_runtime);
                  return (
                    <div key={`${clip}-${anim}`}
                      className={`clip anim ${locked ? "locked" : ""} ${isSel(clip, multi ? anim : null) ? "sel" : ""}`}
                      style={{ left: x(c.start) - LABEL, width: Math.max(3, own * pps - 2) }}
                      title={`${a.class} · ${a.run_time.toFixed(2)} s · ${a.rate_func}\nline ${c.line}`}
                      onMouseDown={(e) => { e.stopPropagation(); onSelectClip(clip, multi ? anim : null); onSeek(c.start * fps, true); }}>
                      {a.class.replace("_MethodAnimation", ".animate")}
                      {handle(clip, multi ? anim : null, multi ? a.run_time : c.duration, locked)}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          <div className="playhead" style={{ left: x(Math.min(f, nFrames - 1) / fps) }} />
        </div>
      </div>
    </div>
  );
}
