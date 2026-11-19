"""Library drops, delete, duplicate, group, animation presets and new files
(code_spec.md §4.5, §4.6, §6). Pure code layer: no Manim.

Inserted code is tier-1 style: a named object, palette colours when the file
imports style.py, explicit run_time=, objects first and then the timeline.
Where the new lines go in time is decided from the scene's trace: after the
last statement that ends at or before the playhead (see `slot`).
"""

from __future__ import annotations

import ast
import builtins
import keyword
import re
from dataclasses import dataclass, field

from .moves import (assigned_name, block_of, delta_expr, function_of, override_target, remove_statement,
                    statement_of)
from .source import Source, Span
from .splice import Edit, EditError, _remove_argument, fmt

# -- the library ----------------------------------------------------------------------
# class -> (arguments without style.py, arguments with style.py, default entrance)
SHAPES = {
    "Circle": ("radius=1, color=BLUE", "radius=1, color=ACCENT", "Create"),
    "Square": ("side_length=2, color=BLUE", "side_length=2, color=ACCENT", "Create"),
    "Rectangle": ("width=3, height=2, color=BLUE", "width=3, height=2, color=ACCENT", "Create"),
    "Triangle": ("color=BLUE", "color=ACCENT", "Create"),
    "RegularPolygon": ("n=6, color=BLUE", "n=6, color=ACCENT", "Create"),
    "Star": ("color=YELLOW", "color=ACCENT_2", "Create"),
    "Dot": ("color=YELLOW", "color=ACCENT", "FadeIn"),
    "Line": ("LEFT, RIGHT", "LEFT, RIGHT, color=FG", "Create"),
    "Arrow": ("LEFT, RIGHT, color=YELLOW", "LEFT, RIGHT, color=ACCENT", "GrowArrow"),
    "Text": ('"Text"', '"Text", font_size=BODY_SIZE, color=FG', "Write"),
    "MathTex": ('r"a^2 + b^2 = c^2"', 'r"a^2 + b^2 = c^2", color=FG', "Write"),
    "Blob": ("BLUE", "ACCENT", "FadeIn"),  # manim_kit
}
KIT = {"Blob"}
ENTRANCES = ("Create", "Write", "FadeIn", "GrowFromCenter", "DrawBorderThenFill", "GrowArrow", "SpinInFromNothing")
PRESETS = ("Indicate", "Circumscribe", "Wiggle", "Flash", "ApplyWave", "FocusOn", "FadeOut", "Uncreate",
           "ShrinkToCenter")
REGIONS = ("title", "main", "left", "right", "footer")
RUN_TIME = {"Write": 1.0, "Create": 0.8, "FadeIn": 0.6, "GrowFromCenter": 0.6, "DrawBorderThenFill": 1.0,
            "GrowArrow": 0.6, "SpinInFromNothing": 0.8, "Indicate": 1.0, "Circumscribe": 1.0, "Wiggle": 1.0,
            "Flash": 0.8, "ApplyWave": 1.0, "FocusOn": 1.0, "FadeOut": 0.6, "Uncreate": 0.8,
            "ShrinkToCenter": 0.6}


@dataclass
class Plan:
    edits: list
    note: str
    confirm: str | None = None
    checks: dict = field(default_factory=dict)


# -- file facts -----------------------------------------------------------------------------
def star_imports(src: Source) -> set[str]:
    return {n.module for n in src.tree.body if isinstance(n, ast.ImportFrom) and n.module
            and any(a.name == "*" for a in n.names)}


def uses_style(src: Source) -> bool:
    return "style" in star_imports(src)


def names_in_use(src: Source) -> set[str]:
    out = set(dir(builtins))
    for n in ast.walk(src.tree):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.alias):
            out.add((n.asname or n.name).split(".")[0])
    return out


def fresh_name(src: Source, base: str, taken: set | None = None) -> str:
    """`circle`, `circle_2`, ... (lowercase class name, numbered on clashes)."""
    stem = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    stem = re.sub(r"\W", "_", stem) or "obj"
    used = names_in_use(src) | (taken or set())
    if stem not in used and not keyword.iskeyword(stem):
        return stem
    i = 2
    while f"{stem}_{i}" in used:
        i += 1
    return f"{stem}_{i}"


