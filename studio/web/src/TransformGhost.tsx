import { useEffect, useState } from "react";
import type { Ghost } from "./types";

// one colour per matched pair; source and target share it
const PAIR = ["#58C4DD", "#FFFF00", "#83C167", "#FC6255", "#FF862F", "#C55F73", "#9A72AC", "#5CD0B3"];

type Box = [number, number, number, number];

/** Where a transform is going (Phase 5 step 8): the target's outline, and for
 * TransformMatchingTex each matched part on both sides in one colour.
 * Unmatched parts are grey; click one on each side to match them
 * ("match these" writes key_map=). Drawn over the frame inside the play. */
export function TransformGhost({ ghosts, frameW, frameH, frameX = 0, frameY = 0, onMatch }: {
  ghosts: Ghost[];
  frameW: number;
  frameH: number;
  frameX?: number;
  frameY?: number;
  onMatch: ((index: number, sourceKey: string, targetKey: string) => void) | null;
}) {
  const [picked, setPick] = useState<{ index: number; key: string } | null>(null);
  // a half-made match only lasts while its part is still there unmatched (frames and edits move on)
  const pick = picked && ghosts.some((g) => g.index === picked.index
    && g.unmatched_source?.some((u) => u.key === picked.key)) ? picked : null;
  useEffect(() => {
    if (!pick) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); setPick(null); }
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [pick?.index, pick?.key]); // eslint-disable-line react-hooks/exhaustive-deps
  const pct = (b: Box, pad = 0.04): React.CSSProperties => ({
    left: `${((b[0] - pad - frameX) / frameW + 0.5) * 100}%`, top: `${(0.5 - (b[3] + pad - frameY) / frameH) * 100}%`,
    width: `${((b[2] - b[0] + 2 * pad) / frameW) * 100}%`, height: `${((b[3] - b[1] + 2 * pad) / frameH) * 100}%`,
  });
  return (
    <div className="ghost-layer">
      {ghosts.map((g) => {
        if (!g.pairs) {
          return g.target && (
            <div key={g.index} className="ghost-target" style={pct(g.target as Box)}>
              <span className="ghost-tag">{g.kind} → here</span>
            </div>
          );
        }
        const canMatch = !!onMatch && g.keys;
        return (
          <div key={g.index}>
            {g.pairs.map((p, k) => {
              const c = PAIR[k % PAIR.length];
              const title = p.key ? (p.to ? `${p.key} → ${p.to} (key_map)` : p.key) : "matched by shape";
              return [p.source, p.target].map((b, side) => b && (
                <div key={`${k}:${side}`} className={`ghost-part ${p.mapped ? "mapped" : ""}`} title={title}
                  style={{ ...pct(b as Box, 0.02), borderColor: c }} />
              ));
            })}
            {g.unmatched_source?.map((u, k) => u.box && (
              <div key={`s${k}`} title={canMatch ? `${u.key}: not matched. Click, then click its partner in the target` : `${u.key ?? "part"} fades out`}
                className={`ghost-part loose ${canMatch ? "pickable" : ""} ${pick?.index === g.index && pick.key === u.key ? "on" : ""}`}
                style={pct(u.box as Box, 0.02)}
                onMouseDown={(e) => { if (!canMatch || u.key == null) return; e.stopPropagation(); e.preventDefault();
                  setPick(pick?.key === u.key ? null : { index: g.index, key: u.key }); }} />
            ))}
            {g.unmatched_target?.map((u, k) => u.box && (
              <div key={`t${k}`} title={canMatch ? (pick ? `match ${pick.key} → ${u.key}` : `${u.key}: not matched. Pick a source part first`) : `${u.key ?? "part"} fades in`}
                className={`ghost-part loose target ${canMatch && pick?.index === g.index ? "pickable" : ""}`}
                style={pct(u.box as Box, 0.02)}
                onMouseDown={(e) => { if (!canMatch || !pick || pick.index !== g.index || u.key == null) return;
                  e.stopPropagation(); e.preventDefault(); onMatch!(g.index, pick.key, u.key); setPick(null); }} />
            ))}
            {g.target && <div className="ghost-target faint" style={pct(g.target as Box)}>
              <span className="ghost-tag">{g.kind}{canMatch && (g.unmatched_source?.length ?? 0) > 0 && (g.unmatched_target?.length ?? 0) > 0
                ? (pick ? ` · now click its partner in the target` : " · grey parts aren't matched: click one, then its partner") : ""}</span>
            </div>}
          </div>
        );
      })}
    </div>
  );
}
