import { useEffect, useRef, useState } from "react";
import type { Obj } from "./types";

interface Props {
  url: string;
  idmapUrl: string | null;
  width: number;
  height: number;
  objects: Obj[];
  selected: string | null;
  onSelect: (o: Obj | null) => void;
  stale: boolean;
}

/** The real Manim frame, with hover and selection resolved in the browser
 * from the ID map (one colour per selectable object, architecture.md §6). */
export function Canvas({ url, idmapUrl, width, height, objects, selected, onSelect, stale }: Props) {
  const [shown, setShown] = useState<string | null>(null);
  const [hover, setHover] = useState<Obj | null>(null);
  const ids = useRef<ImageData | null>(null);
  const overlay = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);

  // swap images only once the next one has loaded: no flashing while scrubbing
  useEffect(() => {
    let gone = false;
    const img = new Image();
    img.onload = () => { if (!gone) setShown(url); };
    img.src = url;
    return () => { gone = true; };
  }, [url]);

  useEffect(() => {
    ids.current = null;
    if (!idmapUrl) return;
    let gone = false;
    const img = new Image();
    img.onload = () => {
      if (gone) return;
      const c = document.createElement("canvas");
      c.width = img.width;
      c.height = img.height;
      const ctx = c.getContext("2d", { willReadFrequently: true })!;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(img, 0, 0);
      ids.current = ctx.getImageData(0, 0, img.width, img.height);
    };
    img.src = idmapUrl;
    return () => { gone = true; };
  }, [idmapUrl]);

  // draw hover and selection boxes
  useEffect(() => {
    const c = overlay.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, c.width, c.height);
    const box = (o: Obj, color: string, dash: number[]) => {
      if (!o.box) return;
      const [x0, y0, x1, y1] = o.box;
      ctx.setLineDash(dash);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x0 - 2.5, y0 - 2.5, x1 - x0 + 5, y1 - y0 + 5);
    };
    const s = objects.find((o) => o.id === selected);
    if (hover && hover.id !== selected) box(hover, "rgba(120,180,255,0.8)", [4, 3]);
    if (s) {
      box(s, "#2f7de1", []);
      if (s.box) {
        ctx.fillStyle = "#2f7de1";
        ctx.font = "11px system-ui";
        const label = `${s.name ?? s.class} · ${s.class}`;
        ctx.fillText(label, s.box[0], Math.max(11, s.box[1] - 6));
      }
    }
  }, [objects, selected, hover]);

  const pick = (e: React.MouseEvent): Obj | null => {
    const d = ids.current;
    const el = wrap.current;
    if (!d || !el) return null;
    const r = el.getBoundingClientRect();
    const x = Math.floor(((e.clientX - r.left) / r.width) * d.width);
    const y = Math.floor(((e.clientY - r.top) / r.height) * d.height);
    // exact pixel first, then the nearest object within 4 px (thin lines)
    for (let rad = 0; rad <= 4; rad++) {
      for (let dy = -rad; dy <= rad; dy++) {
        for (let dx = -rad; dx <= rad; dx++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== rad) continue;
          const px = x + dx, py = y + dy;
          if (px < 0 || py < 0 || px >= d.width || py >= d.height) continue;
          const i = (py * d.width + px) * 4;
          const idx = (d.data[i] << 16) | (d.data[i + 1] << 8) | d.data[i + 2];
          if (idx > 0 && idx <= objects.length) return objects[idx - 1];
        }
      }
    }
    return null;
  };

  return (
    <div className={`canvas ${stale ? "stale" : ""}`} ref={wrap}
      style={{ aspectRatio: `${width} / ${height}` }}
      onMouseMove={(e) => setHover(pick(e))}
      onMouseLeave={() => setHover(null)}
      onClick={(e) => onSelect(pick(e))}>
      {shown && <img src={shown} alt="frame" draggable={false} />}
      <canvas ref={overlay} width={width} height={height} />
      {hover && <div className="hover-tag">{hover.name ?? hover.class}</div>}
    </div>
  );
}
