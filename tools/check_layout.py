"""Layout checker for Manim CE scenes — runs a scene *without rendering* and
flags layout problems.

For every self.play()/self.wait() it samples the scene halfway through and at
the end of the animation, then checks the visible objects for:

  ERROR  off-frame      object extends past the edge of the video frame
  ERROR  text-overlap   two pieces of text overlap each other
  WARN   unsafe-area    object outside the safe area defined in style.py
  WARN   text-on-shape  text partially overlaps a shape (not fully inside it)
  WARN   small-text     text smaller than MIN_FONT_SIZE (end states only)

In a ThreeDScene only objects pinned to the screen (fixed in frame: captions,
headings, formulas) are checked. Check 3D objects with frames.py.

Each problem is reported once, with the play number, the source line of the
self.play() call, and the variable name of the object when one can be found.

Usage:
  .venv\\Scripts\\python tools\\check_layout.py my_scene.py [SceneName ...]

Exit code: 0 = no errors, 1 = errors found, 2 = the scene crashed.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from manim import (  # noqa: E402
    DecimalNumber, Mobject, Paragraph, Scene, SingleStringMathTex, Text,
    MarkupText, VMobject, config, tempconfig,
)
from manim.manager import Manager  # noqa: E402

try:
    import style  # project palette / safe area
    SAFE_X, SAFE_Y, MIN_FONT = style.SAFE_X, style.SAFE_Y, style.MIN_FONT_SIZE
except Exception:  # style.py missing or broken — fall back to defaults
    SAFE_X, SAFE_Y, MIN_FONT = 6.5, 3.5, 20

TEXT_TYPES = (Text, MarkupText, Paragraph, SingleStringMathTex, DecimalNumber)
EPS = 0.02          # ignore overlaps thinner than this (touching edges)
MIN_OVERLAP = 0.15  # fraction of the smaller box that must overlap


@dataclass
class Issue:
    level: str
    kind: str
    message: str
    where: str


@dataclass
class Report:
    scene: str
    issues: dict[tuple, Issue] = field(default_factory=dict)

    def add(self, level, kind, key, message, where):
        k = (kind, key)
        if k not in self.issues:
            self.issues[k] = Issue(level, kind, message, where)


# ── geometry helpers ─────────────────────────────────────────────────────

def bbox(m: Mobject):
    pts = m.get_all_points() if hasattr(m, "get_all_points") else None
    if pts is None or len(pts) == 0:
        return None
    return (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())


def overlap_fraction(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= EPS or h <= EPS:
        return 0.0
    area_a = max((a[2] - a[0]) * (a[3] - a[1]), 1e-6)
    area_b = max((b[2] - b[0]) * (b[3] - b[1]), 1e-6)
    return (w * h) / min(area_a, area_b)


def contains(outer, inner) -> bool:
    return (outer[0] <= inner[0] + EPS and outer[1] <= inner[1] + EPS
            and outer[2] >= inner[2] - EPS and outer[3] >= inner[3] - EPS)


def visible(m: Mobject) -> bool:
    for sub in m.get_family():
        if isinstance(sub, VMobject):
            if sub.get_fill_opacity() > 0.05 or (
                sub.get_stroke_opacity() > 0.05 and sub.get_stroke_width() > 0
            ):
                if len(sub.points):
                    return True
        elif len(getattr(sub, "points", [])):
            return True
    return False


def text_leaves(m: Mobject, out: list):
    """Top-most text-like mobjects inside m (don't descend into glyphs)."""
    if isinstance(m, TEXT_TYPES):
        out.append(m)
        return
    for s in m.submobjects:
        text_leaves(s, out)


def shape_leaves(m: Mobject, out: list):
    """Visible childless mobjects that are not part of a text object."""
    if isinstance(m, TEXT_TYPES):
        return
    if not m.submobjects:
        if len(m.points) and visible(m):
            out.append(m)
        return
    for s in m.submobjects:
        shape_leaves(s, out)


def contains_text(m: Mobject) -> bool:
    found: list = []
    text_leaves(m, found)
    return bool(found)


def describe(m: Mobject, names: dict[int, str]) -> str:
    label = type(m).__name__
    content = (getattr(m, "original_text", None) or getattr(m, "text", None)
               or getattr(m, "tex_string", None))
    if isinstance(content, str):
        content = content.strip().replace("\n", " ")
        if len(content) > 30:
            content = content[:27] + "..."
        label += f' "{content}"'
    name = names.get(id(m))
    return f"{name} ({label})" if name else label


# ── scene instrumentation ────────────────────────────────────────────────

def make_names(frame) -> dict[int, str]:
    names: dict[int, str] = {}
    if frame is None:
        return names
    for k, v in frame.f_locals.items():
        if isinstance(v, Mobject) and k != "self":
            names.setdefault(id(v), k)
    return names


def check_state(scene: Scene, rep: Report, where: str, names, end_state: bool):
    fw, fh = config.frame_width / 2, config.frame_height / 2
    tops = [m for m in scene.mobjects if visible(m)]
    # 3D scene: objects in 3D space are projected by the camera, so their raw
    # coordinates say nothing about the screen. Check only what is pinned to
    # the screen (captions, headings, formulas); review the rest by frames.
    pinned = getattr(scene.camera, "fixed_in_frame_mobjects", None)
    if pinned is not None:
        tops = [m for m in tops if m in pinned] + [
            s for m in tops if m not in pinned for s in m.submobjects if s in pinned]

    # off-frame / unsafe area (top-level objects)
    for m in tops:
        b = bbox(m)
        if b is None:
            continue
        desc = describe(m, names)
        if b[0] < -fw or b[2] > fw or b[1] < -fh or b[3] > fh:
            rep.add("ERROR", "off-frame", id(m),
                    f"{desc} extends past the frame edge "
                    f"(x {b[0]:.2f}..{b[2]:.2f}, y {b[1]:.2f}..{b[3]:.2f}; "
                    f"frame is +/-{fw:.2f} x +/-{fh:.2f})", where)
        elif b[0] < -SAFE_X or b[2] > SAFE_X or b[1] < -SAFE_Y or b[3] > SAFE_Y:
            rep.add("WARN", "unsafe-area", id(m),
                    f"{desc} is outside the safe area +/-{SAFE_X} x +/-{SAFE_Y} "
                    f"(x {b[0]:.2f}..{b[2]:.2f}, y {b[1]:.2f}..{b[3]:.2f})", where)

    # text leaves
    texts: list = []
    for m in tops:
        text_leaves(m, texts)
    texts = [t for t in texts if visible(t)]
    boxes = {id(t): bbox(t) for t in texts}

    for i, a in enumerate(texts):
        ba = boxes[id(a)]
        if ba is None:
            continue
        if end_state:
            fs = getattr(a, "font_size", None)
            if isinstance(fs, (int, float)) and fs < MIN_FONT:
                rep.add("WARN", "small-text", id(a),
                        f"{describe(a, names)} has font size {fs:.0f} "
                        f"(minimum {MIN_FONT})", where)
        for b in texts[i + 1:]:
            bb = boxes[id(b)]
            if bb is None:
                continue
            frac = overlap_fraction(ba, bb)
            if frac >= MIN_OVERLAP:
                key = tuple(sorted((id(a), id(b))))
                rep.add("ERROR", "text-overlap", key,
                        f"{describe(a, names)} overlaps {describe(b, names)} "
                        f"({frac:.0%} of the smaller one)", where)

    # text partially over a non-text shape
    # Compare against individual visible shapes (leaves), not group boxes.
    shapes: list = []
    for m in tops:
        shape_leaves(m, shapes)
    for t in texts:
        bt = boxes[id(t)]
        if bt is None:
            continue
        for s in shapes:
            bs = bbox(s)
            if bs is None or contains(bs, bt):
                continue
            frac = overlap_fraction(bt, bs)
            if frac >= MIN_OVERLAP:
                key = id(t)  # one warning per text object is enough
                rep.add("WARN", "text-on-shape", key,
                        f"{describe(t, names)} partially overlaps "
                        f"{describe(s, names)} ({frac:.0%} of the smaller one)",
                        where)


def instrument(rep: Report, src_file: Path):
    state = {"n": 0}

    def caller_frame():
        for fr in inspect.stack()[1:]:
            if Path(fr.filename).resolve() == src_file:
                return fr
        return None

    def fake_play(self: Manager, *args, subcaption=None, subcaption_duration=None,
                  subcaption_offset=0, **kwargs):
        scene = self.scene
        state["n"] += 1
        fr = caller_frame()
        names = make_names(fr.frame if fr else None)
        where = f"play #{state['n']}" + (f" (line {fr.lineno})" if fr else "")
        scene.compile_animation_data(*args, **kwargs)
        scene.begin_animations()
        dur = scene.duration
        for frac in (0.5, 1.0):
            scene.update_to_time(dur * frac)
            check_state(scene, rep, where + (" mid-animation" if frac < 1 else ""),
                        names, end_state=frac == 1.0)
        for a in scene.animations:
            a.finish()
            a.clean_up_from_scene(scene)
        scene.update_mobjects(0)
        self.renderer.time += dur
        self.renderer.num_plays += 1

    orig_teardown = Manager.tear_down

    def fake_teardown(self: Manager):
        check_state(self.scene, rep, "end of scene", {}, end_state=True)
        orig_teardown(self)

    Manager.play = fake_play
    Manager.tear_down = fake_teardown


def load_scenes(path: Path, wanted: list[str]):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    scenes = [obj for name, obj in vars(mod).items()
              if inspect.isclass(obj) and issubclass(obj, Scene)
              and obj.__module__ == mod.__name__
              and "construct" in vars(obj)]  # skip helper base classes
    if wanted:
        scenes = [s for s in scenes if s.__name__ in wanted]
    return scenes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("scenes", nargs="*")
    args = ap.parse_args()
    path = Path(args.file).resolve()

    errors = crashed = 0
    with tempconfig({"dry_run": True, "disable_caching": True,
                     "quality": "low_quality", "verbosity": "ERROR",
                     "progress_bar": "none",
                     # own LaTeX cache: avoids file-lock clashes on Windows
                     # when the preview server compiles the same TeX at once
                     "tex_dir": str(ROOT / "media" / "Tex_check")}):
        scenes = load_scenes(path, args.scenes)
        if not scenes:
            print(f"No Scene classes found in {path.name}")
            return 2
        for cls in scenes:
            rep = Report(cls.__name__)
            instrument(rep, path)
            try:
                cls().render()
            except Exception:
                crashed += 1
                print(f"\n{cls.__name__}: CRASHED while running the scene")
                traceback.print_exc(limit=-3)
                continue
            issues = list(rep.issues.values())
            n_err = sum(i.level == "ERROR" for i in issues)
            errors += n_err
            status = "OK" if not issues else f"{n_err} error(s), {len(issues) - n_err} warning(s)"
            print(f"\n{cls.__name__}: {status}")
            for i in sorted(issues, key=lambda i: (i.level != "ERROR", i.where)):
                print(f"  {i.level:5} {i.kind:13} {i.where}: {i.message}")

    if crashed:
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
