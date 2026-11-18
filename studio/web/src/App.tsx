import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Conn, frameUrl, query } from "./api";
import type { Clip, DiffHunk, Model, Obj, SceneModel } from "./types";
import { Canvas } from "./Canvas";
import { Timeline } from "./Timeline";
import { Inspector } from "./Inspector";
import { CodePeek } from "./CodePeek";

const conn = new Conn();

interface Toast { id: number; kind: "ok" | "bad" | "info"; text: string }
interface Preview { token: string; summary: string; why: string; diff: DiffHunk[] }
export type Selection =
  | { kind: "object"; obj: Obj }
  | { kind: "clip"; clip: number; anim: number | null }
  | null;

export function App() {
  const [up, setUp] = useState(false);
  const [files, setFiles] = useState<{ path: string; scenes: string[] }[]>([]);
  const [file, setFile] = useState<string>(() => localStorageGet("studio.file") ?? "");
  const [model, setModel] = useState<Model | null>(null);
  const [sceneName, setSceneName] = useState<string | null>(null);
  const [f, setF] = useState(0);
  const [rest, setRest] = useState(true);
  const [playing, setPlaying] = useState(false);
  // objects belong to one frame of one revision; anything else is stale
  const [objs, setObjs] = useState<{ key: string; list: Obj[] }>({ key: "", list: [] });
  const [sel, setSel] = useState<Selection>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [lastDiff, setLastDiff] = useState<DiffHunk[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ cursors?: number; of?: number; cached?: number; frames?: number }>({});

  const toast = useCallback((kind: Toast["kind"], text: string) => {
    const id = Math.random();
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "bad" ? 9000 : 4500);
  }, []);

  // what the server should have open; re-sent after every reconnect
  const fileRef = useRef(file);
  const sceneRef = useRef<string | null>(null);
  fileRef.current = file;
  sceneRef.current = sceneName;

  // -- connection and file list ------------------------------------------------
  useEffect(() => {
    conn.onStatus = setUp;
    let first = true;
    conn.onOpen = () => {
      if (!first) fetch("/api/files").then((r) => r.json()).then(setFiles).catch(() => {});
      first = false;
      if (fileRef.current) {
        conn.send({ type: "open", file: fileRef.current });
        if (sceneRef.current) conn.send({ type: "scene", file: fileRef.current, scene: sceneRef.current });
      }
    };
    conn.connect();
    fetch("/api/files").then((r) => r.json()).then(setFiles).catch(() => {});
    return conn.on((m) => {
      if (m.type === "model") {
        if (m.file === fileRef.current) setModel(m);  // other files' models are for other tabs
      } else if (m.type === "file.changed") {
        toast("info", `${m.file} changed outside the studio; reloaded`);
      } else if (m.type === "error") {
        toast("bad", m.message);
      }
    });
  }, [toast]);

  useEffect(() => {
    if (!file) return;
    localStorageSet("studio.file", file);
    setModel(null);
    setSel(null);
    setSceneName(null);
    setStatus({});
    setF(0);
    // on the very first connect, onOpen sends this
    if (up) conn.send({ type: "open", file });
  }, [file]); // eslint-disable-line react-hooks/exhaustive-deps

  const scene: SceneModel | null = useMemo(() => {
    if (!model) return null;
    const name = sceneName && model.scenes.some((s) => s.name === sceneName) ? sceneName : model.active;
    return model.scenes.find((s) => s.name === name) ?? model.scenes[0] ?? null;
  }, [model, sceneName]);

  const nFrames = scene && !scene.pending ? Math.max(1, scene.frames) : 1;
  const fps = model?.fps ?? 15;
  const session = model?.session ?? "";
  const frameKey = model && scene ? `${model.session}|${model.rev}|${scene.name}|${f}` : "";
  const objects = objs.key === frameKey ? objs.list : [];

  useEffect(() => {
    if (f > nFrames - 1) setF(nFrames - 1);
  }, [nFrames, f]);

  const chooseScene = (name: string) => {
    setSceneName(name);
    setSel(null);
    setF(0);
    conn.send({ type: "scene", file, scene: name });
  };

  // -- objects at the playhead (only at rest) -------------------------------------
  useEffect(() => {
    if (!model || !scene || scene.pending || !rest || playing) return;
    let gone = false;
    const key = frameKey;
    const t = setTimeout(() => {
      fetch(`/objects?${query(model.file, scene.name, model.rev, f, session)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!gone) setObjs({ key, list: d && d.objects ? d.objects : [] });
        })
        .catch(() => { if (!gone) setObjs({ key, list: [] }); });
    }, 60);
    return () => {
      gone = true;
      clearTimeout(t);
    };
  }, [frameKey, rest, playing]); // eslint-disable-line react-hooks/exhaustive-deps

  // keep the selected object fresh after a reload (ids survive edits); an
  // object that isn't on screen at this frame stays selected but can't be edited
  const selOnScreen = sel?.kind === "object" && objs.key === frameKey && objects.some((x) => x.id === sel.obj.id);
  useEffect(() => {
    if (sel?.kind === "object" && objs.key === frameKey) {
      const o = objects.find((x) => x.id === sel.obj.id);
      if (o && o !== sel.obj) setSel({ kind: "object", obj: o });
    }
  }, [objs]); // eslint-disable-line react-hooks/exhaustive-deps

  // -- engine status ---------------------------------------------------------------
  useEffect(() => {
    if (!model) return;
    let inFlight = false, gone = false;
    const id = setInterval(() => {
      if (inFlight) return;  // the worker is busy; don't pile up requests
      inFlight = true;
      fetch(`/api/status?file=${encodeURIComponent(model.file)}`)
        .then((r) => r.json()).then((s) => { if (!gone) setStatus(s); }).catch(() => {})
        .finally(() => { inFlight = false; });
    }, 2000);
    return () => { gone = true; clearInterval(id); };
  }, [model?.file]);

  const selectedClip: Clip | null = sel?.kind === "clip" && scene && !scene.pending ? scene.clips[sel.clip] ?? null : null;
  const peekSpan = sel?.kind === "object" ? (sel.obj.site ?? sel.obj.user_site)
    : selectedClip ? selectedClip.call : null;
  const err = model?.error ?? scene?.error ?? null;
  const ready = !!(model && scene && !scene.pending);
  const time = (f / fps).toFixed(2);

  // -- playback ----------------------------------------------------------------------
  const playRef = useRef<{ t0: number; f0: number } | null>(null);
  useEffect(() => {
    if (!playing) return;
    playRef.current = { t0: performance.now(), f0: f >= nFrames - 1 ? 0 : f };
    setRest(false);
    let raf = 0;
    const tick = () => {
      const p = playRef.current!;
      const nf = p.f0 + Math.floor(((performance.now() - p.t0) / 1000) * fps);
      if (nf >= nFrames - 1) {
        setF(nFrames - 1);
        setPlaying(false);
        setRest(true);
        return;
      }
      setF(nf);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]); // eslint-disable-line react-hooks/exhaustive-deps

  const seek = useCallback((nf: number, atRest: boolean) => {
    setPlaying(false);
    setF(Math.max(0, Math.min(nFrames - 1, Math.round(nf))));
    setRest(atRest);
  }, [nFrames]);

  // pausing puts the playhead at rest: full frame, ID map and objects again
  const togglePlay = useCallback(() => {
    if (playing) setRest(true);
    setPlaying(!playing);
  }, [playing]);

  // -- edits -------------------------------------------------------------------------
  const diffTimer = useRef<number | undefined>(undefined);
  const handleReply = useCallback((r: any) => {
    setBusy(false);
    if (r.type === "edit.done") {
      toast("ok", `✓ ${r.summary} · verified`);
      setLastDiff(r.diff);
      clearTimeout(diffTimer.current);
      diffTimer.current = window.setTimeout(() => setLastDiff(null), 6000);
    } else if (r.type === "edit.refused") {
      toast("bad", `✗ Not changed: ${r.reason}`);
    } else if (r.type === "edit.preview") {
      setPreview({ token: r.token, summary: r.summary, why: r.why, diff: r.diff });
    } else if (r.type === "error") {
      toast("bad", r.message);
    }
  }, [toast]);

  const sendEdit = useCallback((msg: object) => {
    if (!model || !scene) return;
    setBusy(true);
    conn.request({ ...msg, file: model.file, scene: scene.name, rev: model.rev }).then(handleReply);
  }, [model, scene, handleReply]);

  const undoRedo = useCallback((which: "undo" | "redo") => {
    if (!model || busy || preview || !(which === "undo" ? model.undo : model.redo)) return;
    setBusy(true);
    conn.request({ type: which, file: model.file }).then(handleReply);
  }, [model, busy, preview, handleReply]);

  // -- keyboard ------------------------------------------------------------------------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (preview) return;  // the confirm dialog is open
      if (e.key === " ") {
        e.preventDefault();
        if (ready) togglePlay();
      } else if (e.key === "ArrowLeft") {
        seek(f - (e.shiftKey ? fps : 1), true);
      } else if (e.key === "ArrowRight") {
        seek(f + (e.shiftKey ? fps : 1), true);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        undoRedo(e.shiftKey ? "redo" : "undo");
      } else if (e.key === "Escape") {
        setSel(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [f, fps, seek, undoRedo, togglePlay, preview, ready]);

  return (
    <div className="app">
      <header className="bar">
        <strong className="brand">Manim Studio</strong>
        <select value={file} onChange={(e) => setFile(e.target.value)} title="Scene file">
          <option value="" disabled>Open a scene file…</option>
          {files.map((x) => <option key={x.path} value={x.path}>{x.path}</option>)}
        </select>
        {model && (
          <select value={scene?.name ?? ""} onChange={(e) => chooseScene(e.target.value)} title="Scene">
            {model.scenes.map((s) => <option key={s.name} value={s.name}>{s.name}{s.pending ? " (tracing…)" : ""}</option>)}
          </select>
        )}
        <span className="grow" />
        {model && (
          <span className={`pill ${err ? "err" : ready ? "ok" : "warm"}`}>
            {err ? `● ${err.message.slice(0, 60)}` : ready
              ? `● ready · cursors ${status.cursors ?? 0}/${status.of ?? 0} · cached ${status.cached ?? 0}/${status.frames ?? 0}`
              : "● tracing…"}
          </span>
        )}
        {model?.census && <span className="pill" title="Statements by tier (code_spec §2)">tier 1 {model.census.pct["1"]}% · 2 {model.census.pct["2"]}% · 3 {model.census.pct["3"]}%</span>}
        {model && <span className="pill">rev {model.rev}</span>}
        <button disabled={!model?.undo || busy} onClick={() => undoRedo("undo")} title="Undo (Ctrl+Z)">↶ Undo</button>
        <button disabled={!model?.redo || busy} onClick={() => undoRedo("redo")} title="Redo (Ctrl+Shift+Z)">↷ Redo</button>
        <span className={`dot ${up ? "on" : ""}`} title={up ? "connected" : "disconnected"} />
      </header>

      {!file && <div className="empty">Pick a scene file to open. The studio reads it, runs it, and shows every frame; your edits go straight into the .py file.</div>}

      {file && (
        <div className="main">
          <aside className="panel layers">
            <h3>Layers <small>at {time}s</small></h3>
            {objects.length === 0 && <div className="muted">{ready ? "Nothing selectable on screen" : "…"}</div>}
            {objects.map((o) => (
              <div key={o.id} className={`layer ${sel?.kind === "object" && sel.obj.id === o.id ? "sel" : ""}`}
                onClick={() => setSel({ kind: "object", obj: o })} title={o.call_text ?? o.id}>
                <span className="lname">{o.name ?? o.class}</span>
                <span className="badge">{o.class}</span>
                {o.tier === 2 && <span className="badge" title="tier 2: computed; literals editable">≈</span>}
                {o.tier === 3 && <span className="badge" title="tier 3: code only">🔒</span>}
              </div>
            ))}
          </aside>

          <section className="stage">
            {model && scene && !scene.pending ? (
              <Canvas
                url={frameUrl(model.file, scene.name, model.rev, f, rest && !playing, session)}
                idmapUrl={rest && !playing ? `/idmap?${query(model.file, scene.name, model.rev, f, session)}` : null}
                width={model.width} height={model.height}
                objects={rest && !playing ? objects : []}
                selected={sel?.kind === "object" ? sel.obj.id : null}
                onSelect={(o) => setSel(o ? { kind: "object", obj: o } : null)}
                stale={!!err}
              />
            ) : (
              <div className="canvas-placeholder">{err ? "The file doesn't run — see the error" : "Tracing the scene…"}</div>
            )}
            <div className="transport">
              <button onClick={() => seek(0, true)} title="Start">⏮</button>
              <button onClick={togglePlay} disabled={!ready} title="Play / pause (Space)">{playing ? "⏸" : "▶"}</button>
              <span className="mono">{time} / {scene && !scene.pending ? scene.duration.toFixed(2) : "…"} s · frame {f}</span>
              {scene?.target ? <span className="muted">TARGET {scene.target} s</span> : null}
              <span className="muted">{fps} fps</span>
            </div>
            {err && <div className="errbar">⚠ {err.message}{err.line ? ` (line ${err.line})` : ""} — editing is paused until the file runs again.</div>}
          </section>

          <aside className="panel inspector">
            <Inspector sel={sel} scene={scene && !scene.pending ? scene : null} model={model} busy={busy} f={f}
              onScreen={sel?.kind !== "object" || selOnScreen} sendEdit={sendEdit} />
          </aside>

          <section className="timeline-wrap">
            {scene && !scene.pending && (
              <Timeline scene={scene} f={f} fps={fps} nFrames={nFrames}
                sel={sel} onSeek={seek}
                onSelectClip={(clip, anim) => setSel({ kind: "clip", clip, anim })}
                selectedObjectId={sel?.kind === "object" ? sel.obj.id : null}
                onTrim={(clip, anim, d) => sendEdit({ type: "edit.timing", clip, anim, field: "duration", value: d })}
              />
            )}
          </section>

          <section className="code-wrap">
            {model && <CodePeek source={model.source} span={peekSpan} diff={lastDiff} file={model.file} />}
          </section>
        </div>
      )}

      {preview && (
        <div className="modal-back">
          <div className="modal">
            <h4>Check this edit first</h4>
            <p>{preview.why}</p>
            <DiffView diff={preview.diff} />
            <div className="btns">
              <button onClick={() => { conn.send({ type: "edit.cancel", file: model?.file, token: preview.token }); setPreview(null); }}>Cancel</button>
              <button className="pri" onClick={() => {
                setBusy(true);
                conn.request({ type: "edit.confirm", file: model?.file, token: preview.token }).then(handleReply);
                setPreview(null);
              }}>Apply</button>
            </div>
          </div>
        </div>
      )}

      <div className="toasts">
        {busy && <div className="toast info">Verifying the edit by replaying the scene…</div>}
        {toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
      </div>
    </div>
  );
}

export function DiffView({ diff }: { diff: DiffHunk[] }) {
  return (
    <div className="code small">
      {diff.map((h, i) => (
        <div key={i}>
          {h.before.map((l, j) => <div key={"b" + j} className="del"><span className="ln">{h.line + j}</span>{l}</div>)}
          {h.after.map((l, j) => <div key={"a" + j} className="add"><span className="ln">{h.line + j}</span>{l}</div>)}
        </div>
      ))}
    </div>
  );
}

function localStorageGet(k: string): string | null {
  try { return localStorage.getItem(k); } catch { return null; }
}
function localStorageSet(k: string, v: string) {
  try { localStorage.setItem(k, v); } catch { /* private mode */ }
}