def scene_construct(src: Source, scene: str) -> ast.FunctionDef:
    if not src.ok:
        raise EditError("the file doesn't parse")
    cls = next((n for n in src.tree.body if isinstance(n, ast.ClassDef) and n.name == scene), None)
    if cls is None:
        raise EditError(f"class {scene} isn't defined at the top of this file")
    fn = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "construct"), None)
    if fn is None:
        raise EditError(f"{scene} has no construct() of its own; add things in the class that defines it")
    return fn


def import_edit(src: Source, module: str) -> Edit | None:
    """`from <module> import *` after the last top-level import, if missing."""
    if module in star_imports(src):
        return None
    imports = [n for n in src.tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    nl = src.newline
    if not imports:
        return Edit(0, 0, f"from {module} import *{nl}")
    at = src.line_end(imports[-1].end_lineno)
    pre = "" if src.data[at - 1:at] == b"\n" else nl
    return Edit(at, at, f"{pre}from {module} import *{nl}")


# -- where in time -------------------------------------------------------------------------
@dataclass
class Slot:
    edits_before: list       # edits that make room (a split wait)
    at: int                  # byte offset where the new lines go
    indent: str
    start: float             # when the new play() starts
    replace_pass: Edit | None = None
    note: str = ""
    tail: str = ""           # a statement after the new lines (the rest of a split wait)
    absorbs: float = 0.0     # seconds of the split wait the new play() uses up
    at_needed: bool = True   # TimedScene: write `self.at(t)` (False: the play starts later, as is)


def _stmt_times(src: Source, fn, events: list) -> dict[int, list]:
    """id(statement of fn's body, at any depth) -> [(start, end)] of its events."""
    out: dict[int, list] = {}
    for ev in events:
        spans = list(ev.get("chain") or []) or ([ev["call"]] if ev.get("call") else [])
        for sp in spans:
            c = src.find_call(Span(*sp))
            if c is None or function_of(src, c) is not fn:
                continue
            st = statement_of(src, c)
            while st is not None and st is not fn:
                out.setdefault(id(st), []).append((ev["start"], ev["start"] + ev["duration"], ev))
                st = statement_of(src, src.parent(st))
            break
    return out


def _wait_literal(st):
    """`self.wait(d)` with a literal d -> the Constant node."""
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
        c = st.value
        f = c.func
        if isinstance(f, ast.Attribute) and f.attr == "wait" and isinstance(f.value, ast.Name) and \
                f.value.id == "self" and len(c.args) == 1 and not c.keywords and \
                isinstance(c.args[0], ast.Constant) and isinstance(c.args[0].value, (int, float)):
            return c.args[0]
    return None


def slot(src: Source, fn, events: list, t: float, fps: float, timed: bool, run_time: float) -> Slot:
    """Where new statements go so their play() starts at (or right after) t."""
    times = _stmt_times(src, fn, events)
    frame = 1 / fps
    body = fn.body
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        p = body[0]
        if p.lineno == fn.lineno:
            raise EditError(f"construct() is written on one line (line {fn.lineno}); "
                            "put its body on its own line first")
        a = src.line_starts[p.lineno - 1]
        return Slot([], a, src.indent_of(p.lineno), t if timed else 0.0,
                    replace_pass=Edit(a, src.line_end(p.end_lineno), ""))
    block_start = 0.0
    while True:
        j = next((i for i, st in enumerate(body) if any(e > t + 1e-6 for _, e, _ in times.get(id(st), []))),
                 None)
        if j is None:
            last = body[-1]
            end = max([block_start] + [e for st in body for _, e, _ in times.get(id(st), [])])
            return Slot([], src.line_end(last.end_lineno), src.indent_of(last.lineno),
                        t if timed else end)
        st = body[j]
        a = min(s for s, _, _ in times[id(st)])
        prev_end = max([block_start] + [e for s2 in body[:j] for _, e, _ in times.get(id(s2), [])])
        lit = _wait_literal(st)
        if lit is not None and a <= t + frame / 2:
            # a literal wait covers t: split it around the new lines so later
            # clips keep their times (as far as the wait is long enough)
            d = float(lit.value)
            first = round(t - a, 2) if t - a > frame / 2 else 0.0
            rest = round(d - first - run_time, 2)
            ws, we = src.span(lit)
            indent = src.indent_of(st.lineno)
            nl = src.newline
            absorbs = run_time if rest >= frame else d - first
            if first == 0.0:
                # the new lines go before the wait, which keeps what is left of it
                if rest >= frame:
                    sl = _before(src, body, j, a, False, t)
                    sl.edits_before, sl.start, sl.absorbs = [Edit(ws, we, fmt(rest, src.text(lit)))], a, absorbs
                    return sl
                # the new play() uses up the whole wait: remove it, or (when it
                # shares its line or is alone in its block) make it a `pass`;
                # never `wait(0)`, which Manim refuses
                e = _remove_stmt_edit(src, st)
                if e is None:
                    s0, s1 = src.span(st)
                    e = Edit(s0, s1, "pass")
                sl = _before(src, body, j, a, False, t)
                sl.edits_before, sl.start, sl.absorbs = [e], a, absorbs
                return sl
            edits = [Edit(ws, we, fmt(first, src.text(lit)))]
            tail = f"{indent}self.wait({fmt(rest, src.text(lit))}){nl}" if rest >= frame else ""
            return Slot(edits, src.line_end(st.end_lineno), indent, a + first, tail=tail, absorbs=absorbs)
        if a >= t - 1e-6:   # the next statement starts at or after t: go just before it
            return _before(src, body, j, prev_end, timed, t)
        if isinstance(st, (ast.With, ast.AsyncWith)) and st.body:
            body, block_start = st.body, a   # t is inside the with block: look inside
            continue
        if timed and _is_self_stmt(st, "at"):
            e = max(x for _, x, _ in times[id(st)])
            if abs(e - t) < frame / 2:
                # `self.at(t)` itself (its end only rounds past t): go after it
                return Slot([], src.line_end(st.end_lineno), src.indent_of(st.lineno), e, at_needed=False)
            # `self.at(3)` waiting through t: the new self.at(t) goes before it
            return _before(src, body, j, prev_end, timed, t)
        # t is inside a play() or something else that runs: start right after it
        # (in a TimedScene too: `self.at(t)` for a time already past would do nothing)
        e = max(x for _, x, _ in times[id(st)])
        return Slot([], src.line_end(st.end_lineno), src.indent_of(st.lineno), e,
                    note=f"; starts at {e:.2f} s, when the play() at line {st.lineno} ends", at_needed=False)


def _is_self_stmt(st, method: str) -> bool:
    return isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and _is_self(st.value, method)


def _remove_stmt_edit(src: Source, st) -> Edit | None:
    return remove_statement(src, st)


def _before(src, body, j, prev_end, timed, t) -> Slot:
    st = body[j]
    # the statements before already bring the scene to t (`self.at(t)` just
    # above, a play() ending at t): another self.at(t) would do nothing
    there = timed and abs(prev_end - t) < 0.005
    if j == 0:
        return Slot([], src.line_starts[st.lineno - 1], src.indent_of(st.lineno), t if timed else prev_end,
                    at_needed=not there)
    prev = body[j - 1]
    return Slot([], src.line_end(prev.end_lineno), src.indent_of(prev.lineno), t if timed else prev_end,
                at_needed=not there)


def _start(sl: Slot, t: float, timed: bool) -> float:
    """When the new play() really starts."""
    return t if timed and sl.at_needed else max(sl.start, t)


def _timeline_lines(sl: Slot, t: float, timed: bool, fps: float, play: str) -> list[str]:
    lines = []
    if timed and sl.at_needed and t > 1 / fps:
        lines.append(f"self.at({fmt(round(t, 2))})")
    elif not timed and t - sl.start > 1 / fps:
        lines.append(f"self.wait({fmt(round(t - sl.start, 2))})")
    lines.append(play)
    return lines


def _pushed(sl: Slot, t: float, timed: bool, fps: float, run_time: float, events: list) -> str:
    """How much later the clips after the new play() start (sequential scenes)."""
    if timed:
        return sl.note
    gap = t - sl.start if t - sl.start > 1 / fps else 0.0
    later = any(ev["start"] >= sl.start + 1e-6 for ev in events if ev.get("call"))
    push = round(gap + run_time - sl.absorbs, 2)
    if later and push > 1 / fps:
        return sl.note + f"; later clips start {fmt(push)} s later"
    return sl.note


def _lead(src: Source, at: int) -> str:
    """A newline first when inserting after a last line that has none."""
    return src.newline if at > 0 and src.data[at - 1:at] != b"\n" else ""


def _emit(src: Source, sl: Slot, lines: list[str], extra: list | None = None) -> list[Edit]:
    nl = src.newline
    text = "".join(f"{sl.indent}{ln}{nl}" for ln in lines) + sl.tail
    edits = list(sl.edits_before) + list(extra or [])
    if sl.replace_pass is not None:
        edits.append(Edit(sl.replace_pass.start, sl.replace_pass.end, _lead(src, sl.replace_pass.start) + text))
    else:
        edits.append(Edit(sl.at, sl.at, _lead(src, sl.at) + text))
    return edits


# -- insert from the library ----------------------------------------------------------------
def plan_insert(src: Source, scene: str, events: list, fps: float, timed: bool, cls: str, x: float, y: float,
                t: float, entrance: str | None = None, region: str | None = None) -> Plan:
    if cls not in SHAPES:
        raise EditError(f"{cls} isn't in the library")
    if entrance is not None and entrance != "" and entrance not in ENTRANCES:
        raise EditError(f"{entrance} isn't an entrance")
    if region is not None and region not in REGIONS:
        raise EditError(f"no region {region!r}")
    fn = scene_construct(src, scene)
    style = uses_style(src)
    plain, styled, default_in = SHAPES[cls]
    args = styled if style else plain
    entrance = default_in if entrance is None else entrance
    name = fresh_name(src, cls)
    make = f"{cls}({args})"
    if region and style:
        make = f'place({make}, "{region}")'
    elif abs(x) > 1e-3 or abs(y) > 1e-3:
        make += f".move_to({delta_expr(round(x, 2), round(y, 2))})"
    rt = RUN_TIME.get(entrance, 0.8) if entrance else 0.0
    play = f"self.play({entrance}({name}), run_time={fmt(rt)})" if entrance else f"self.add({name})"
    sl = slot(src, fn, events, t, fps, timed, rt)
    lines = [f"{name} = {make}"] + _timeline_lines(sl, t, timed, fps, play)
    extra = []
    if cls in KIT:
        e = import_edit(src, "manim_kit")
        if e is not None:
            extra.append(e)
    start = _start(sl, t, timed)
    return Plan(_emit(src, sl, lines, extra),
                f"{name} = {cls}(...) and {entrance or 'add'}() at {start:.2f} s"
                f"{_pushed(sl, t, timed, fps, rt, events)}",
                checks={"name": name, "class": cls, "start": start, "run_time": rt,
                        "center": None if (region and style) else [round(x, 2), round(y, 2)]})


def plan_preset(src: Source, scene: str, events: list, fps: float, timed: bool, obj: dict, preset: str,
                t: float) -> Plan:
    """An animation preset dropped on an object: a play() at the playhead."""
    if preset not in PRESETS:
        raise EditError(f"{preset} isn't an animation preset")
    fn = scene_construct(src, scene)
    expr = reference(src, obj, fn)
    rt = RUN_TIME.get(preset, 1.0)
    sl = slot(src, fn, events, t, fps, timed, rt)
    lines = _timeline_lines(sl, t, timed, fps, f"self.play({preset}({expr}), run_time={fmt(rt)})")
    start = _start(sl, t, timed)
    return Plan(_emit(src, sl, lines), f"{preset}({expr}) at {start:.2f} s{_pushed(sl, t, timed, fps, rt, events)}",
                checks={"start": start, "run_time": rt})


def reference(src: Source, obj: dict, fn) -> str:
    """A name (or `group[i]`) for `obj` that is in scope in `fn`."""
    return reference_at(src, obj, fn)[0]


def reference_at(src: Source, obj: dict, fn) -> tuple[str, ast.stmt]:
    """The name for `obj` and the statement that binds it to this object
    (not just any assignment of that name: names get reused)."""
    named = assigned_name(src, obj.get("site"))
    if named and function_of(src, named[1]) is fn:
        return named
    for sp in obj.get("chain_spans") or []:
        r = assigned_name(src, sp)
        if r and function_of(src, r[1]) is fn:
            return r
    ov = override_target(src, obj)
    if ov and function_of(src, ov[1]) is fn:
        return ov
    raise EditError("this object isn't stored in a variable in construct(); name it in the code first")


def _assigns(node, name: str) -> bool:
    return any(isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For)) and any(
        isinstance(t, ast.Name) and t.id == name
        for tg in (n.targets if isinstance(n, ast.Assign) else [n.target]) for t in ast.walk(tg))
        for n in ast.walk(node))


