"""Spike S3: which line of code made the thing under the mouse?

Every mobject records where it was created:
  site       - the exact call (file, line, end line, col, end col) that
               constructed it, if that call is in the scene file
               ("primary": the user wrote this constructor call), else None
  user_site  - the innermost scene-file frame on the stack at creation, for
               things built inside Manim (Axes.plot() makes a curve deep in
               Manim; the user's line is the `axes.plot(...)` call)
  chain      - every scene-file frame on the stack, outermost first, so a
               Text made inside a helper also knows the construct() line that
               called the helper
  occurrence - how many objects that site had made before (loops)

A click resolves to the nearest PRIMARY ancestor of the drawn leaf: clicking
one glyph selects its Text, clicking the panel border selects the
Rectangle. Things in manim_kit.py (Blob's body) are library code: they
resolve up to the scene-file object that owns them (the Blob).

`.copy()` called from the scene file gives the copy its own site (the copy
line), and remembers the original's in `copied_from`.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from manim import Mobject


@dataclass
class Site:
    file: str
    line: int
    end_line: int
    col: int
    end_col: int
    func: str

    def key(self) -> tuple:
        return (self.file, self.line, self.col)

    def __str__(self) -> str:
        return f"{Path(self.file).name}:{self.line}:{self.col} in {self.func}()"


@dataclass
class Origin:
    site: Site | None
    user_site: Site | None
    chain: list[Site] = field(default_factory=list)
    occurrence: int = 0
    copied_from: "Origin | None" = None
    regenerated: bool = False  # made by an updater (always_redraw, ClippedGrid)


_POSITIONS: dict = {}  # code object -> its co_positions() list


def _site(frame) -> Site:
    code = frame.f_code
    pos = None
    positions = _POSITIONS.get(code)
    if positions is None:
        positions = _POSITIONS[code] = list(code.co_positions())
    try:
        pos = positions[frame.f_lasti // 2]
    except IndexError:
        pass
    if not pos or pos[0] is None:
        pos = (frame.f_lineno, frame.f_lineno, 0, 0)
    return Site(code.co_filename, pos[0], pos[1] or pos[0], pos[2] or 0, pos[3] or 0, code.co_name)


class OriginTracker:
    """Install once per process; `files` are the scene files to attribute to."""

    def __init__(self, files: list[Path]):
        self.files = {str(Path(f).resolve()).lower() for f in files}
        self.counts: Counter = Counter()
        self._user_files: dict[str, bool] = {}  # co_filename -> in self.files
        self._orig_init = Mobject.__init__
        self._orig_copy = Mobject.copy
        tracker = self

        def init(mob, *a, **k):
            tracker._orig_init(mob, *a, **k)
            if "_studio_origin" not in mob.__dict__:
                mob._studio_origin = tracker._origin_for(mob, sys._getframe(1))

        def copy(mob, *a, **k):
            new = tracker._orig_copy(mob, *a, **k)
            caller = sys._getframe(1)
            # deepcopy copied the originals' origins. Re-stamp the copy's
            # family: it was made now, by this call. (Text's SVG cache hands
            # out copies whose glyphs would otherwise point at the line that
            # first made that text.)
            if tracker._is_user(caller):
                o = tracker._origin_for(new, caller, direct=caller)
                o.copied_from = getattr(mob, "_studio_origin", None)
                new._studio_origin = o
                inner = Origin(None, o.site, o.chain)
                for m in new.get_family()[1:]:
                    m._studio_origin = inner
            else:
                o = tracker._origin_for(new, caller, direct=caller)
                if o.user_site is not None:
                    shared = Origin(None, o.user_site, o.chain, regenerated=o.regenerated)
                    for m in new.get_family():
                        m._studio_origin = shared
            return new

        Mobject.__init__ = init
        Mobject.copy = copy

    def reset_counts(self):
        """Call before each replay, so occurrence numbers are reproducible."""
        self.counts.clear()

    def uninstall(self):
        Mobject.__init__ = self._orig_init
        Mobject.copy = self._orig_copy

    def _is_user(self, frame) -> bool:
        name = frame.f_code.co_filename
        hit = self._user_files.get(name)
        if hit is None:
            hit = self._user_files[name] = str(Path(name).resolve()).lower() in self.files
        return hit

    def _origin_for(self, mob, frame, direct=None) -> Origin:
        if direct is None:
            # skip the construction chain of this very object: super()
            # __init__ calls, and any wrapper around __init__ (the engine
            # adds some). They all have `self` bound to the new object.
            # (f_locals is costly on 3.13; only frames whose first argument
            # is `self` can be part of the chain)
            f = frame
            while f is not None and f.f_code.co_varnames[:1] == ("self",)                     and f.f_locals.get("self") is mob:
                f = f.f_back
            direct = f
        site = _site(direct) if direct is not None and self._is_user(direct) else None
        chain = []
        regenerated = False
        f = direct
        while f is not None:
            if self._is_user(f):
                chain.append(_site(f))
            elif f.f_code.co_name == "update" and f.f_code.co_filename.endswith("mobject.py"):
                regenerated = True  # inside Mobject.update(): an updater made it
            f = f.f_back
        chain.reverse()
        user_site = chain[-1] if chain else None
        occ = 0
        if site is not None:
            occ = self.counts[site.key()]
            self.counts[site.key()] += 1
        return Origin(site, user_site, chain, occ, regenerated=regenerated)


def parent_map(scene) -> dict[int, Mobject]:
    parents: dict[int, Mobject] = {}

    def walk(m):
        for s in m.submobjects:
            parents.setdefault(id(s), m)
            walk(s)
    for m in list(scene.mobjects) + list(getattr(scene, "foreground_mobjects", [])):
        walk(m)
    return parents


def resolve(leaf: Mobject, parents: dict[int, Mobject]) -> tuple[Mobject | None, Origin | None, str]:
    """(selected mobject, its origin, how).

    - The leaf was made by a scene-file call: select it ("primary").
    - It was made inside a scene-file call (glyphs of a Text, parts of a
      Blob, a grid inside ClippedGrid): walk up while the ancestors were
      made by that same call; if one of them IS that call's result, select
      it ("primary"), else the biggest group it made ("factory").
    - No scene-file frame at all: nearest primary ancestor.
    """
    o = getattr(leaf, "_studio_origin", None)
    if o is not None and o.regenerated:
        # rebuilt by an updater each frame: it belongs to the object that
        # holds it, not to whichever play() happened to be running
        m = parents.get(id(leaf))
        while m is not None and getattr(getattr(m, "_studio_origin", None), "regenerated", False):
            m = parents.get(id(m))
        if m is not None:
            return resolve(m, parents)
    if o is not None and o.site is not None:
        return leaf, o, "primary"
    if o is not None and o.user_site is not None:
        key = o.user_site.key()
        top, m = leaf, parents.get(id(leaf))
        while m is not None:
            mo = getattr(m, "_studio_origin", None)
            if mo is None:
                break
            if mo.site is not None and mo.site.key() == key:
                return m, mo, "primary"
            if mo.user_site is None or mo.user_site.key() != key:
                break
            top = m
            m = parents.get(id(m))
        return top, o, "factory"
    m = parents.get(id(leaf))
    while m is not None:
        mo = getattr(m, "_studio_origin", None)
        if mo is not None and mo.site is not None:
            return m, mo, "primary"
        m = parents.get(id(m))
    return None, None, "unknown"
