import { useEffect, useRef, useState } from "react";
import type { CameraState } from "./types";

const DEG_PER_PX = 0.35;   // orbit speed
const WHEEL = 1.1;         // zoom per wheel notch
const IDLE_MS = 450;       // wheel zoom is sent this long after the last notch

/** Camera on the canvas (Phase 5 steps 9, 10). 2D: drag pans, wheel zooms;
 * the frame previews the move, and the edit is sent on release. 3D: drag
 * orbits (left/right theta, up/down phi), wheel zooms, with a readout. */
export function CameraGizmo({ cam, img, onCommit, onClose }: {
  cam: CameraState;
  img: React.RefObject<HTMLImageElement | null>;
  onCommit: (m: object) => void;
  onClose: () => void;
}) {
  const layer = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ x0: number; y0: number; x: number; y: number } | null>(null);
  const [zoom, setZoom] = useState(1);       // preview zoom factor (>1 closer)
  const idle = useRef<number | null>(null);
  const zoomRef = useRef(1);
  const dragRef = useRef(drag);
  dragRef.current = drag;

  // the preview: move/scale the frame image itself (2D only)
  const dx = drag ? drag.x - drag.x0 : 0, dy = drag ? drag.y - drag.y0 : 0;
  useEffect(() => {
    const el = img.current;
    if (!el) return;
    el.style.transform = cam.kind === "2d" && (dx || dy || zoom !== 1) ? `translate(${dx}px, ${dy}px) scale(${zoom})` : "";
    return () => { el.style.transform = ""; };
  }, [img, cam.kind, dx, dy, zoom]);
  useEffect(() => () => { if (idle.current) window.clearTimeout(idle.current); }, []);
  // Esc closes camera mode (before App's Escape, which would clear the selection)
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); onClose(); }
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [onClose]);
  // a drag follows the mouse outside the canvas too, and is sent wherever it ends
  const dragging = drag !== null;
  useEffect(() => {
    if (!dragging) return;
    const move = (e: MouseEvent) => {
      const r = size();
      setDrag((d) => d && { ...d, x: e.clientX - r.left, y: e.clientY - r.top });
    };
    const up = () => {
      const d = dragRef.current;
      setDrag(null);
      if (d && Math.hypot(d.x - d.x0, d.y - d.y0) > 2) commit(d.x - d.x0, d.y - d.y0, 1);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
  }, [dragging]); // eslint-disable-line react-hooks/exhaustive-deps

  const size = () => layer.current!.getBoundingClientRect();
  const commit = (ddx: number, ddy: number, z: number) => {
    const r = size();
    if (cam.kind === "2d") {
      const ux = cam.width / r.width, uy = cam.height / r.height;
      const m: { center?: number[]; width?: number } = {};
      if (ddx || ddy) m.center = [cam.center[0] - ddx * ux / z, cam.center[1] + ddy * uy / z];
      if (z !== 1) m.width = cam.width / z;
      if (m.center || m.width) onCommit(m);
    } else {
      const m: Record<string, number> = {};
      if (ddx) m.theta = round(cam.theta - ddx * DEG_PER_PX, 1);
      if (ddy) m.phi = round(Math.min(180, Math.max(0, cam.phi - ddy * DEG_PER_PX)), 1);
      if (z !== 1) m.zoom = round(cam.zoom * z, 3);
      if (Object.keys(m).length) onCommit(m);
    }
  };
  const live = cam.kind === "3d" && drag ? {
    theta: cam.theta - dx * DEG_PER_PX, phi: Math.min(180, Math.max(0, cam.phi - dy * DEG_PER_PX)), zoom: cam.zoom * zoom,
  } : cam.kind === "3d" ? { theta: cam.theta, phi: cam.phi, zoom: cam.zoom * zoom } : null;

  return (
    <div ref={layer} className="camera-layer"
      onMouseDown={(e) => {
        e.stopPropagation(); e.preventDefault();
        if (idle.current) {
          // a zoom is still waiting to be sent: send it now, the pan comes after its frame
          window.clearTimeout(idle.current); idle.current = null;
          const zz = zoomRef.current; zoomRef.current = 1; setZoom(1); commit(0, 0, zz);
          return;
        }
        const r = size();
        setDrag({ x0: e.clientX - r.left, y0: e.clientY - r.top, x: e.clientX - r.left, y: e.clientY - r.top }); }}
      onDoubleClick={(e) => e.stopPropagation()}
      onWheel={(e) => {
        e.stopPropagation();
        const z = zoomRef.current * (e.deltaY < 0 ? WHEEL : 1 / WHEEL);  // a ref: notches between renders add up
        zoomRef.current = z;
        setZoom(z);
        if (idle.current) window.clearTimeout(idle.current);
        idle.current = window.setTimeout(() => {
          idle.current = null; const zz = zoomRef.current; zoomRef.current = 1; setZoom(1); commit(0, 0, zz);
        }, IDLE_MS);
      }}>
      <div className="camera-hud">
        {cam.kind === "2d"
          ? <>Camera: drag to pan, scroll to zoom{zoom !== 1 ? ` · width ${(cam.width / zoom).toFixed(2)}` : ""}</>
          : <>Orbit: drag (θ {live!.theta.toFixed(1)}°, φ {live!.phi.toFixed(1)}°), scroll to zoom ({live!.zoom.toFixed(2)})</>}
        <button onMouseDown={(e) => e.stopPropagation()} onClick={onClose}>Done</button>
      </div>
      {cam.kind === "3d" && <Orbit theta={live!.theta} phi={live!.phi} />}
    </div>
  );
}

function round(v: number, d: number) { const k = 10 ** d; return Math.round(v * k) / k; }

/** A small axis tripod showing where the camera is looking from. */
function Orbit({ theta, phi }: { theta: number; phi: number }) {
  const t = (theta * Math.PI) / 180, p = (phi * Math.PI) / 180;
  // Manim's camera: x, y, z axes projected for (phi, theta)
  const proj = (v: [number, number, number]): [number, number] => {
    const [x, y, z] = v;
    const x1 = -Math.sin(t) * x + Math.cos(t) * y;   // screen right
    const d = Math.cos(t) * x + Math.sin(t) * y;
    const y1 = Math.sin(p) * z - Math.cos(p) * d;     // screen up
    return [x1 * 26, -y1 * 26];
  };
  const axes: [string, [number, number, number], string][] = [["x", [1, 0, 0], "#fc6255"], ["y", [0, 1, 0], "#83c167"], ["z", [0, 0, 1], "#58c4dd"]];
  return (
    <svg className="orbit" viewBox="-40 -40 80 80" width={80} height={80}>
      <circle r={34} fill="rgba(24,27,34,.8)" stroke="rgba(255,255,255,.2)" />
      {axes.map(([n, v, c]) => { const [x, y] = proj(v); return (
        <g key={n}><line x1={0} y1={0} x2={x} y2={y} stroke={c} strokeWidth={2} />
          <text x={x * 1.18} y={y * 1.18 + 3} fill={c} fontSize={9} textAnchor="middle">{n}</text></g>); })}
    </svg>
  );
}