# -- duplicate and group ------------------------------------------------------------------
def plan_duplicate(src: Source, scene: str, events: list, fps: float, timed: bool, obj: dict,
                   t: float, dx: float = 0.5, dy: float = -0.5) -> Plan:
    fn = scene_construct(src, scene)
    expr = reference(src, obj, fn)
    base = re.sub(r"\[.*", "", expr)
    name = fresh_name(src, base)
    rt = RUN_TIME["FadeIn"]
    sl = slot(src, fn, events, t, fps, timed, rt)
    lines = [f"{name} = {expr}.copy().shift({delta_expr(dx, dy)})"] + \
        _timeline_lines(sl, t, timed, fps, f"self.play(FadeIn({name}), run_time={fmt(rt)})")
    start = _start(sl, t, timed)
    return Plan(_emit(src, sl, lines),
                f"{name} = {expr}.copy() at {start:.2f} s{_pushed(sl, t, timed, fps, rt, events)}",
                checks={"name": name, "start": start, "run_time": rt})


def plan_group(src: Source, scene: str, objs: list[dict]) -> Plan:
    if len(objs) < 2:
        raise EditError("select two or more objects to group (Shift-click)")
    fn = scene_construct(src, scene)
    exprs, binds = [], []
    for o in objs:
        e, st = reference_at(src, o, fn)
        if e in exprs:
            continue
        exprs.append(e)
        binds.append((re.sub(r"\[.*", "", e), st))
    # after the later of the creations, at construct()'s own level
    tops = [(root, _top(src, fn, st)) for root, st in binds]
    after = max((t for _, t in tops), key=lambda s: s.end_lineno)
    i_after = fn.body.index(after)
    for root, top in tops:
        # the name must still mean this object where the group is made
        later = fn.body[fn.body.index(top) + 1:i_after + 1]
        hit = next((s for s in later if _assigns(s, root)), None)
        if hit is not None:
            raise EditError(f"{root} is given a new value at line {hit.lineno}; group them in the code")
    name = fresh_name(src, "group")
    nl = src.newline
    indent = src.indent_of(after.lineno)
    at = src.line_end(after.end_lineno)
    return Plan([Edit(at, at, f"{_lead(src, at)}{indent}{name} = VGroup({', '.join(exprs)}){nl}")],
                f"{name} = VGroup({', '.join(exprs)}) after line {after.end_lineno}",
                checks={"name": name, "members": exprs})


