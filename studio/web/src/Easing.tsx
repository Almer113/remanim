import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/** Manim's named rate functions, re-implemented for drawing only (the code
 * gets the name; the studio never writes a curve of its own). */
const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));
const smooth = (t: number, k = 10) => {
  const e = sigmoid(-k / 2);
  return Math.min(Math.max((sigmoid(k * (t - 0.5)) - e) / (1 - 2 * e), 0), 1);
};
const thereAndBack = (t: number) => (t < 0.5 ? smooth(2 * t) : smooth(2 - 2 * t));
const bounceOut = (t: number) => {
  const n1 = 7.5625, d1 = 2.75;
  if (t < 1 / d1) return n1 * t * t;
  if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
  if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
  return n1 * (t -= 2.625 / d1) * t + 0.984375;
};

export const CURVES: Record<string, (t: number) => number> = {
  smooth,
  linear: (t) => t,
  rush_into: (t) => 2 * smooth(t / 2),
  rush_from: (t) => 2 * smooth(t / 2 + 0.5) - 1,
  slow_into: (t) => Math.sqrt(1 - (1 - t) * (1 - t)),
  double_smooth: (t) => (t < 0.5 ? 0.5 * smooth(2 * t) : 0.5 * (1 + smooth(2 * t - 1))),
  there_and_back: thereAndBack,
  wiggle: (t) => thereAndBack(t) * Math.sin(2 * Math.PI * t),
  ease_in_sine: (t) => 1 - Math.cos((t * Math.PI) / 2),
  ease_out_sine: (t) => Math.sin((t * Math.PI) / 2),
  ease_in_out_sine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
  ease_in_quad: (t) => t * t,
  ease_out_quad: (t) => 1 - (1 - t) * (1 - t),
  ease_in_out_cubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  ease_in_expo: (t) => (t === 0 ? 0 : Math.pow(2, 10 * t - 10)),
  ease_out_expo: (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  ease_in_back: (t) => 2.70158 * t * t * t - 1.70158 * t * t,
  ease_out_back: (t) => 1 + 2.70158 * Math.pow(t - 1, 3) + 1.70158 * Math.pow(t - 1, 2),
  ease_out_bounce: bounceOut,
  ease_out_elastic: (t) => (t === 0 || t === 1 ? t : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1),
};

const W = 64, H = 44, PAD = 8;

function path(fn: (t: number) => number) {
  let d = "";
  for (let i = 0; i <= 40; i++) {
    const t = i / 40;
    const x = PAD / 2 + t * (W - PAD);
    const y = H - PAD - fn(t) * (H - 2 * PAD);
    d += `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }
  return d;
}

function Curve({ name, active, playing }: { name: string; active: boolean; playing: boolean }) {
  const fn: ((t: number) => number) | undefined = CURVES[name];
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!playing) { setT(0); return; }
    let raf = 0;
    const t0 = performance.now();
    const tick = () => {
      setT(((performance.now() - t0) / 1200) % 1);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
  const v = fn ? fn(t) : t;
  return (
    <svg width={W} height={H} className={active ? "on" : ""}>
      <rect x={PAD / 2} y={PAD} width={W - PAD} height={H - 2 * PAD} className="frame" />
      {fn && <path d={path(fn)} />}
      {playing && !!fn && <circle cx={PAD / 2 + t * (W - PAD)} cy={H - PAD - v * (H - 2 * PAD)} r={2.6} />}
      {/* the moving object: where the clip is at time t */}
      {playing && !!fn && <rect x={W - 6} y={H - PAD - v * (H - 2 * PAD) - 2} width={4} height={4} className="obj" />}
    </svg>
  );
}

interface Props {
  value: string | null;        // the clip's rate function, by name
  fallback: string | null;     // the animation's default
  disabled: boolean;
  onPick: (name: string) => void;
}

/** A grid of easing curves; hover plays the curve, click writes rate_func=. */
export function EasingPicker({ value, fallback, disabled, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const current = value ?? fallback ?? "smooth";
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      const t = e.target as Node;
      if (box.current?.contains(t) || grid.current?.contains(t)) return;
      setOpen(false);
    };
    // Escape closes the grid only (the app's Escape would also clear the selection)
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopImmediatePropagation(); setOpen(false); } };
    const close = () => setOpen(false);
    window.addEventListener("mousedown", away);
    window.addEventListener("keydown", esc, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("mousedown", away);
      window.removeEventListener("keydown", esc, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);
  const names = Object.keys(CURVES);
  // the grid lives on <body> (the inspector is under the timeline's stacking)
  // and opens upward when there's no room below the button
  const toggle = () => {
    if (open) { setOpen(false); return; }
    const r = box.current!.getBoundingClientRect();
    const rows = Math.ceil((names.length + 1) / 4), h = rows * 76 + 14, w = 4 * 80 + 14;
    const top = r.bottom + h > window.innerHeight - 8 ? Math.max(8, r.top - h - 4) : r.bottom + 4;
    setPos({ left: Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)), top });
    setOpen(true);
  };
  return (
    <div className="easing" ref={box}>
      <button className="easing-btn" disabled={disabled} onClick={toggle}
        title="Pick an easing curve (writes rate_func=)">
        <Curve name={current} active playing={false} /><span>{current}{value ? "" : " (default)"}</span>
      </button>
      {open && pos && createPortal(
        <div className="easing-grid" role="listbox" ref={grid} style={{ left: pos.left, top: pos.top }}>
          {[...new Set([...(CURVES[current] ? [] : [current]), ...names])].map((n) => (
            <button key={n} role="option" aria-selected={n === current} className={n === current ? "on" : ""}
              onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)}
              onClick={() => { setOpen(false); if (n !== current) onPick(n); }}>
              <Curve name={n} active={n === current} playing={hover === n} />
              <span>{n.replace(/_/g, " ")}</span>
            </button>
          ))}
        </div>, document.body
      )}
    </div>
  );
}
