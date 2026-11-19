import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Conn, frameUrl, query } from "./api";
import type { CameraState, Clip, DiffHunk, Ghost, LibItem, Literal, Model, Obj, SceneModel, Span } from "./types";
import { Canvas, type Gesture } from "./Canvas";
import { Library } from "./Library";
import { Timeline } from "./Timeline";
import { Inspector } from "./Inspector";
import { CodePeek } from "./CodePeek";

const conn = new Conn();

interface Toast { id: number; kind: "ok" | "bad" | "info"; text: string }
interface Alt { token: string; summary: string; diff: DiffHunk[]; label: string }
interface Preview { token: string; summary: string; why: string; diff: DiffHunk[]; also: string[]; alts: Alt[] }
export type Selection =
  | { kind: "object"; obj: Obj }
  // `line` and `text` find the clip again after an edit moves the indexes
  | { kind: "clip"; clip: number; anim: number | null; line?: number | null; text?: string | null }
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
  const [muted, setMuted] = useState(() => localStorageGet("studio.muted") === "1");
  // objects belong to one frame of one revision; anything else is stale
  const [objs, setObjs] = useState<{ key: string; list: Obj[]; camera?: CameraState | null; ghosts?: Ghost[] | null }>({ key: "", list: [] });
  const [sel, setSel] = useState<Selection>(null);
  const [others, setOthers] = useState<string[]>([]);  // shift-click adds to the selection
  const [leftTab, setLeftTab] = useState<"layers" | "library">("layers");
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
  const [camCanvas, setCamCanvas] = useState(false);
  // a 3D scene's first frame: where the scene before ends, for the continuity warning
  const [prevCam, setPrevCam] = useState<{ key: string; scene: string; cam: CameraState } | null>(null);
  const prevScene = model && scene ? model.scenes[model.scenes.findIndex((s) => s.name === scene.name) - 1] : undefined;
  const prevKey = model && prevScene && !prevScene.pending ? `${model.session}|${model.rev}|${prevScene.name}` : "";
  const wantPrev = f === 0 && objs.key === frameKey && objs.camera?.kind === "3d" && !!prevKey;
  useEffect(() => {
    if (!wantPrev || !model || !prevScene || prevCam?.key === prevKey) return;
    let gone = false;
    fetch(`/objects?${query(model.file, prevScene.name, model.rev, Math.max(0, prevScene.frames - 1), session)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!gone && d?.camera) setPrevCam({ key: prevKey, scene: prevScene.name, cam: d.camera }); })
      .catch(() => {});
    return () => { gone = true; };
  }, [wantPrev, prevKey]); // eslint-disable-line react-hooks/exhaustive-deps
  // the selected play() is under the playhead: show where its transforms go (step 8)
  const selClip = sel?.kind === "clip" && scene ? scene.clips[sel.clip] : null;
  const ghosts: Ghost[] | null = selClip && objs.key === frameKey && objs.ghosts
    && selClip.start - 1e-6 <= f / fps && f / fps < selClip.start + selClip.duration
    ? objs.ghosts.filter((g) => sel?.kind !== "clip" || sel.anim === null || g.index === sel.anim) : null;

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
          if (!gone) setObjs({ key, list: d && d.objects ? d.objects : [], camera: d?.camera ?? null, ghosts: d?.ghosts ?? null });
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

  // a clip is selected by index, and edits (an insert above it, undo) move indexes:
  // find the same clip again in every new model, or let it go
  useEffect(() => {
    if (sel?.kind !== "clip" || !scene || scene.pending) return;
    const at = scene.clips[sel.clip];
    if (at && at.line === sel.line && at.text === sel.text) return;
    const same = scene.clips.map((c, i) => [c, i] as const).filter(([c]) => c.text === sel.text);
    const byLine = scene.clips.findIndex((c) => c.line === sel.line);
    const pick = same.length ? same.reduce((a, b) => Math.abs(b[1] - sel.clip) < Math.abs(a[1] - sel.clip) ? b : a)[1]
      : at && at.line === sel.line ? sel.clip : byLine >= 0 && sel.text === undefined ? byLine : -1;
    if (pick < 0) setSel(null);
    else if (pick !== sel.clip) setSel({ ...sel, clip: pick, line: scene.clips[pick].line, text: scene.clips[pick].text });
  }, [scene]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedClip: Clip | null = sel?.kind === "clip" && scene && !scene.pending ? scene.clips[sel.clip] ?? null : null;
  const peekSpan = sel?.kind === "object" ? (sel.obj.site ?? sel.obj.user_site)
    : selectedClip ? selectedClip.call : null;
  const err = model?.error ?? scene?.error ?? null;
  const ready = !!(model && scene && !scene.pending);
  const time = (f / fps).toFixed(2);

  // -- playback ----------------------------------------------------------------------
  const playRef = useRef<{ t0: number; f0: number } | null>(null);
  const hasSound = !!scene && !scene.pending && ((scene.voice ?? []).length > 0 || (scene.sounds ?? []).length > 0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    if (!playing) return;
    playRef.current = { t0: performance.now(), f0: f >= nFrames - 1 ? 0 : f };
    setRest(false);
    // the scene's narration and sounds, mixed by the server (GET /audio); the
    // audio clock drives the frames while it plays, so picture and words stay
    // together. Until the sound really starts (the mix is made and loaded),
    // the picture holds at the start frame instead of running ahead.
    let audio: HTMLAudioElement | null = null;
    let waiting = false;
    if (hasSound && model && scene) {
      audio = new Audio(`/audio?file=${encodeURIComponent(model.file)}&scene=${encodeURIComponent(scene.name)}`
        + `&rev=${model.rev}&s=${encodeURIComponent(session)}`);
      audio.muted = muted;
      audio.currentTime = playRef.current.f0 / fps;
      waiting = true;
      const go = () => {
        if (!waiting) return;
        waiting = false;
        const want = playRef.current!.f0 / fps;
        if (audio && Math.abs(audio.currentTime - want) > 0.25) {
          // the sound couldn't seek there: keep the picture on the wall clock
          // and silence the sound rather than play the wrong words
          audio.pause();
          audio = null;
        }
        playRef.current = { t0: performance.now(), f0: playRef.current!.f0 };
      };
      const fail = () => { waiting = false; audio = null; playRef.current = { t0: performance.now(), f0: playRef.current!.f0 }; };
      audio.addEventListener("playing", go, { once: true });
      audio.addEventListener("error", fail, { once: true });
      audio.play().catch(fail);
      audioRef.current = audio;
    }
    let raf = 0;
    const tick = () => {
      const p = playRef.current!;
      if (waiting) { raf = requestAnimationFrame(tick); return; }
      const viaAudio = audio && !audio.paused && !audio.ended;
      const nf = viaAudio ? Math.floor(audio!.currentTime * fps)
        : p.f0 + Math.floor(((performance.now() - p.t0) / 1000) * fps);
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
    return () => {
      cancelAnimationFrame(raf);
      waiting = false;
      if (audio) { audio.pause(); audio.removeAttribute("src"); audio.load(); }
      audioRef.current = null;
    };
  }, [playing]); // eslint-disable-line react-hooks/exhaustive-deps

  // a different scene, file or revision stops playback (and its sound)
  useEffect(() => {
    setPlaying(false);
    setRest(true);
  }, [file, scene?.name, model?.rev, session]);

  // mute and unmute while playing
  useEffect(() => {
    if (audioRef.current) audioRef.current.muted = muted;
  }, [muted]);

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
      setPreview({ token: r.token, summary: r.summary, why: r.why, diff: r.diff, also: r.also_moves ?? [], alts: r.alternatives ?? [] });
    } else if (r.type === "error") {
      toast("bad", r.message);
    }
  }, [toast]);

  // one edit at a time, and none while a preview waits for an answer
  const sendEdit = useCallback((msg: object): Promise<any> | null => {
    if (!model || !scene || busy || preview) return null;
    setBusy(true);
    return conn.request({ ...msg, file: model.file, scene: scene.name, rev: model.rev }).then((r) => {
      handleReply(r);
      return r;
    });
  }, [model, scene, handleReply, busy, preview]);

  const select = useCallback((o: Obj | null, how: "set" | "toggle" = "set") => {
    if (!o) { setSel(null); setOthers([]); return; }
    if (how === "toggle" && sel?.kind === "object") {
      if (o.id === sel.obj.id) return;
      setOthers((l) => l.includes(o.id) ? l.filter((x) => x !== o.id) : [...l, o.id]);
      return;
    }
    setSel({ kind: "object", obj: o });
    setOthers([]);
  }, [sel]);

  const canEdit = ready && !busy && !preview && !err && rest && !playing;
  const [textEdit, setTextEdit] = useState<Obj | null>(null);
  useEffect(() => setTextEdit(null), [model?.rev, scene?.name, f]);
  const onTextDone = useCallback(async (changes: { span: Span; value: string }[] | null) => {
    setTextEdit(null);
    if (!changes?.length) return;
    // every changed part in one edit: one undo step
    sendEdit({ type: "edit.literal", changes: changes.map((c) => ({ span: c.span, value: { string: c.value } })) });
  }, [sendEdit]);
  // part colour: pick glyphs of the selected text on the canvas, then a colour
  const [partPick, setPartPick] = useState<Obj | null>(null);
  useEffect(() => setPartPick(null), [model?.rev, scene?.name, f]);
  const onPartDone = useCallback((pick: { glyphs: number[]; colour: string } | null) => {
    const o = partPick;
    setPartPick(null);
    if (!pick || !o) return;
    sendEdit({ type: "edit.part_colour", object: o, f, glyphs: pick.glyphs, value: { name: pick.colour } });
  }, [partPick, sendEdit, f]);
  const onLiteral = useMemo(() => canEdit
    ? (lit: Literal, value: object) => sendEdit({ type: "edit.literal", span: lit.span, value })
    : null, [canEdit, sendEdit]);

  const onGesture = useCallback((g: Gesture) => {
    if (g.kind === "move") sendEdit({ type: "edit.move", object: g.obj, f, dx: g.dx, dy: g.dy });
    else if (g.kind === "scale") sendEdit({ type: "edit.scale", object: g.obj, f, k: g.k });
    else sendEdit({ type: "edit.rotate", object: g.obj, f, deg: g.deg });
  }, [sendEdit, f]);

  const onDrop = useCallback((item: LibItem, x: number, y: number, on: Obj | null) => {
    if (!canEdit) {
      toast("info", busy ? "Wait for the edit in progress" : playing || !rest ? "Pause first, then drop"
        : "Editing is paused (see the status above)");
      return;
    }
    if (item.kind === "shape") {
      sendEdit({ type: "edit.insert", class: item.class, x, y, f, ...(item.entrance ? { entrance: item.entrance } : {}) });
    } else if (item.kind === "composite") {
      if (item.onObject && !on) { toast("info", "Drop it on an object"); return; }
      sendEdit({ type: "edit.composite", preset: item.preset, x, y, f, ...(item.onObject ? { object: on } : {}) });
    } else if (on) {
      sendEdit({ type: "edit.preset", object: on, preset: item.preset, f });
    } else {
      toast("info", `Drop ${item.preset} on an object`);
    }
  }, [canEdit, sendEdit, f, toast, busy, playing, rest]);

  const onPick = useCallback((item: LibItem) => {
    if (item.kind === "shape" || (item.kind === "composite" && !item.onObject)) onDrop(item, 0, 0, null);
    else if (sel?.kind === "object") onDrop(item, 0, 0, sel.obj);
    else toast("info", `Select an object first, or drag ${item.preset} onto one`);
  }, [onDrop, sel, toast]);

  const selectedObjs = sel?.kind === "object"
    ? [sel.obj, ...others.map((id) => objects.find((o) => o.id === id)).filter((o): o is Obj => !!o)] : [];

  // the same rules for keys and Inspector buttons
  const objLocked = sel?.kind === "object" && (!sel.obj.site || sel.obj.tier === 3);
  const objReady = canEdit && sel?.kind === "object" && selOnScreen;
  const offScreenNote = () => toast("info", "Not on screen at this frame: move the playhead to where it shows");

  const doDelete = useCallback(() => {
    if (!canEdit || !sel) return;
    if (sel.kind === "object" && !selOnScreen) { offScreenNote(); return; }
    const p = sel.kind === "object" ? sendEdit({ type: "edit.delete", object: sel.obj, f })
      : sendEdit({ type: "edit.delete_clip", clip: sel.clip, anim: sel.anim });
    // keep the selection if the delete is refused
    p?.then((r) => { if (r?.type === "edit.done") { setSel(null); setOthers([]); } });
  }, [canEdit, sel, sendEdit, f, selOnScreen]); // eslint-disable-line react-hooks/exhaustive-deps
  const doDuplicate = useCallback(() => {
    if (!canEdit || sel?.kind !== "object") return;
    if (!selOnScreen) { offScreenNote(); return; }
    if (objLocked || sel.obj.virtual) { toast("info", "This one can't be duplicated from the studio"); return; }
    sendEdit({ type: "edit.duplicate", object: sel.obj, f });
  }, [canEdit, sel, sendEdit, f, selOnScreen, objLocked]); // eslint-disable-line react-hooks/exhaustive-deps
  const doGroup = useCallback(() => {
    if (!objReady) { if (canEdit && sel?.kind === "object") offScreenNote(); return; }
    if (selectedObjs.length < 2) { toast("info", "Shift-click a second object to group them"); return; }
    sendEdit({ type: "edit.group", objects: selectedObjs, f });
  }, [objReady, canEdit, sel, selectedObjs, sendEdit, f, toast]); // eslint-disable-line react-hooks/exhaustive-deps

  const cancelPreview = useCallback(() => {
    if (!preview) return;
    for (const t of [preview.token, ...preview.alts.map((a) => a.token)]) conn.send({ type: "edit.cancel", file: model?.file, token: t });
    setPreview(null);
  }, [preview, model?.file]);

  const newFile = useCallback(() => {
    const name = window.prompt("New scene file (inside the project), e.g. my_scene.py", "my_scene.py");
    if (!name) return;
    conn.request({ type: "file.new", name }).then((r) => {
      if (r.type !== "file.created") { toast("bad", r.message ?? "Couldn't make the file"); return; }
      fetch("/api/files").then((x) => x.json()).then(setFiles).catch(() => {});
      setFile(r.file);
      setLeftTab("library");
      toast("ok", `✓ Made ${r.file} with scene ${r.scene}`);
    });
  }, [toast]);

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
      if (preview) {  // the confirm dialog is open: Escape cancels it, nothing else
        if (e.key === "Escape") cancelPreview();
        return;
      }
      // Backspace deletes only when nothing has focus (not after clicking a button)
      if (e.key === "Backspace" && e.target !== document.body) return;
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
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        undoRedo("redo");
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") {
        e.preventDefault();
        doDuplicate();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "g") {
        e.preventDefault();
        doGroup();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        doDelete();
      } else if (e.key === "Escape") {
        setSel(null);
        setOthers([]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [f, fps, seek, undoRedo, togglePlay, preview, ready, doDelete, doDuplicate, doGroup]); // eslint-disable-line react-hooks/exhaustive-deps

  // the dialog takes the focus (not a button: a second Enter from the field
  // must not answer it unread); Tab reaches the buttons, Escape cancels
  const modalRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (preview) modalRef.current?.focus();
  }, [preview]);

  return (
    <div className="app">
      <header className="bar">
        <strong className="brand">Manim Studio</strong>
        <select value={file} onChange={(e) => setFile(e.target.value)} title="Scene file">
          <option value="" disabled>Open a scene file…</option>
          {file && !files.some((x) => x.path === file) && <option value={file}>{file}</option>}
          {files.map((x) => <option key={x.path} value={x.path}>{x.path}</option>)}
        </select>
        <button onClick={newFile} title="A new scene file from the studio template">+ New file</button>
        {model && (
          <select value={scene?.name ?? ""} onChange={(e) => chooseScene(e.target.value)} title="Scene">
            {model.scenes.map((s) => <option key={s.name} value={s.name}>{s.name}{s.pending ? " (tracing…)" : ""}</option>)}
          </select>
        )}
        {model && model.scenes.length > 1 && scene && (() => {
          const names = model.scenes.map((s) => s.name);
          const i = names.indexOf(scene.name);
          const moveScene = (d: number) => {
            const order = [...names];
            order.splice(i, 1);
            order.splice(i + d, 0, scene.name);
            sendEdit({ type: "edit.scene_order", order });
          };
          return (
            <span className="scene-order" title="Render order (the file's SCENES list)">
              <button disabled={!canEdit || i <= 0} onClick={() => moveScene(-1)}
                title="Render this scene earlier" aria-label="Render this scene earlier">◀</button>
              <span className="muted">{i + 1}/{names.length}</span>
              <button disabled={!canEdit || i >= names.length - 1} onClick={() => moveScene(1)}
                title="Render this scene later" aria-label="Render this scene later">▶</button>
            </span>
          );
        })()}
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
            <div className="tabs">
              <button className={leftTab === "layers" ? "on" : ""} onClick={() => setLeftTab("layers")}>Layers</button>
              <button className={leftTab === "library" ? "on" : ""} onClick={() => setLeftTab("library")}>Library</button>
              <small className="muted">at {time}s</small>
            </div>
            {leftTab === "library" ? (
              <Library disabled={!canEdit} hasSelection={sel?.kind === "object"} onPick={onPick} />
            ) : (
              <>
                {objects.length === 0 && <div className="muted">{ready ? "Nothing selectable on screen" : "…"}</div>}
                <LayerTree objects={objects} sel={sel?.kind === "object" ? sel.obj.id : null} others={others}
                  onPick={(o, toggle) => select(o, toggle ? "toggle" : "set")} />
              </>
            )}
          </aside>

          <section className="stage">
            {model && scene && !scene.pending ? (
              <Canvas
                url={frameUrl(model.file, scene.name, model.rev, f, rest && !playing, session)}
                idmapUrl={rest && !playing ? `/idmap?${query(model.file, scene.name, model.rev, f, session)}` : null}
                width={model.width} height={model.height}
                frameW={model.frame_width ?? 14.2222} frameH={model.frame_height ?? 8}
                objects={rest && !playing ? objects : []}
                selected={sel?.kind === "object" ? sel.obj.id : null}
                others={others}
                onSelect={select}
                onGesture={onGesture}
                onDrop={onDrop}
                editable={canEdit}
                stale={!!err}
                onTextEdit={canEdit ? setTextEdit : null}
                textEdit={textEdit}
                onTextDone={onTextDone}
                partPick={partPick}
                glyphUrl={partPick ? `/glyphs?${query(model.file, scene.name, model.rev, f, session)}&id=${encodeURIComponent(partPick.id)}` : null}
                onPartDone={onPartDone}
                ghosts={ghosts}
                camera={camCanvas && canEdit && objs.key === frameKey && objs.camera ? {
                  cam: objs.camera, onCommit: (m: object) => sendEdit({ type: "edit.camera", f, ...m }),
                  onClose: () => setCamCanvas(false) } : null}
                onMatch={canEdit && sel?.kind === "clip" ? (arg, sk, tk) => sendEdit({ type: "edit.match_parts",
                  clip: sel.clip, arg, source_key: sk, target_key: tk }) : null}
              />
            ) : (
              <div className="canvas-placeholder">{err ? "The file doesn't run — see the error" : "Tracing the scene…"}</div>
            )}
            <div className="transport">
              <button onClick={() => seek(0, true)} title="Start">⏮</button>
              <button onClick={togglePlay} disabled={!ready} title="Play / pause (Space)">{playing ? "⏸" : "▶"}</button>
              <span className="mono">{time} / {scene && !scene.pending ? scene.duration.toFixed(2) : "…"} s · frame {f}</span>
              {scene?.target ? <span className="muted">TARGET {scene.target} s</span> : null}
              {hasSound && <button className="ghost" aria-pressed={muted} aria-label={muted ? "Sound off" : "Sound on"} onClick={() => { const m = !muted; setMuted(m); localStorageSet("studio.muted", m ? "1" : "0"); }}
                title={muted ? "Sound off: narration is not played" : "Sound on: narration plays with the picture"}>{muted ? "🔇" : "🔊"}</button>}
              <span className="muted">{fps} fps</span>
            </div>
            {err && <div className="errbar">⚠ {err.message}{err.line ? ` (line ${err.line})` : ""} — editing is paused until the file runs again.</div>}
          </section>

          <aside className="panel inspector">
            <Inspector sel={sel} scene={scene && !scene.pending ? scene : null} model={model} busy={busy || !!preview} f={f}
              onScreen={sel?.kind !== "object" || selOnScreen} sendEdit={sendEdit}
              camera={canEdit && objs.key === frameKey ? objs.camera ?? null : null}
              prevCamera={wantPrev && prevCam?.key === prevKey ? prevCam : null}
              camCanvas={{ on: camCanvas, toggle: () => setCamCanvas((v) => !v) }}
              actions={{ remove: doDelete, duplicate: doDuplicate, group: doGroup, count: selectedObjs.length,
                partColour: canEdit && sel?.kind === "object" && selOnScreen ? () => setPartPick(sel.obj) : null }} />
          </aside>

          <section className="timeline-wrap">
            {scene && !scene.pending && (
              <Timeline scene={scene} file={model!.file} rev={model!.rev} session={session} f={f} fps={fps} nFrames={nFrames}
                sel={sel} onSeek={seek} editable={canEdit} onEdit={sendEdit}
                onBlocked={(why) => toast("info", why)}
                onSelectClip={(clip, anim) => setSel({ kind: "clip", clip, anim, line: scene.clips[clip]?.line,
                  text: scene.clips[clip]?.text })}
                selectedObjectId={sel?.kind === "object" ? sel.obj.id : null}
                onTrim={(clip, anim, d) => sendEdit({ type: "edit.timing", clip, anim, field: "duration", value: d })}
              />
            )}
          </section>

          <section className="code-wrap">
            {model && <CodePeek source={model.source} span={peekSpan} diff={lastDiff} file={model.file}
              literals={model.literals}
              onLiteral={onLiteral} />}
          </section>
        </div>
      )}

      {preview && (
        <div className="modal-back">
          <div className="modal" ref={modalRef} tabIndex={-1} role="dialog" aria-modal="true">
            <h4>Check this edit first</h4>
            <p>{preview.why}</p>
            {preview.also.length > 0 && <p className="note">This also moves: {preview.also.join(", ")}</p>}
            <DiffView diff={preview.diff} />
            {preview.alts.map((a) => (
              <div key={a.token}>
                <p className="alt-head">Or change only this one: {a.summary.replace(/^only this one: /, "")}</p>
                <DiffView diff={a.diff} />
              </div>
            ))}
            <div className="btns">
              <button onClick={cancelPreview}>Cancel</button>
              {preview.alts.map((a) => (
                <button key={a.token} onClick={() => {
                  setBusy(true);
                  conn.send({ type: "edit.cancel", file: model?.file, token: preview.token });
                  conn.request({ type: "edit.confirm", file: model?.file, token: a.token }).then(handleReply);
                  setPreview(null);
                }}>{a.label}</button>
              ))}
              <button className="pri" onClick={() => {
                setBusy(true);
                for (const a of preview.alts) conn.send({ type: "edit.cancel", file: model?.file, token: a.token });
                conn.request({ type: "edit.confirm", file: model?.file, token: preview.token }).then(handleReply);
                setPreview(null);
              }}>{preview.alts.length ? "Every one" : "Apply"}</button>
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

/** Objects on screen as a tree: a group the user made holds its parts.
 * Click selects, Shift-click adds to the selection. */
function LayerTree({ objects, sel, others, onPick }: {
  objects: Obj[]; sel: string | null; others: string[]; onPick: (o: Obj, toggle: boolean) => void;
}) {
  const kids = new Map<number, number[]>();
  const roots: number[] = [];
  objects.forEach((o, i) => {
    if (o.parent !== undefined && objects[o.parent]) {
      const l = kids.get(o.parent) ?? [];
      l.push(i);
      kids.set(o.parent, l);
    } else roots.push(i);
  });
  const row = (i: number, depth: number, seen: Set<number>): React.ReactNode => {
    if (seen.has(i)) return null;
    seen.add(i);
    const o = objects[i];
    const cls = o.id === sel ? "sel" : others.includes(o.id) ? "sel2" : "";
    return (
      <div key={o.id}>
        <div className={`layer ${cls}`} style={{ paddingLeft: 6 + depth * 12 }}
          onClick={(e) => onPick(o, e.shiftKey)} title={o.call_text ?? o.id}>
          <span className="lname">{o.virtual ? "▾ " : ""}{o.name ?? o.class}</span>
          <span className="badge">{o.class}</span>
          {o.tier === 2 && <span className="badge" title="tier 2: computed; literals editable">≈</span>}
          {o.tier === 3 && <span className="badge" title="tier 3: code only">🔒</span>}
        </div>
        {(kids.get(i) ?? []).map((j) => row(j, depth + 1, seen))}
      </div>
    );
  };
  const seen = new Set<number>();
  // groups first, the way they read in the code
  return <>{[...roots.filter((i) => objects[i].virtual), ...roots.filter((i) => !objects[i].virtual)].map((i) => row(i, 0, seen))}</>;
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
