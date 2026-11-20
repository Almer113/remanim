// The scene's length, TARGET (Phase 7 step 4): type a length and press
// Enter, or "fit" (the content's end + 0.1 s). A TimedScene without one gets
// "+ target". A computed TARGET is shown, greyed, with the reason.
import { useEffect, useState } from "react";
import type { SceneModel } from "./types";

export function TargetField({ scene, canEdit, onEdit }: {
  scene: SceneModel; canEdit: boolean; onEdit: (msg: object) => Promise<any> | null;
}) {
  const info = scene.target_info;
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);
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
  const send = (value: number | "fit") => onEdit({ type: "edit.target", value })?.then((r) => {
    if (r?.type !== "edit.done") setText(info.value != null ? String(info.value) : "");
  });
  return (
    <span className="target-field" title={`The scene is padded to this length. Content ends at ${end} s.${info.line ? ` TARGET is on line ${info.line}.` : ""}`}>
      <label>TARGET <input value={text} inputMode="decimal" size={5} disabled={!canEdit} aria-label="Scene length (TARGET), seconds"
        autoFocus={adding}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && ok && v !== info.value) { e.preventDefault(); send(v); (e.target as HTMLInputElement).blur(); }
          if (e.key === "Escape") { setText(info.value != null ? String(info.value) : ""); setAdding(false); (e.target as HTMLInputElement).blur(); }
        }} /> s</label>
      <button className="ghost small" disabled={!canEdit} onClick={() => send("fit")}
        title={`Fit to the content: ${end} s + 0.1 s`}>fit</button>
    </span>
  );
}
