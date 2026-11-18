"""Which scene-file call last placed, scaled or rotated each mobject (S2).

Ported from the S2 spike (`spikes/code_edit.py`, MoveRecorder). While a
scene runs, every positioning call on a mobject records the scene-file call
that caused it and how:

- static: an ordinary call (`c.shift(UP)`, `Text(...).to_edge(UP)`);
- animate: inside `mob.animate.<method>(...)`, credited to the animated
  mobject itself (moving a pupil inside `Blob.animate.look_at` isn't);
- updater: inside an updater (set every frame; not draggable that way);
- laid_out: placed by a group's `arrange()`; every descendant is marked,
  with its index path from the group.

`Transform(a, b)` also remembers `b` on `a`: what is drawn as `a` is then
placed by `b`'s code as much as by `a`'s.

Only the outermost call is recorded (`next_to` calls `shift`), and only the
last few records per mobject are kept: an updater runs every frame.
"""

from __future__ import annotations

import itertools
import sys
import threading
from dataclasses import dataclass, field

from manim import Mobject

MOVE = ("shift", "move_to", "next_to", "to_edge", "to_corner", "align_to", "set_x", "set_y",
        "center", "arrange", "arrange_in_grid", "match_x", "match_y", "surround")
SCALE = ("scale", "scale_to_fit_width", "scale_to_fit_height", "stretch_to_fit_width",
         "stretch_to_fit_height", "set_width", "set_height")
ROTATE = ("rotate", "flip")
LAYOUT = ("arrange", "arrange_in_grid")
KEEP = 8  # records kept per mobject and group of methods

_clock = itertools.count()


class Fresh(list):
    """Studio bookkeeping on a mobject. `mob.copy()` deep-copies __dict__; a
    copy starts with none of it (a copy is placed by its own code, and must
    not drag whole groups along)."""

    def __deepcopy__(self, memo):
        return Fresh()

    def __copy__(self):
        return Fresh()


class FreshDict(dict):
    def __deepcopy__(self, memo):
        return FreshDict()

    def __copy__(self):
        return FreshDict()


def group_of(method: str) -> str:
    return "scale" if method in SCALE else "rotate" if method in ROTATE else "move"


@dataclass
class Move:
    order: int
    method: str
    site: object        # identity.Site: the innermost scene-file call on the stack
    kind: str           # static | animate | updater | laid_out
    chain: list         # every scene-file call on the stack, outermost first
    group: object = None  # laid_out: the group whose arrange() placed it
    path: tuple = ()      # laid_out: index path from that group to the object
    args: dict = field(default_factory=dict)  # a few argument facts (about_edge given, ...)


class MoveRecorder:
    """Installed once per worker process (runtime.install)."""

    def __init__(self, tracker):
        self.tracker = tracker
        self._local = threading.local()
        self._orig = {}
        for name in MOVE + SCALE + ROTATE:
            orig = getattr(Mobject, name, None)
            if orig is None:
                continue
            self._orig[name] = orig
            setattr(Mobject, name, self._wrap(name, orig))
        self._install_morphs()
        self._install_groups()

    def _install_groups(self):
        """Remember which groups each mobject was added to, so a group the
        scene never adds (`pair = VGroup(a, b)`) can still be selected and
        used for overrides."""
        orig = Mobject.add

        def add(group, *mobjects):
            out = orig(group, *mobjects)
            for m in mobjects:
                if isinstance(m, Mobject):
                    refs = m.__dict__.get("_studio_in")
                    if refs is None:
                        refs = m.__dict__["_studio_in"] = Fresh()
                    # a strong reference: `pair = VGroup(a, b)` lives only in construct()
                    refs.append(group)
                    if len(refs) > 4:
                        del refs[0]
            return out
        add.__doc__ = orig.__doc__
        Mobject.add = add

    def _depth(self) -> int:
        return getattr(self._local, "depth", 0)

    def _wrap(self, name, orig):
        rec = self

        def method(mob, *a, **k):
            loc = rec._local
            loc.depth = getattr(loc, "depth", 0) + 1
            try:
                return orig(mob, *a, **k)
            finally:
                loc.depth -= 1
                if loc.depth == 0:  # outermost call only
                    try:
                        rec._record(mob, name, k)
                    except Exception:
                        pass  # recording must never break a scene
        method.__name__ = name
        method.__doc__ = orig.__doc__
        return method

    def _record(self, mob, name, kwargs):
        f = sys._getframe(2)
        chain, kind, owner = [], "static", mob
        tracker = self.tracker
        from .identity import site_of
        while f is not None:
            co = f.f_code
            if tracker.is_user(f):
                chain.append(site_of(f))
            elif co.co_name == "update_target" and co.co_filename.endswith("mobject.py"):
                # mob.animate.<method>(...) is applied to mob.target at once;
                # the move belongs to the real mobject
                b = f.f_locals.get("self")
                if b is not None and hasattr(b, "mobject"):
                    if getattr(b.mobject, "target", None) is not mob:
                        return  # a part of the target moved
                    owner, kind = b.mobject, "animate"
            elif co.co_name == "update" and co.co_filename.endswith("mobject.py"):
                kind = "updater"
            elif kind == "static" and co.co_name in ("interpolate", "interpolate_mobject", "begin",
                                                      "finish", "clean_up_from_scene") \
                    and "animation" in co.co_filename.replace("\\", "/"):
                kind = "animation"  # moved by a running animation (MoveAlongPath, ...)
            f = f.f_back
        if not chain:
            return
        chain.reverse()
        args = {}
        if "about_edge" in kwargs or "about_point" in kwargs:
            args["about"] = True
        mv = Move(next(_clock), name, chain[-1], kind, chain, args=args)
        if kind == "animation":
            # _MethodAnimation.finish() applies `.animate` methods again on the
            # real object: the `animate` record made at build time is the one
            # that names the code
            prev = moves_of(owner, group_of(name))
            if prev and prev[-1].kind == "animate" and prev[-1].site.line == mv.site.line \
                    and prev[-1].site.file == mv.site.file:
                return
        _push(owner, mv)
        if name in LAYOUT and kind == "static":
            # everything inside was placed by this layout call
            def mark(m, path):
                for i, child in enumerate(m.submobjects):
                    _push(child, Move(mv.order, name, mv.site, "laid_out", chain, group=owner,
                                      path=path + (i,)))
                    mark(child, path + (i,))
            mark(owner, ())

    def _install_morphs(self):
        from manim import Transform
        orig = Transform.begin

        def begin(anim):
            target = getattr(anim, "target_mobject", None)
            o = getattr(target, "_studio_origin", None)
            if target is not None and target is not anim.mobject and o is not None \
                    and o.site is not None and o.copied_from is None:
                lst = anim.mobject.__dict__.get("_studio_morphs")
                if lst is None:
                    lst = anim.mobject.__dict__["_studio_morphs"] = Fresh()
                if target not in lst:
                    lst.append(target)
            return orig(anim)
        Transform.begin = begin


