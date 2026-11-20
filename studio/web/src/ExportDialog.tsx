// Export dialog (Phase 6 step 5): real renders with plain Manim, run by the
// server one scene at a time under the render lock; optional join and
// narration check. Jobs keep running when the dialog closes.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Conn } from "./api";

export interface ExportScene { name: string; state: string; out: string | null; s: number | null; pct: number | null; anim?: number }
export interface ExportJob {
  id: string; file: string; state: string; message: string; log: string;
  spec: { scenes: string[]; quality: string; format: string; transparent: boolean; join: boolean; check: boolean };
  scenes: ExportScene[]; joined: string | null; check: { ok: boolean; report: string } | null;
  started: number; finished: number | null;
}

const QUALITIES: [string, string][] = [["l", "Low · 480p15 (drafts)"], ["m", "Medium · 720p30"], ["h", "High · 1080p60"], ["k", "4K · 2160p60"]];
const FORMATS: [string, string][] = [["mp4", "MP4 video"], ["webm", "WebM video"], ["gif", "GIF"], ["mov", "MOV (ProRes)"], ["png", "PNG frames"]];
export const RUNNING = new Set(["queued", "waiting", "rendering", "joining", "checking"]);

interface Choice { which: "this" | "all" | "pick"; picked: string[]; quality: string; format: string; transparent: boolean; join: boolean; check: boolean }
const DEFAULT: Choice = { which: "all", picked: [], quality: "l", format: "mp4", transparent: false, join: true, check: true };

function load(file: string): Choice {
  try {
    const v = JSON.parse(localStorage.getItem("studio.export." + file) ?? "null");
    return v && typeof v === "object" ? { ...DEFAULT, ...v } : DEFAULT;
  } catch { return DEFAULT; }
}
function save(file: string, c: Choice) {
  try { localStorage.setItem("studio.export." + file, JSON.stringify(c)); } catch { /* private window */ }
}

export function jobLine(j: ExportJob): string {
  const done = j.scenes.filter((s) => s.state === "done").length;
  const cur = j.scenes.find((s) => s.state === "rendering");
  if (j.state === "rendering") return `rendering ${done + 1}/${j.scenes.length}${cur ? ` · ${cur.name}${cur.anim != null ? ` · animation ${cur.anim + 1}` : ""}` : ""}`;
  if (j.state === "waiting") return j.message || "waiting for another render of this file";
  if (j.state === "joining") return "joining the scenes…";
  if (j.state === "checking") return "checking the narration…";
  if (j.state === "done") return j.message || `done · ${done} scene${done === 1 ? "" : "s"}${j.joined ? " · joined" : ""}`;
  return j.message || j.state;
}

