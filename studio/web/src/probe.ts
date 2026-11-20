// UI frame-time probe (Phase 7 step 15). Idle until started from the console
// or a test: window.__frameProbe.start(), scrub, then .stop() gives the time
// between animation frames (render, layout and paint), in ms.

type Stats = { frames: number; median: number; p95: number; max: number; over50: number; hidden: boolean };

let times: number[] = [];
let last = 0;
let raf = 0;
let sawHidden = false;

function tick(now: number) {
  if (last) times.push(now - last);
  last = now;
  if (document.hidden) sawHidden = true;
  raf = requestAnimationFrame(tick);
}

function pct(xs: number[], p: number): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(p * (s.length - 1)))];
}

export const frameProbe = {
  start() {
    cancelAnimationFrame(raf);
    times = []; last = 0; sawHidden = document.hidden;
    raf = requestAnimationFrame(tick);
  },
  stop(): Stats {
    cancelAnimationFrame(raf);
    raf = 0;
    const r = (x: number) => Math.round(x * 10) / 10;
    return {
      frames: times.length, median: r(pct(times, 0.5)), p95: r(pct(times, 0.95)),
      max: r(Math.max(0, ...times)), over50: times.filter((t) => t > 50).length,
      hidden: sawHidden,  // a hidden page throttles frames: such a run measures nothing
    };
  },
};

(window as unknown as { __frameProbe: typeof frameProbe }).__frameProbe = frameProbe;
