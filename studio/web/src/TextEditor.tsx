import { useEffect, useRef, useState } from "react";
import type { Obj, TextArg } from "./types";

const MATHS = new Set(["MathTex", "SingleStringMathTex"]);

/** Edits a Text / MathTex / Tex in place, over the object on the canvas.
 * One field per string argument (`MathTex("a^2", "+", "b^2")` has three).
 * Enter writes, Shift+Enter is a new line, Escape cancels. */
export function TextEditor({ obj, style, onDone }: {
  obj: Obj;
  style: React.CSSProperties;
  onDone: (changes: { span: NonNullable<TextArg["span"]>; value: string }[] | null) => void;
}) {
  const parts = obj.texts ?? [];
  const [vals, setVals] = useState(parts.map((p) => p.value ?? ""));
  const first = useRef<HTMLTextAreaElement>(null);
  const done = useRef(false);
  useEffect(() => { first.current?.focus(); first.current?.select(); }, []);
  const finish = (commit: boolean) => {
    if (done.current) return;
    done.current = true;
    if (!commit) { onDone(null); return; }
    const changes = parts.flatMap((p, i) => p.editable && p.span && vals[i] !== p.value
      ? [{ span: p.span, value: vals[i] }] : []);
    onDone(changes.length ? changes : null);
  };
  const maths = MATHS.has(obj.class);
  const firstEditable = parts.findIndex((p) => p.editable);
  return (
    <div className="text-editor" style={style}
      onMouseDown={(e) => {
        e.stopPropagation();
        // a click on the header, a fixed part or a gap keeps the field focused (a blur would cancel)
        if ((e.target as HTMLElement).tagName !== "TEXTAREA") e.preventDefault();
      }}
      onBlur={(e) => {
        // leaving the editor (not moving between its fields) cancels
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) finish(false);
      }}>
      <div className="te-head">{obj.name ?? obj.class}{maths ? " · LaTeX (maths)" : obj.class === "Tex" ? " · LaTeX" : ""}</div>
      {parts.map((p, i) => p.editable ? (
        <textarea key={i} ref={i === firstEditable ? first : undefined} value={vals[i]} spellCheck={!maths}
          rows={Math.min(6, Math.max(1, vals[i].split("\n").length))}
          aria-label={`Text ${i + 1}`}
          onChange={(e) => { const v = [...vals]; v[i] = e.target.value; setVals(v); }}
          onKeyDown={(e) => {
            e.stopPropagation();  // keys belong to the field, not the timeline or canvas
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); finish(true); }
            if (e.key === "Escape") { e.preventDefault(); finish(false); }
          }} />
      ) : (
        <div key={i} className="te-fixed" title="Computed in the code: change it there">
          {p.code ?? p.value ?? ""}
        </div>
      ))}
      <div className="te-hint">Enter to apply · Shift+Enter new line · Esc to cancel</div>
    </div>
  );
}
