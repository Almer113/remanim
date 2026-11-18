"""Which line of code made each mobject (Phase 0 S3, docs/phase0/S3_identity.md).

Changes from the spike: occurrence counters are per thread (cursor threads
build objects at the same time), and object ids are strings for the wire.
"""

from __future__ import annotations

import sys
import threading
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

    def span(self) -> list[int]:
        return [self.line, self.col, self.end_line, self.end_col]

    def as_dict(self) -> dict:
        return {"span": self.span(), "func": self.func, "file": Path(self.file).name}


@dataclass
class Origin:
    site: Site | None
    user_site: Site | None
    chain: list[Site] = field(default_factory=list)
    occurrence: int = 0
    copied_from: "Origin | None" = None
    regenerated: bool = False  # made by an updater (always_redraw, ClippedGrid)


_POSITIONS: dict = {}


def site_of(frame) -> Site:
    code = frame.f_code
    positions = _POSITIONS.get(code)
    if positions is None:
        positions = _POSITIONS[code] = list(code.co_positions())
    pos = None
    try:
        pos = positions[frame.f_lasti // 2]
    except IndexError:
        pass
    if not pos or pos[0] is None:
        pos = (frame.f_lineno, frame.f_lineno, 0, 0)
    return Site(code.co_filename, pos[0], pos[1] or pos[0], pos[2] or 0, pos[3] or 0, code.co_name)


class OriginTracker:
    """Installed once per worker process."""

    def __init__(self):
        self.files: set[str] = set()
        self._local = threading.local()
        self._user_files: dict[str, bool] = {}
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
            if tracker.is_user(caller):
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

    def set_files(self, files):
        self.files = {str(Path(f).resolve()).lower() for f in files}
        self._user_files.clear()

    @property
    def counts(self) -> Counter:
        c = getattr(self._local, "counts", None)
        if c is None:
            c = self._local.counts = Counter()
        return c

    def reset_counts(self):
        """Call at the start of every run of construct() (per thread)."""
        self._local.counts = Counter()

    def raw_copy(self, mob):
        return self._orig_copy(mob)

    def is_user(self, frame) -> bool:
        name = frame.f_code.co_filename
        hit = self._user_files.get(name)
        if hit is None:
            hit = self._user_files[name] = str(Path(name).resolve()).lower() in self.files
        return hit

    def user_chain(self, frame) -> list[Site]:
        chain = []
        f = frame
        while f is not None:
            if self.is_user(f):
                chain.append(site_of(f))
            f = f.f_back
        chain.reverse()
        return chain

    def _origin_for(self, mob, frame, direct=None) -> Origin:
        if direct is None:
            f = frame
            while f is not None and f.f_code.co_varnames[:1] == ("self",) \
                    and f.f_locals.get("self") is mob:
                f = f.f_back
            direct = f
        site = site_of(direct) if direct is not None and self.is_user(direct) else None
        chain = []
        regenerated = False
        f = direct
        while f is not None:
            if self.is_user(f):
                chain.append(site_of(f))
            elif f.f_code.co_name == "update" and f.f_code.co_filename.endswith("mobject.py"):
                regenerated = True
            f = f.f_back
        chain.reverse()
        user_site = chain[-1] if chain else None
        occ = 0
        if site is not None:
            counts = self.counts
            occ = counts[site.key()]
            counts[site.key()] += 1
        return Origin(site, user_site, chain, occ, regenerated=regenerated)


def object_id(mob) -> str | None:
    o = getattr(mob, "_studio_origin", None)
    if o is None:
        return None
    s = o.site or o.user_site
    if s is None:
        return None
    tag = "" if o.site is not None else "~"
    # no end position: an edit later on the same line keeps the id
    return f"{tag}{type(mob).__name__}@{s.line}:{s.col}#{o.occurrence}"


def parent_map(scene) -> dict[int, Mobject]:
    parents: dict[int, Mobject] = {}

    def walk(m):
        for s in m.submobjects:
            parents.setdefault(id(s), m)
            walk(s)
    for m in list(scene.mobjects) + list(getattr(scene, "foreground_mobjects", [])):
        walk(m)
    return parents


def resolve(leaf, parents):
    """(selected mobject, origin, how) for a drawn leaf (see S3)."""
    o = getattr(leaf, "_studio_origin", None)
    if o is not None and o.regenerated:
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
