// Snapping for canvas drags: lines in scene units that a moving box's
// centre or edges stick to. The fixed ones follow style.py (safe area,
// REGIONS, grid_point on a 6 x 6 grid); other objects add their own.

export interface Lines {
  x: number[]; y: number[];    // centre lines: a box's centre sticks to them
  ex: number[]; ey: number[];  // edge lines: a box's edges stick to them
}
export interface Box { x0: number; y0: number; x1: number; y1: number }  // scene units, y up

const SAFE_X = 6.5;
const SAFE_Y = 3.5;
const GRID = 6;

/** Frame centre, region centres and grid_point cells; the safe area's edges. */
export function fixedLines(): Lines {
  const x = [0, -3.4, 3.4];
  const y = [0, 3.0, -0.15, -3.2];
  for (let i = 0; i < GRID; i++) {
    x.push(-SAFE_X + ((2 * SAFE_X) / GRID) * (i + 0.5));
    y.push(SAFE_Y - ((2 * SAFE_Y) / GRID) * (i + 0.5));
  }
  return { x, y, ex: [-SAFE_X, SAFE_X], ey: [-SAFE_Y, SAFE_Y] };
}

/** Other objects: centre to centre, edge to edge. */
export function objectLines(items: { box: Box; c: [number, number] }[]): Lines {
  const out: Lines = { x: [], y: [], ex: [], ey: [] };
  for (const { box: b, c } of items) {
    out.x.push(c[0]);
    out.y.push(c[1]);
    out.ex.push(b.x0, b.x1);
    out.ey.push(b.y0, b.y1);
  }
  return out;
}

export function joinLines(a: Lines, b: Lines): Lines {
  return { x: [...a.x, ...b.x], y: [...a.y, ...b.y], ex: [...a.ex, ...b.ex], ey: [...a.ey, ...b.ey] };
}

export interface Snap { d: number; line: number | null }

/** The shift (within `tol` units) that puts one of `feats` on one of `lines`. */
export function snap1(pairs: [number[], number[]][], tol: number): Snap {
  let best: Snap = { d: 0, line: null };
  let bestErr = tol;
  for (const [feats, lines] of pairs) {
    for (const f of feats) {
      for (const l of lines) {
        const e = Math.abs(l - f);
        if (e < bestErr) {
          bestErr = e;
          best = { d: l - f, line: l };
        }
      }
    }
  }
  return best;
}

/** Snap a moved box with centre `c`: the corrected offset and the guide lines hit.
 * `axes` limits snapping to one axis (Shift locks the drag to it). */
export function snapMove(box: Box, c: [number, number], dx: number, dy: number, lines: Lines, tol: number,
  axes: "xy" | "x" | "y" = "xy") {
  const b = { x0: box.x0 + dx, x1: box.x1 + dx, y0: box.y0 + dy, y1: box.y1 + dy };
  const none: Snap = { d: 0, line: null };
  const sx = axes === "y" ? none : snap1([[[c[0] + dx], lines.x], [[b.x0, b.x1], lines.ex]], tol);
  const sy = axes === "x" ? none : snap1([[[c[1] + dy], lines.y], [[b.y0, b.y1], lines.ey]], tol);
  return { dx: dx + sx.d, dy: dy + sy.d, gx: sx.line, gy: sy.line };
}

/** Round a drag to what a person would type: 0.05 units, 0.05x, 1 degree. */
export const tidy = {
  dist: (v: number) => Math.round(v * 20) / 20,
  /** a snapped distance: exact, but no more digits than a person would write */
  snapped: (v: number) => Math.round(v * 1000) / 1000,
  k: (v: number, fine: boolean) => Math.max(0.05, fine ? Math.round(v * 100) / 100 : Math.round(v * 20) / 20),
  deg: (v: number, fine: boolean) => (fine ? Math.round(v) : Math.round(v / 15) * 15),
};