def _top(src: Source, fn, st):
    while st is not None and not any(s is st for s in fn.body):
        st = statement_of(src, src.parent(st))
    if st is None:
        raise EditError("that object is made inside a block; group it in the code")
    return st


# -- delete ------------------------------------------------------------------------------------
def _refs(node, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _other_names(node, name: str, api: set) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and n.id not in (name, "self")
            and n.id not in api}


def _is_self(call, method: str) -> bool:
    f = call.func
    return isinstance(f, ast.Attribute) and f.attr == method and isinstance(f.value, ast.Name) and f.value.id == "self"


def _base_name(expr):
    """`x` in `x.shift(...).set_color(...)`."""
    n = expr
    while isinstance(n, (ast.Call, ast.Attribute, ast.Subscript)):
        n = n.func if isinstance(n, ast.Call) else n.value
    return n.id if isinstance(n, ast.Name) else None


def _remove_stmts(src: Source, stmts: list) -> list[Edit]:
    out = []
    ids = {id(s) for s in stmts}
    for st in stmts:
        blk = block_of(src, st)
        head = src.parent(st)
        if head is not None and not isinstance(head, ast.Module) and getattr(head, "lineno", None) == st.lineno:
            # `with self.voiceover(...): self.play(...)`: removing the line would take the header too
            raise EditError(f"line {st.lineno} puts the statement on the same line as its "
                            f"{type(head).__name__.lower()}; delete it in the code")
        if blk is not None and all(id(s) in ids for s in blk) and st is blk[0]:
            # the whole block goes: keep it valid Python
            a = src.line_starts[st.lineno - 1]
            out.append(Edit(a, src.line_end(st.end_lineno), f"{src.indent_of(st.lineno)}pass{src.newline}"))
            continue
        if blk is not None and all(id(s) in ids for s in blk):
            e = Edit(src.line_starts[st.lineno - 1], src.line_end(st.end_lineno), "")
        else:
            e = remove_statement(src, st)
        if e is None:
            raise EditError(f"line {st.lineno} shares its line with other code; delete it in the code")
        out.append(e)
    return out


