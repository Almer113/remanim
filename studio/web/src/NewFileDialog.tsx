// New file (Phase 7 step 2): an in-app dialog instead of window.prompt (which
// the desktop app's browser pane doesn't support). The server checks the
// name (file.new refuses bad names and existing files); its message shows here
// and the dialog stays open to fix it.
import { useEffect, useRef, useState } from "react";
import type { Conn } from "./api";

interface Opts { voice: boolean; target: string }
const KEY = "studio.newfile";
function load(): Opts {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null");
    return { voice: !!v?.voice, target: typeof v?.target === "string" ? v.target : "5" };
  } catch { return { voice: false, target: "5" }; }
}
function save(o: Opts) {
  try { localStorage.setItem(KEY, JSON.stringify(o)); } catch { /* private window */ }
}

/** The class name the server would pick for a file name (my_scene.py → MyScene). */
export function classFor(file: string): string {
  const stem = (file.split("/").pop() ?? "").replace(/\.py$/, "");
  const s = stem.split(/[_\W]+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase()).join("");
  return s ? (/^[A-Za-z]/.test(s) ? s : "Scene" + s) : "NewScene";
}

export function NewFileDialog({ conn, onCreated, onClose }: {
  conn: Conn; onCreated: (file: string, scene: string) => void; onClose: () => void;
}) {
  const [name, setName] = useState("my_scene.py");
  const [scene, setScene] = useState("");
  const [opts, setOpts] = useState<Opts>(load);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => { nameRef.current?.focus(); nameRef.current?.setSelectionRange(0, "my_scene".length); }, []);

  const file = name.trim().endsWith(".py") ? name.trim() : name.trim() + ".py";
  const t = opts.target.trim();
  const target = t === "" ? null : Number(t);
  const badTarget = target !== null && !(Number.isFinite(target) && target > 0 && target <= 3600);
  const badScene = scene.trim() !== "" && !/^[A-Za-z_]\w*$/.test(scene.trim());

  const submit = () => {
    if (busy || !name.trim() || badTarget || badScene) return;
    setBusy(true);
    setError(null);
    save(opts);
    conn.request({ type: "file.new", name: file, ...(scene.trim() ? { scene: scene.trim() } : {}),
      voice: opts.voice, target }).then((r) => {
      setBusy(false);
      if (r.type === "file.created") onCreated(r.file, r.scene);
      else setError(r.message ?? "Couldn't make the file");
    });
  };

  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form className="modal newfile" role="dialog" aria-modal="true" aria-labelledby="newfile-title"
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } }}>
        <h4 id="newfile-title">New scene file</h4>
        <label>File name
          <input ref={nameRef} value={name} spellCheck={false} onChange={(e) => { setName(e.target.value); setError(null); }}
            aria-describedby="newfile-where" />
        </label>
        <p id="newfile-where" className="muted small">Inside the project; folders with / (e.g. <code>videos/intro.py</code>).</p>
        <label>Scene class
          <input value={scene} spellCheck={false} placeholder={classFor(file)} aria-invalid={badScene}
            onChange={(e) => { setScene(e.target.value); setError(null); }} />
        </label>
        {badScene && <p className="err small">A class name: letters, digits and _, not starting with a digit.</p>}
        <label className="check">
          <input type="checkbox" checked={opts.voice} onChange={(e) => setOpts({ ...opts, voice: e.target.checked })} />
          Narrated (the house voice, en-US-AndrewNeural)
        </label>
        <label>Length (TARGET, seconds)
          <input value={opts.target} inputMode="decimal" placeholder="none" aria-invalid={badTarget}
            onChange={(e) => setOpts({ ...opts, target: e.target.value })} />
        </label>
        <p className="muted small">{badTarget ? <span className="err">A number of seconds above 0, or blank.</span>
          : target === null ? "Blank: the scene is as long as what's in it." : "The scene is padded to this length."}</p>
        {error && <p className="err" role="alert">{error}</p>}
        <div className="btns">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary" disabled={busy || !name.trim() || badTarget || badScene}>
            {busy ? "Making…" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
