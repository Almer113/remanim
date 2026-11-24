// The bar between the canvas and the timeline (Phase 7 step 10): drag it to
// give one more room, double-click to go back to the default share. Arrow
// keys move it too. The height is remembered in this browser.
import { useRef } from "react";

const MIN = 40;
/** Room the rest of the window needs: header, timeline tools, the code row
 * (190 px) and a canvas row of at least 200 px. styles.css caps --tl-h the
 * same way, so a height saved in a taller window can't hide the canvas. */
export const RESERVED = 470;
const maxH = () => Math.max(MIN, window.innerHeight - RESERVED);

export function Splitter({ height, onHeight }: { height: number | null; onHeight: (h: number | null) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const current = () => {
    const sc = ref.current?.parentElement?.querySelector(".tl-scroll") as HTMLElement | null;
    // what is on screen (the CSS may have capped a saved height), not what was saved
    return sc?.getBoundingClientRect().height ?? height ?? 230;
  };
  const clamp = (h: number) => Math.max(MIN, Math.min(maxH(), h));
  return (
    <div ref={ref} className="split-h" role="separator" aria-orientation="horizontal" tabIndex={0}
      aria-label="Resize the timeline" aria-valuenow={Math.round(current())} aria-valuemin={MIN} aria-valuemax={maxH()}
      title="Drag to give the canvas or the timeline more room; double-click to reset"
      onMouseDown={(e) => {
        e.preventDefault();
        const y0 = e.clientY, h0 = current();
        const move = (ev: MouseEvent) => onHeight(clamp(h0 + (y0 - ev.clientY)));
        const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
      }}
      onDoubleClick={() => onHeight(null)}
      onKeyDown={(e) => {
        if (e.key === "ArrowUp" || e.key === "ArrowDown") {
          e.preventDefault();
          e.stopPropagation();
          onHeight(clamp(current() + (e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 80 : 20)));
        } else if (e.key === "Home") { e.preventDefault(); e.stopPropagation(); onHeight(null); }
      }} />
  );
}