def _orphan_at(src: Source, gone: list, block) -> list:
    """`self.at(t)` statements left timing nothing once `gone` are removed."""
    if block is None:
        return []
    ids = {id(s) for s in gone}
    keep = [s for s in block if id(s) not in ids]
    out = []
    for i, st in enumerate(block):
        if id(st) not in ids:
            continue
        j = i - 1
        while j >= 0 and id(block[j]) in ids:
            j -= 1
        if j < 0:
            continue
        prev = block[j]
        if not (isinstance(prev, ast.Expr) and isinstance(prev.value, ast.Call) and _is_self(prev.value, "at")):
            continue
        nxt = next((s for s in block[i + 1:] if id(s) not in ids), None)
        nxt_is_at = nxt is None or (isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Call)
                                    and _is_self(nxt.value, "at"))
        if nxt_is_at and prev not in out and len(keep) > 1:
            out.append(prev)
    return out


def plan_delete(src: Source, scene: str, obj: dict, api: set) -> Plan:
    fn = scene_construct(src, scene)
    named = assigned_name(src, obj.get("site"))
    if not named or function_of(src, named[1]) is not fn:
        return _delete_inline(src, fn, obj)
    name, made = named
    # names the file assigns itself are the user's, even if a library also exports
    # them (`rotation`, `scene`, `camera`)
    api = set(api) - {n.id for n in ast.walk(src.tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    if not any(s is made for s in fn.body):
        raise EditError(f"{name} is made inside a block (line {made.lineno}); delete it in the code")
    gone, arg_edits, readers = [made], [], []
    for st in fn.body[fn.body.index(made) + 1:]:
        if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in st.targets) \
                and not _refs(st.value, name):
            break  # the name is reused from here on
        if not _refs(st, name):
            continue
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
            c = st.value
            if any(_is_self(c, m) for m in ("add", "remove", "bring_to_front", "bring_to_back",
                                             "add_foreground_mobject")) and not c.keywords:
                hits = [a for a in c.args if _refs(a, name)]
                if all(isinstance(a, ast.Name) for a in hits):
                    if len(hits) == len(c.args):
                        gone.append(st)
                    else:
                        arg_edits += [_remove_argument(src, c, a) for a in hits]
                    continue
            if _is_self(c, "play"):
                hits = [a for a in c.args if _refs(a, name)]
                mixed = [a for a in hits if _other_names(a, name, api)]
                if not mixed and not any(_refs(k.value, name) for k in c.keywords):
                    if len(hits) == len(c.args):
                        gone.append(st)
                    else:
                        arg_edits += [_remove_argument(src, c, a) for a in hits]
                    continue
            if _base_name(c) == name and not _other_names(c, name, api):
                gone.append(st)  # name.shift(...), name.set_color(...)
                continue
        readers.append(st.lineno)
    if readers:
        raise EditError(f"{name} is also used at line{'s' if len(readers) > 1 else ''} "
                        f"{', '.join(map(str, readers[:6]))}; change those first")
    gone += _orphan_at(src, gone, fn.body)
    edits = _remove_stmts(src, gone) + arg_edits
    return Plan(edits, f"{name} deleted ({len(gone)} statement{'s' if len(gone) != 1 else ''}"
                       f"{', ' + str(len(arg_edits)) + ' argument(s)' if arg_edits else ''})",
                checks={"gone": obj.get("id")})


def _delete_inline(src: Source, fn, obj: dict) -> Plan:
    """An object made inside a play() (`self.play(Write(Text("x")))`): delete that animation."""
    site = obj.get("site")
    call = src.find_call(Span(*site)) if site else None
    if call is None:
        raise EditError("this object isn't made in the scene file")
    st = statement_of(src, call)
    if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and _is_self(st.value, "play")
            and any(s is st for s in fn.body)):
        raise EditError("this object isn't stored in a variable; delete it in the code")
    play = st.value
    arg = next((a for a in play.args if any(n is call for n in ast.walk(a))), None)
    if arg is None:
        raise EditError("can't tell which animation makes this object")
    return _delete_anim(src, fn, play, st, arg)