export function ExportDialog({ conn, file, scenes, active, jobs, onClose }: {
  conn: Conn; file: string; scenes: string[]; active: string | null; jobs: ExportJob[]; onClose: () => void;
}) {
  const [c, setC] = useState<Choice>(() => load(file));
  const [error, setError] = useState<string | null>(null);
  // the server opens Explorer on its own machine (refused for pages from another one)
  const reveal = (job: string, i: number) => { conn.send({ type: "export.reveal", id: job, i }); };
  const [playing, setPlaying] = useState<{ job: string; i: number; name: string; gif: boolean } | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => { boxRef.current?.focus(); }, []);
  useEffect(() => { save(file, c); }, [file, c]);

  const chosen = useMemo(() => {
    if (c.which === "this") return active ? [active] : [];
    if (c.which === "all") return scenes;
    return scenes.filter((s) => c.picked.includes(s));  // file order, whatever the clicking order
  }, [c, scenes, active]);
  const set = (p: Partial<Choice>) => setC((x) => ({ ...x, ...p }));
  const canJoin = c.format === "mp4" && !c.transparent && chosen.length > 1;
  const canCheck = c.format === "mp4" && !c.transparent;
  const mine = jobs.filter((j) => j.file === file).slice().reverse();
  const running = mine.some((j) => RUNNING.has(j.state));
  // CLAUDE.md: high quality only after the low-quality render of the same scenes has been looked at
  const draftDone = mine.some((j) => j.state === "done" && j.spec.quality === "l" && chosen.every((s) => j.spec.scenes.includes(s)));
  const highFirst = (c.quality === "h" || c.quality === "k") && !draftDone;

  const start = () => {
    setError(null);
    conn.request({ type: "export.start", file, spec: { scenes: chosen, quality: c.quality, format: c.format,
      transparent: c.transparent, join: canJoin && c.join, check: canCheck && c.check } })
      .then((r) => { if (r.type === "error") setError(r.message); });
  };

  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal export" ref={boxRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Export"
        onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}>
        <h4>Export {file}</h4>
        <p className="note muted">Rendered by plain Manim, exactly as on the command line. Keeps running if you close this.</p>
        <div className="export-grid">
          <label>Scenes</label>
          <div>
            <label className="opt"><input type="radio" checked={c.which === "all"} onChange={() => set({ which: "all" })} /> All ({scenes.length}, in render order)</label>
            <label className="opt"><input type="radio" checked={c.which === "this"} onChange={() => set({ which: "this" })} disabled={!active} /> This scene{active ? ` (${active})` : ""}</label>
            <label className="opt"><input type="radio" checked={c.which === "pick"} onChange={() => set({ which: "pick" })} /> Choose…</label>
            {c.which === "pick" && (
              <div className="export-pick">
                {scenes.map((s) => (
                  <label key={s} className="opt"><input type="checkbox" checked={c.picked.includes(s)}
                    onChange={(e) => set({ picked: e.target.checked ? [...c.picked, s] : c.picked.filter((x) => x !== s) })} /> {s}</label>
                ))}
              </div>
            )}
          </div>
          <label htmlFor="ex-q">Quality</label>
          <select id="ex-q" value={c.quality} onChange={(e) => set({ quality: e.target.value })}>
            {QUALITIES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          <label htmlFor="ex-f">Format</label>
          <div>
            <select id="ex-f" value={c.format} onChange={(e) => set({ format: e.target.value })}>
              {FORMATS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
            {["mov", "webm", "png"].includes(c.format) && (
              <label className="opt"><input type="checkbox" checked={c.transparent} onChange={(e) => set({ transparent: e.target.checked })} /> Transparent background</label>
            )}
          </div>
          <label>After</label>
          <div>
            <label className={`opt ${canJoin ? "" : "muted"}`} title={canJoin ? "" : "Joining needs two or more scenes as MP4 without transparency"}>
              <input type="checkbox" disabled={!canJoin} checked={canJoin && c.join} onChange={(e) => set({ join: e.target.checked })} /> Join into one video (audio as one track)</label>
            <label className={`opt ${canCheck ? "" : "muted"}`}>
              <input type="checkbox" disabled={!canCheck} checked={canCheck && c.check} onChange={(e) => set({ check: e.target.checked })} /> Check the narration is in the file</label>
          </div>
        </div>
        {highFirst && <p className="note warn">Render the low-quality version of these scenes and look at it before a high-quality render: it takes much longer.</p>}
        {error && <p className="note bad">{error}</p>}
        <div className="btns">
          <button onClick={onClose}>Close</button>
          <button className="pri" disabled={!chosen.length} onClick={start}>
            {running ? "Queue export" : highFirst ? "Export anyway" : "Export"}{chosen.length ? ` ${chosen.length} scene${chosen.length === 1 ? "" : "s"}` : ""}
          </button>
        </div>

        {mine.length > 0 && <h4 className="export-h">Exports</h4>}
        <div className="export-jobs">
          {mine.map((j) => (
            <div key={j.id} className={`export-job ${j.state}`}>
              <div className="row">
                <strong>{j.spec.quality.toUpperCase()} · {j.spec.format}</strong>
                <span className="grow">{jobLine(j)}</span>
                {RUNNING.has(j.state) && <button onClick={() => conn.request({ type: "export.cancel", id: j.id })}>Cancel</button>}
              </div>
              {RUNNING.has(j.state) && (
                <progress max={j.scenes.length} value={j.scenes.filter((s) => s.state === "done").length} />
              )}
              <ul>
                {j.scenes.map((s, i) => (
                  <li key={s.name} className={s.state}>
                    {s.name} <span className="muted">{s.state === "done" ? `${s.s}s` : s.state}</span>
                    {s.out && <> · <span className="mono">{s.out}</span>
                      {/\.(mp4|webm|mov|gif)$/.test(s.out) && <button className="small" onClick={() => setPlaying({ job: j.id, i, name: s.name, gif: s.out!.endsWith(".gif") })}>Play</button>}
                      <button className="small" onClick={() => reveal(j.id, i)} title="Show the file in Explorer">Show in folder</button></>}
                  </li>
                ))}
                {j.joined && (
                  <li className="done"><strong>Joined</strong> · <span className="mono">{j.joined}</span>
                    <button className="small" onClick={() => setPlaying({ job: j.id, i: j.scenes.filter((s) => s.out).length, name: "joined", gif: false })}>Play</button>
                    <button className="small" onClick={() => reveal(j.id, j.scenes.filter((s) => s.out).length)} title="Show the file in Explorer">Show in folder</button></li>
                )}
              </ul>
              {j.check && <details className={j.check.ok ? "ok" : "bad"}><summary>{j.check.ok ? "Narration check passed" : "Narration check found problems"}</summary><pre>{j.check.report}</pre></details>}
              {j.state === "failed" && j.log && <details open><summary>What Manim said</summary><pre>{j.log}</pre></details>}
            </div>
          ))}
        </div>
        {playing && (
          <div className="export-player">
            <div className="row"><strong>{playing.name}</strong><span className="grow" /><button className="small" onClick={() => setPlaying(null)}>Close</button></div>
            {playing.gif
              ? <img src={`/export/file?job=${playing.job}&i=${playing.i}`} alt={playing.name} />
              : <video src={`/export/file?job=${playing.job}&i=${playing.i}`} controls autoPlay />}
          </div>
        )}
      </div>
    </div>
  );
}
