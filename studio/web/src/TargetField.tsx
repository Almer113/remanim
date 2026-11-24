// The scene's length, TARGET (Phase 7 step 4): type a length and press
// Enter, or "fit" (the content's end + 0.1 s). A TimedScene without one gets
// "+ target". A computed TARGET is shown, greyed, with the reason.
import { useEffect, useRef, useState } from "react";
import type { SceneModel } from "./types";

export function TargetField({ scene, canEdit, onEdit }: {
  scene: SceneModel; canEdit: boolean; onEdit: (msg: object) => Promise<any> | null;
}) {
  const info = scene.target_info;
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);
  const sendingRef = useRef(false);
  useEffect(() => { setText(info?.value != null ? String(info.value) : ""); setAdding(false); }, [info?.value, scene.name]);
  if (!info || (!info.editable && info.value == null)) {
    return scene.target ? <span className="muted">TARGET {scene.target} s</span> : null;
  }
  const end = info.content_end.toFixed(2);
  if (!info.editable) {
    return <span className="muted target-field" title={info.computed ?? "Not editable here"}>TARGET {info.value} s</span>;
  }
  if (info.value == null && !adding) {
    return <button className="ghost small" disabled={!canEdit} onClick={() => setAdding(true)}
      title={`Pad the scene to a fixed length (the content ends at ${end} s)`}>+ target</button>;
  }
  const v = Number(text);
  const ok = text.trim() !== "" && Number.isFinite(v) && v > 0;
  const reset = () => setText(info.value != null ? String(info.value) : "");
  const bad = text.trim() !== "" && !ok;
  const send = (value: number | "fit") => {
    const p = onEdit({ type: "edit.target", value });
    if (!p) { reset(); return; }  // another edit is running: nothing was sent
    p.then((r) => { if (r?.type !== "edit.done") reset(); });
  };
  return (
    <span className="target-field" title={`The scene is padded to this length. Content ends at ${end} s.${info.line ? ` TARGET is on line ${info.line}.` : ""}`}>
      <label>TARGET <input value={text} inputMode="decimal" size={5} disabled={!canEdit} aria-label="Scene length (TARGET), seconds"
        autoFocus={adding} aria-invalid={bad} className={bad ? "bad" : undefined}
        title={bad ? "A length in seconds, more than 0" : undefined}
        onChange={(e) => setText(e.target.value)}
        // leaving the field without Enter puts the real value back (it must never show a length the file doesn't have)
        onBlur={() => { if (!sendingRef.current) reset(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            const el = e.target as HTMLInputElement;
            if (ok && v !== info.value) {
              // the typed value stays while the edit runs (a refusal puts the old one back)
              sendingRef.current = true; send(v); el.blur(); sendingRef.current = false;
            } else { reset(); el.blur(); }
          }
          if (e.key === "Escape") { setText(info.value != null ? String(info.value) : ""); setAdding(false); (e.target as HTMLInputElement).blur(); }
        }} /> s</label>
      <button className="ghost small" disabled={!canEdit} onClick={() => send("fit")}
        title={`Fit to the content: ${end} s + 0.1 s`}>fit</button>
    </span>
  );
}
