import { useState } from "react";
import type { LibItem } from "./types";

// Mirrors studio/server/code/inserts.py (SHAPES, ENTRANCES, PRESETS).
const SHAPES: [string, string][] = [
  ["Circle", "○"], ["Square", "□"], ["Rectangle", "▭"], ["Triangle", "△"], ["RegularPolygon", "⬡"],
  ["Star", "☆"], ["Dot", "•"], ["Line", "—"], ["Arrow", "→"], ["Text", "T"], ["MathTex", "∑"], ["Blob", "◕"],
];
const ENTRANCES = ["", "Create", "Write", "FadeIn", "GrowFromCenter", "DrawBorderThenFill", "GrowArrow", "SpinInFromNothing"];
// Mirrors inserts.py COMPOSITES / ON_OBJECT.
const COMPOSITES: [string, string, boolean][] = [
  ["graph", "Axes + curve + label", false], ["number_line", "Number line + moving dot", false],
  ["vector", "Labelled vector", false], ["equation", "Equation reveal", false], ["title_card", "Title card", false],
  ["brace", "Brace + label", true], ["highlight", "Highlight box", true],
  ["surface", "3D surface (ThreeDScene)", false],
];
const PRESETS = ["Indicate", "Circumscribe", "Wiggle", "Flash", "ApplyWave", "FocusOn", "FadeOut", "Uncreate", "ShrinkToCenter"];

interface Props {
  disabled: boolean;
  hasSelection: boolean;
  /** click instead of drag: shapes go to the frame centre, presets onto the selection */
  onPick: (item: LibItem) => void;
}

export function Library({ disabled, hasSelection, onPick }: Props) {
  const [entrance, setEntrance] = useState("");
  const drag = (item: LibItem) => (e: React.DragEvent) => {
    e.dataTransfer.setData("application/x-studio", JSON.stringify(item));
    e.dataTransfer.effectAllowed = "copy";
  };
  const shape = (cls: string): LibItem => ({ kind: "shape", class: cls, ...(entrance ? { entrance } : {}) });
  return (
    <div className="library">
      <h4>Shapes <small>drag onto the canvas</small></h4>
      <div className="lib-grid">
        {SHAPES.map(([cls, icon]) => (
          <button key={cls} className="lib-item" draggable={!disabled} disabled={disabled}
            onDragStart={drag(shape(cls))} onClick={() => onPick(shape(cls))}
            title={`${cls}: drag to place it at a time and spot, or click for the centre at the playhead`}>
            <span className="lib-icon">{icon}</span>{cls === "RegularPolygon" ? "Polygon" : cls}
          </button>
        ))}
      </div>
      <div className="row small-gap">
        <label>Comes in with</label>
        <select value={entrance} onChange={(e) => setEntrance(e.target.value)} disabled={disabled}>
          {ENTRANCES.map((x) => <option key={x} value={x}>{x || "(its usual)"}</option>)}
        </select>
      </div>
      <h4>Animations <small>drop on an object</small></h4>
      <div className="lib-list">
        {PRESETS.map((p) => (
          <button key={p} className="lib-item wide" draggable={!disabled} disabled={disabled}
            onDragStart={drag({ kind: "preset", preset: p })}
            onClick={() => onPick({ kind: "preset", preset: p })}
            title={hasSelection ? `Play ${p} on the selection at the playhead` : `Drag onto an object, or select one first`}>
            {p}
          </button>
        ))}
      </div>
      <h4>Presets <small>several lines, one undo</small></h4>
      <div className="lib-list">
        {COMPOSITES.map(([id, label, onObject]) => {
          const item: LibItem = { kind: "composite", preset: id, onObject };
          return (
            <button key={id} className="lib-item wide" draggable={!disabled} disabled={disabled}
              onDragStart={drag(item)} onClick={() => onPick(item)}
              title={onObject ? `Drop on an object, or select one and click` : `Drag to place it, or click for the centre at the playhead`}>
              {label}
            </button>
          );
        })}
      </div>
      <div className="muted small-gap">Each drop becomes ordinary Manim code at the playhead's time, checked by a replay before it is written.</div>
    </div>
  );
}