def parent_of(mob, parents: dict):
    """The group `mob` is in: on screen (the scene's tree) or, failing that,
    the last group the user made that still holds it."""
    p = parents.get(id(mob))
    if p is not None:
        return p
    for g in reversed(mob.__dict__.get("_studio_in", [])):
        o = getattr(g, "_studio_origin", None)
        if g is not None and o is not None and o.site is not None and any(s is mob for s in g.submobjects):
            return g
    return None


def _push(mob, mv: Move):
    d = mob.__dict__.get("_studio_moves")
    if d is None:
        d = mob.__dict__["_studio_moves"] = FreshDict()
    lst = d.setdefault(group_of(mv.method) if mv.kind != "laid_out" else "move", [])
    lst.append(mv)
    if len(lst) > KEEP:
        del lst[0]


def moves_of(mob, group: str = "move") -> list:
    return list(mob.__dict__.get("_studio_moves", {}).get(group, []))


# -- serialising for the planner (code/moves.py) -----------------------------------
def _ser(mv: Move) -> dict:
    d = {"order": mv.order, "method": mv.method, "kind": mv.kind, "site": mv.site.span(),
         "func": mv.site.func, "chain": [s.span() for s in mv.chain],
         "chain_funcs": [s.func for s in mv.chain]}
    if mv.args:
        d["args"] = mv.args
    if mv.kind == "laid_out":
        g = mv.group
        go = getattr(g, "_studio_origin", None)
        d["path"] = list(mv.path)
        d["group_site"] = go.site.span() if go is not None and go.site is not None else None
        d["group_func"] = go.site.func if go is not None and go.site is not None else None
        # the group's static placements at or after the layout, same function:
        # a later next_to()/move_to() re-centres the group
        d["group_moves"] = [_ser(m) for m in moves_of(g, "move")
                            if m.kind == "static" and m.order >= mv.order and m.site.func == mv.site.func]
    return d


def _create_move(mob) -> dict | None:
    o = getattr(mob, "_studio_origin", None)
    s = (o.site or o.user_site) if o is not None else None
    if s is None:
        return None
    return {"order": -1, "method": "create", "kind": "static", "site": s.span(), "func": s.func,
            "chain": [c.span() for c in o.chain], "chain_funcs": [c.func for c in o.chain],
            "library": o.site is None}


def placement(mob, parents: dict) -> dict:
    """What the planner needs to move, scale or rotate `mob`: its last
    records of each kind, its creation, Transform targets, and its ancestors
    (for overrides like `row[0][1].shift(...)`)."""
    out = {"create": _create_move(mob)}
    for g in ("move", "scale", "rotate"):
        lst = moves_of(mob, g)
        if lst:
            out[g] = _ser(lst[-1])
    morphs = []
    for t in mob.__dict__.get("_studio_morphs", []):
        m = {"create": _create_move(t)}
        lst = moves_of(t, "move")
        if lst:
            m["move"] = _ser(lst[-1])
        morphs.append(m)
    if morphs:
        out["morphs"] = morphs
    anc, child, p = [], mob, parent_of(mob, parents)
    while p is not None and len(anc) < 6:
        po = getattr(p, "_studio_origin", None)
        try:
            idx = next(i for i, s in enumerate(p.submobjects) if s is child)
        except StopIteration:
            break
        from .identity import object_id
        a = {"index": idx, "class": type(p).__name__, "id": object_id(p),
             "site": po.site.span() if po is not None and po.site is not None else None,
             "func": po.site.func if po is not None and po.site is not None else None,
             "chain": [c.span() for c in po.chain] if po is not None else []}
        lst = [m for m in moves_of(p, "move") if m.kind == "static"]
        if lst:
            a["move"] = _ser(lst[-1])
        anc.append(a)
        child, p = p, parent_of(p, parents)
    if anc:
        out["ancestors"] = anc
    return out
