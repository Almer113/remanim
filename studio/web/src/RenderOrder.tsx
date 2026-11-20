// Render order (Phase 7 step 1): the file's scene order, moved one place at a
// time with ↑ ↓. Each move is one edit (the file's SCENES list), so one undo
// step. The ◀ ▶ arrows in the header only go to the previous / next scene.
import { useEffect, useRef } from "react";

export function RenderOrderDialog({ names, current, canEdit, onMove, onClose }: {
  names: string[]; current: string | null; canEdit: boolean;
  onMove: (order: string[]) => void; onClose: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => { boxRef.current?.focus(); }, []);
  const move = (i: number, d: number) => {
    const order = [...names];
    const [n] = order.splice(i, 1);
    order.splice(i + d, 0, n);
    onMove(order);
  };
  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal order" role="dialog" aria-modal="true" aria-labelledby="order-title" tabIndex={-1} ref={boxRef}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } }}>
        <h4 id="order-title">Render order</h4>
        <p className="muted">The order Export and plain <code>manim -a</code> use (the file's <code>SCENES</code> list). Each move is one undo step.</p>
        <ol className="order-list">
          {names.map((n, i) => (
            <li key={n} className={n === current ? "on" : ""}>
              <span className="name">{n}</span>
              <button disabled={!canEdit || i === 0} onClick={() => move(i, -1)} aria-label={`Move ${n} earlier`} title="Earlier">↑</button>
              <button disabled={!canEdit || i === names.length - 1} onClick={() => move(i, 1)} aria-label={`Move ${n} later`} title="Later">↓</button>
            </li>
          ))}
        </ol>
        <div className="btns"><button onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}
