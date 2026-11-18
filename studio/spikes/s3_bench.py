"""Spike S3 benchmark: does a click resolve to the right line of code?

At sampled times, every drawn object is "clicked" once:
  1. ID buffer: each drawn leaf is repainted in a unique flat colour and the
     frame is drawn again; a pixel whose 3x3 neighbourhood is one ID colour
     is a click on that leaf (antialiased edges are ignored).
  2. The leaf is resolved with identity.resolve().
  3. Check: the source text of the resolved call contains the class name of
     the selected object (or one of its base classes), or `.copy(`. Factory
     results (Axes.plot and the like) are listed for review.
Stability: the scene is replayed twice; the selected (site, occurrence)
must be the same both times.

  .venv/Scripts/python studio/spikes/s3_bench.py order_matters.py [Scene ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_engine import ROOT, FrameEngine  # noqa: E402
from identity import OriginTracker, parent_map, resolve  # noqa: E402
from manim import ImageMobject, VMobject  # noqa: E402

OUT = ROOT / "media" / "studio_spikes" / "s3"


def id_color(i: int) -> tuple[int, int, int]:
    v = (i + 1) * 2654435761 % (1 << 24)  # spread ids over the colour cube
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def drawn_leaves(scene):
    mobs = []
    for m in scene.get_mobject_family_members():
        if isinstance(m, ImageMobject):
            mobs.append(m)
        elif isinstance(m, VMobject) and len(m.points) > 0:
            fill = m.get_fill_opacities()
            stroke = m.get_stroke_opacities()
            vis_fill = len(fill) and float(np.max(fill)) > 0.02
            vis_stroke = m.get_stroke_width() > 0 and len(stroke) and float(np.max(stroke)) > 0.02
            if vis_fill or vis_stroke:
                mobs.append(m)
    return mobs


def id_buffer(scene, leaves) -> tuple[np.ndarray, dict]:
    """Repaint leaves in ID colours, draw, return (frame, colour -> leaf)."""
    table = {}
    keep = {id(m) for m in leaves}
    for m in scene.get_mobject_family_members():
        if isinstance(m, VMobject) and id(m) not in keep:
            m.set_fill(opacity=0, family=False)
            m.set_stroke(opacity=0, family=False)
            m.set_stroke(width=0, background=True, family=False)
    for i, m in enumerate(leaves):
        c = id_color(i)
        table[c] = m
        hexc = "#%02x%02x%02x" % c
        if isinstance(m, ImageMobject):
            m.pixel_array[:, :, :3] = c
            continue
        vis_fill = float(np.max(m.get_fill_opacities())) > 0.02
        vis_stroke = m.get_stroke_width() > 0 and float(np.max(m.get_stroke_opacities())) > 0.02
        m.set_fill(hexc, opacity=1 if vis_fill else 0, family=False)
        m.set_stroke(hexc, opacity=1 if vis_stroke else 0, family=False)
        m.set_stroke(width=0, background=True, family=False)
        m.set_sheen(0, family=False) if hasattr(m, "set_sheen") else None
    cam = scene.renderer.camera
    if hasattr(cam, "should_apply_shading"):
        cam.should_apply_shading = False
    cam.background = np.zeros_like(cam.background)
    cam.background[:, :, 3] = 255
    scene.renderer.static_image = None
    scene.renderer.update_frame(scene, ignore_skipping=True)
    return scene.renderer.get_frame(), table


def interior_hits(frame, table) -> dict[int, tuple[int, int]]:
    """leaf id -> one interior pixel (y, x)."""
    f = frame[:, :, :3].astype(np.int32)
    code = (f[:, :, 0] << 16) | (f[:, :, 1] << 8) | f[:, :, 2]
    # a pixel of an exact ID colour with at least 2 same-coloured neighbours
    # (thin lines count; a lone blended edge pixel doesn't)
    n_same = np.zeros(code.shape, np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                n_same += code == np.roll(np.roll(code, dy, 0), dx, 1)
    same = n_same >= 2
    hits = {}
    lookup = {(c[0] << 16) | (c[1] << 8) | c[2]: m for c, m in table.items()}
    ys, xs = np.nonzero(same & (code != 0))
    for y, x in zip(ys, xs):
        m = lookup.get(int(code[y, x]))
        if m is not None and id(m) not in hits:
            hits[id(m)] = (int(y), int(x))
    return hits


def call_text(site) -> str:
    lines = Path(site.file).read_text(encoding="utf-8").splitlines()
    if site.line == site.end_line:
        return lines[site.line - 1][site.col:site.end_col or None]
    parts = [lines[site.line - 1][site.col:]] + lines[site.line:site.end_line - 1] + \
        [lines[site.end_line - 1][:site.end_col]]
    return "\n".join(parts)


def plausible(mob, origin) -> bool:
    text = call_text(origin.site)
    if ".copy(" in text and origin.copied_from is not None:
        return True
    names = [c.__name__ for c in type(mob).__mro__]
    return any(f"{n}(" in text for n in names)


def describe(mob) -> str:
    name = type(mob).__name__
    txt = getattr(mob, "text", None) or getattr(mob, "tex_string", None)
    return f"{name} {txt[:24]!r}" if isinstance(txt, str) else name


def selections(eng, scene_name, t):
    eng_tracker.reset_counts()
    _, scene = eng._run(scene_name, t, None)
    parents = parent_map(scene)
    leaves = drawn_leaves(scene)
    frame, table = id_buffer(scene, leaves)
    hits = interior_hits(frame, table)
    out = []
    for m in leaves:
        if id(m) not in hits:
            continue  # fully covered, or too thin to click
        sel, origin, how = resolve(m, parents)
        out.append((m, sel, origin, how, hits[id(m)]))
    return out, len(leaves)


def main() -> int:
    global eng_tracker
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("scenes", nargs="*")
    ap.add_argument("--n", type=int, default=6)
    args = ap.parse_args()
    path = (ROOT / args.file).resolve()
    eng_tracker = OriginTracker([path])
    eng = FrameEngine(args.file)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name in args.scenes or eng.scenes():
        events = eng.trace(name)
        total = events[-1][0] + events[-1][1]
        times = [round(total * (k + 0.5) / args.n * 15) / 15 + 1e-4 for k in range(args.n)]
        stats = Counter()
        bad, factory, seen = [], [], {}
        for t in times:
            a, n_leaves = selections(eng, name, t)
            b, _ = selections(eng, name, t)
            stats["drawn"] += n_leaves
            key = lambda r: (r[2].site.key(), r[2].occurrence) if r[2] and r[2].site else \
                (r[2].user_site.key() if r[2] and r[2].user_site else None)
            ka, kb = [key(r) for r in a], [key(r) for r in b]
            stats["stable"] += sum(x == y for x, y in zip(ka, kb)) if len(ka) == len(kb) else 0
            for leaf, sel, origin, how, px in a:
                stats["clicked"] += 1
                stats[how] += 1
                if how == "primary":
                    if plausible(sel, origin):
                        stats["right"] += 1
                    else:
                        bad.append(f"t={t:.2f} {describe(leaf)} -> {describe(sel)} @ {origin.site}: "
                                   f"{call_text(origin.site)[:60]!r}")
                    seen.setdefault(str(origin.site), describe(sel))
                elif how == "factory":
                    stats["right"] += 1  # the user's line that built it (listed for review)
                    factory.append(f"t={t:.2f} {describe(leaf)} @ {origin.user_site}: "
                                   f"{call_text(origin.user_site)[:60]!r}")
                else:
                    bad.append(f"t={t:.2f} {describe(leaf)} -> unknown")
        clicked = stats["clicked"] or 1
        r = {k: stats[k] for k in ("drawn", "clicked", "primary", "factory", "unknown", "right", "stable")}
        r["right_pct"] = round(100 * stats["right"] / clicked, 1)
        r["stable_pct"] = round(100 * stats["stable"] / clicked, 1)
        report[name] = {**r, "bad": bad[:30], "factory": sorted(set(factory))[:30],
                        "selectable": seen}
        print(f"{name:15} drawn {r['drawn']:4} clicked {r['clicked']:4} | primary {r['primary']:4}"
              f" factory {r['factory']:3} unknown {r['unknown']:3} | right {r['right_pct']}%"
              f" stable {r['stable_pct']}%", flush=True)
        for line in bad[:6]:
            print("   BAD", line)
        for line in sorted({f.split(" @ ", 1)[1] for f in factory})[:8]:
            print("   FACTORY", line)
    (OUT / f"{path.stem}.json").write_text(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
