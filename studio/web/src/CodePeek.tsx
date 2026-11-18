import { useEffect, useRef } from "react";
import type { DiffHunk, Span } from "./types";

/** The code behind the selection, with the last edit highlighted. */
export function CodePeek({ source, span, diff, file }: { source: string; span: Span | null; diff: DiffHunk[] | null; file: string }) {
  const lines = source.split(/\r?\n/);
  const box = useRef<HTMLDivElement>(null);
  const added = new Set<number>();
  for (const h of diff ?? []) h.after.forEach((_, j) => added.add(h.line + j));
  const focus = diff?.length ? diff[0].line : span ? span[0] : null;
  useEffect(() => {
    const el = box.current?.querySelector(".focus") as HTMLElement | null;
    if (el && box.current) box.current.scrollTop = el.offsetTop - box.current.clientHeight / 3;
  }, [focus, source]);
  return (
    <div className="codepeek">
      <h3>Code <small>{file}{span ? ` · line ${span[0]}` : ""}</small></h3>
      <div className="code" ref={box}>
        {lines.map((l, i) => {
          const n = i + 1;
          const inSpan = span && n >= span[0] && n <= span[2];
          const cls = added.has(n) ? "add" : inSpan ? "hl" : "";
          return (
            <div key={i} className={`${cls} ${n === focus ? "focus" : ""}`}>
              <span className="ln">{n}</span>{l || " "}
            </div>
          );
        })}
      </div>
    </div>
  );
}
