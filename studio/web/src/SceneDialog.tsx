// Add, rename or delete a scene class (Phase 7 step 3). Each is one edit,
// verified by tracing and undone in one step. The server refuses names the
// file or Manim already uses, and deletes or renames of a class other code
// names; its reason shows here and the dialog stays open.
import { useEffect, useRef, useState } from "react";

export type SceneAction = "add" | "rename" | "delete";

export function SceneDialog({ action, scene, last, busy, onSubmit, onClose }: {
  action: SceneAction; scene: string; last: boolean; busy: boolean;
  onSubmit: (msg: object) => Promise<any> | null; onClose: () => void;
}) {
  const [name, setName] = useState(action === "rename" ? scene : "");
  const [where, setWhere] = useState<"after" | "end">("after");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLFormElement>(null);
  useEffect(() => { (inputRef.current ?? boxRef.current)?.focus(); inputRef.current?.select(); }, []);

  const n = name.trim();
  const badName = action !== "delete" && n !== "" && !/^[A-Za-z_]\w*$/.test(n);
  const can = !busy && !sending && (action === "delete" || (n !== "" && !badName && n !== scene));

  const submit = () => {
    if (!can) return;
    const msg = action === "add" ? { type: "edit.scene_add", name: n, where }
      : action === "rename" ? { type: "edit.scene_rename", name: n } : { type: "edit.scene_delete" };
    const p = onSubmit(msg);
    if (!p) { setError("Wait for the edit in progress, then try again"); return; }
    setSending(true);
    setError(null);
    p.then((r) => {
      setSending(false);
      if (r?.type === "edit.done") onClose();
      else setError(r?.reason ?? r?.message ?? "The edit was refused");
    });
  };

  const title = action === "add" ? "New scene" : action === "rename" ? `Rename ${scene}` : `Delete ${scene}`;
  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form className="modal newfile" role="dialog" aria-modal="true" aria-labelledby="scene-dlg-title" tabIndex={-1}
        ref={boxRef} onSubmit={(e) => { e.preventDefault(); submit(); }}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } }}>
        <h4 id="scene-dlg-title">{title}</h4>
        {action !== "delete" && (
          <label>Class name
            <input ref={inputRef} value={name} spellCheck={false} aria-invalid={badName}
              placeholder={action === "add" ? "e.g. Intro" : undefined}
              onChange={(e) => { setName(e.target.value); setError(null); }} />
          </label>
        )}
        {badName && <p className="err small">Letters, digits and _, not starting with a digit.</p>}
        {action === "add" && (<>
          <p className="muted small">Same base class as {scene}, with its TARGET and VOICE; an empty construct().</p>
          <div className="radios" role="radiogroup" aria-label="Where">
            <label className="check"><input type="radio" checked={where === "after"} onChange={() => setWhere("after")} />
              After {scene}</label>
            <label className="check"><input type="radio" checked={where === "end"} onChange={() => setWhere("end")}
              disabled={last} />At the end</label>
          </div>
        </>)}
        {action === "rename" && <p className="muted small">The class, and the file's SCENES list and render order if it has them.
          Other files that import it aren't checked.</p>}
        {action === "delete" && <p>The class {scene} and everything in it goes; Undo brings it back.
          Other files that import it aren't checked.</p>}
        {error && <p className="err" role="alert">{error}</p>}
        <div className="btns">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className={action === "delete" ? "danger" : "primary"} disabled={!can}>
            {sending ? "Checking…" : action === "add" ? "Add scene" : action === "rename" ? "Rename" : "Delete"}
          </button>
        </div>
      </form>
    </div>
  );
}