def _delete_anim(src: Source, fn, play, st, arg) -> Plan:
    if len(play.args) > 1:
        return Plan([_remove_argument(src, play, arg)], f"{src.text(arg)[:40]} removed from play() (line {st.lineno})")
    blk = block_of(src, st)
    gone = [st] + _orphan_at(src, [st], blk)
    return Plan(_remove_stmts(src, gone), f"play() at line {st.lineno} deleted")


def plan_delete_clip(src: Source, scene: str, clip: dict, anim: int | None) -> Plan:
    if clip.get("in_helper"):
        raise EditError(f"this clip is made inside {clip.get('func')}(); delete it in the code")
    call = src.find_call(Span(*clip["call"])) if clip.get("call") else None
    if call is None:
        raise EditError("can't find the code for this clip")
    st = statement_of(src, call)
    if not (isinstance(st, ast.Expr) and st.value is call):
        raise EditError(f"the clip's call at line {call.lineno} is part of a larger statement")
    name = Source.call_name(call)
    fn = function_of(src, st)
    if name == "play" and anim is not None:
        if any(isinstance(a, ast.Starred) for a in call.args) or not 0 <= anim < len(call.args):
            raise EditError("can't tell which argument of play() this animation is")
        return _delete_anim(src, fn, call, st, call.args[anim])
    if name not in ("play", "wait"):
        raise EditError(f"this clip comes from {name}(); delete it in the code")
    blk = block_of(src, st)
    gone = [st] + (_orphan_at(src, [st], blk) if name == "play" else [])
    return Plan(_remove_stmts(src, gone), f"{name}() at line {st.lineno} deleted")


# -- a new scene file -------------------------------------------------------------------------
def new_file_text(scene: str = "NewScene", target: float = 5.0) -> str:
    """The §6 template: a TimedScene with a length to drop things into."""
    if not scene.isidentifier() or keyword.iskeyword(scene):
        raise EditError(f"not a class name: {scene!r}")
    return (
        "from manim import *\n"
        "from manim_kit import *\n"
        "from style import *\n"
        "\n"
        "\n"
        f"class {scene}(TimedScene):\n"
        "    VOICE = None  # set a voice to narrate\n"
        f"    TARGET = {fmt(target, '1.0')}  # seconds; the scene is padded to this length\n"
        "\n"
        "    def construct(self):\n"
        "        apply_background()\n"
    )
