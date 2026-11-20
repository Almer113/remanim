// The bar between the canvas and the timeline (Phase 7 step 10): drag it to
// give one more room, double-click to go back to the default share. Arrow
// keys move it too. The height is remembered in this browser.
import { useRef } from "react";

const MIN = 40;
const maxH = () => Math.round(window.innerHeight * 0.7);

export function Splitter({ height, onHeight }: { height: number | null; onHeight: (h: number | null) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const current = () => {
    const sc = ref.current?.parentElement?.querySelector(".tl-scroll") as HTMLElement | null;
    return height ?? sc?.getBoundingClientRect().height ?? 230;
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
        } else if (e.key === "Home") { e.preventDefault(); onHeight(null); }
      }} />
  );
}
