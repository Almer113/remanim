"""Camera edits (Phase 5, steps 9 and 10).

2D (`MovingCameraScene`): the camera frame is moved or resized at the
playhead. The edit goes to the last `self.play(self.camera.frame.animate...)`
that has finished by then: its `.move_to(...)` and `.set(width=...)` /
`.scale(k)` change, or are added to its chain. With no camera move before
the playhead, one is inserted there. A move that follows an object
(`.move_to(dot)`) is not overwritten with numbers.

3D (`ThreeDScene`): phi, theta, zoom. The edit goes to the `move_camera(...)`
clip under the playhead, else the last `move_camera` or
`set_camera_orientation` before it, in `DEGREES` as the file writes them.
With none, `self.set_camera_orientation(...)` is added at the top of
construct().

Both are verified by replay: the camera at the playhead must be where the
user put it.
"""

from __future__ import annotations

import ast
import math

from .source import Source, Span
from .splice import Edit, EditError, fmt, number_of, set_keyword, set_number

ANGLES = ("phi", "theta", "gamma")


def _chain(call) -> list[ast.Call]:
    """`a.animate.scale(0.5).move_to(X)` → [scale call, move_to call] (outermost last)."""
    out = []
    n = call
    while isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        out.append(n)
        n = n.func.value
    return out[::-1]


def _is_frame_animate(expr) -> bool:
    """Does the call chain start at `self.camera.frame.animate`?"""
    n = expr
    while isinstance(n, (ast.Call, ast.Attribute)):
        if isinstance(n, ast.Attribute) and n.attr == "animate":
            v = n.value
            return (isinstance(v, ast.Attribute) and v.attr == "frame" and isinstance(v.value, ast.Attribute)
                    and v.value.attr == "camera")
        n = n.func if isinstance(n, ast.Call) else n.value
    return False


def _camera_play(src: Source, ev) -> ast.Call | None:
    """The `self.camera.frame.animate...` argument of this play() event, if any."""
    if not ev.get("call"):
        return None
    call = src.find_call(Span(*ev["call"]))
    if call is None or Source.call_name(call) != "play":
        return None
    arg = next((a for a in call.args if _is_frame_animate(a)), None)
    return arg if isinstance(arg, ast.Call) else None


def _is_frame(expr) -> bool:
    """`self.camera.frame`"""
    return (isinstance(expr, ast.Attribute) and expr.attr == "frame" and isinstance(expr.value, ast.Attribute)
            and expr.value.attr == "camera" and isinstance(expr.value.value, ast.Name) and expr.value.value.id == "self")


def _placements(fn, events) -> list[ast.Call]:
    """`self.camera.frame.move_to(..).set(width=..)` statements that run
    before the first play()/wait() of construct(): where the camera starts."""
    first = min((e["call_line"] for e in events if e.get("call_line")), default=None)
    out = []
    for st in fn.body:
        if first is not None and st.lineno >= first:
            break
        v = st.value if isinstance(st, ast.Expr) else None
        if isinstance(v, ast.Call):
            calls = _chain(v)
            if calls and _is_frame(calls[0].func.value):
                out.append(v)
    return out


def _fixed(node) -> bool:
    """A position written with numbers and Manim constants only."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and not n.id.isupper():
            return False
        if isinstance(n, (ast.Call, ast.Attribute, ast.Subscript)):
            return False
    return True


def plan_camera_2d(src: Source, scene: str, events: list, fps: float, timed: bool, t: float,
                   center: list | None, width: float | None, cur: dict):
    from . import inserts
    from .moves import delta_expr
    from .planner import Plan
    if center is None and width is None:
        raise EditError("nothing to change")
    if width is not None and not width > 0:
        raise EditError("the camera's width must be more than 0")
    running = [ev for ev in events if _camera_play(src, ev) is not None
               and ev["start"] < t - 1e-6 < ev["start"] + ev["duration"]]
    if running:
        raise EditError(f"the camera is moving here (line {running[0].get('call_line')}); "
                        "move the playhead to after the move")
    before = [ev for ev in events if _camera_play(src, ev) is not None
              and ev["start"] + ev["duration"] <= t + 1e-6]
    pos = delta_expr(round(center[0], 2), round(center[1], 2)) if center is not None else None
    if not before:
        fn = inserts.scene_construct(src, scene)
        chain = (f".move_to({pos})" if pos else "") + (f".set(width={fmt(round(width, 2))})" if width else "")
        placed = _placements(fn, events) if t < 1e-6 else []
        if placed:
            # the first frame, with the camera already placed: edit that line
            return _edit_chain(src, placed[-1], pos, width, cur, f"camera placement at line {placed[-1].lineno}")
        if t < 1e-6:
            # the first frame: place the camera before anything plays, no move
            body = fn.body
            first = body[1] if (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                                and len(body) > 1) else body[0]
            at = src.offset(first.lineno, 0)
            line = f"{src.indent_of(first.lineno)}self.camera.frame{chain}{src.newline}"
            return Plan([Edit(at, at, line)], f"camera placed: self.camera.frame{chain}", None,
                        checks={"camera": True})
        play = f"self.play(self.camera.frame.animate{chain}, run_time=1)"
        sl = inserts.slot(src, fn, events, t, fps, timed, 1.0)
        lines = inserts._timeline_lines(sl, t, timed, fps, play)
        start = inserts._start(sl, t, timed)
        return Plan(inserts._emit(src, sl, lines), f"camera move added at {start:.2f} s",
                    checks={"camera": True, "start": start, "run_time": 1.0})
    ev = before[-1]
    return _edit_chain(src, _camera_play(src, ev), pos, width, cur, f"camera move at line {ev.get('call_line')}")


def _edit_chain(src: Source, expr, pos, width, cur, where: str):
    """Change `.move_to(..)` / `.set(width=..)` / `.set_width(..)` / `.scale(k)` in a
    camera-frame chain, or add them to its end."""
    from .planner import Plan
    calls = _chain(expr)
    edits, notes = [], []
    end = src.span(expr)[1]
    tail = ""
    if pos is not None:
        mv = next((c for c in calls if c.func.attr == "move_to"), None)
        if mv is not None and mv.args:
            if not _fixed(mv.args[0]):
                raise EditError(f"the camera follows {src.text(mv.args[0])} (line {mv.lineno}); "
                                "move that instead, or change the code")
            edits.append(Edit(*src.span(mv.args[0]), pos))
        else:
            tail += f".move_to({pos})"
        notes.append(f"centre → {pos}")
    if width is not None:
        w = round(width, 3)
        st = next((c for c in calls if c.func.attr == "set" and Source.keyword(c, "width")), None)
        sw = next((c for c in calls if c.func.attr == "set_width" and c.args), None)
        sc = next((c for c in calls if c.func.attr == "scale" and c.args), None)
        if st is not None:
            k = Source.keyword(st, "width").value
            if number_of(k) is None:
                raise EditError(f"the camera width is computed ({src.text(k)}) at line {st.lineno}")
            edits.append(set_number(src, k, w))
        elif sw is not None:
            if number_of(sw.args[0]) is None:
                raise EditError(f"the camera width is computed ({src.text(sw.args[0])}) at line {sw.lineno}")
            edits.append(set_number(src, sw.args[0], w))
        elif sc is not None and number_of(sc.args[0]) is not None and cur.get("width"):
            k = number_of(sc.args[0]) * width / cur["width"]
            edits.append(set_number(src, sc.args[0], round(k, 3)))
        elif sc is not None:
            raise EditError(f"the camera zoom is computed ({src.text(sc.args[0])}) at line {sc.lineno}")
        else:
            tail += f".set(width={fmt(w)})"
        notes.append(f"width → {fmt(w)}")
    if tail:
        edits.append(Edit(end, end, tail))
    return Plan(edits, f"{where}: " + ", ".join(notes), None, checks={"camera": True})


# -- 3D ---------------------------------------------------------------------------------
def _camera_stmts(src: Source, fn) -> list[ast.Call]:
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "self" \
                and n.func.attr in ("set_camera_orientation", "move_camera"):
            out.append(n)
    return sorted(out, key=lambda c: (c.lineno, c.col_offset))


def _angle_text(src: Source, node, deg: float) -> Edit:
    """Replace an angle written as `N * DEGREES`, `N*DEGREES`, or radians."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        for num, other in ((node.left, node.right), (node.right, node.left)):
            if number_of(num) is not None and isinstance(other, ast.Name) and other.id == "DEGREES":
                return set_number(src, num, round(deg, 2))
    if number_of(node) is not None:
        return set_number(src, node, round(math.radians(deg), 4))
    raise EditError(f"the angle is computed ({src.text(node)}) at line {node.lineno}; change it in the code")


def plan_camera_3d(src: Source, scene: str, events: list, t: float, values: dict):
    from . import inserts
    from .planner import Plan
    want = {k: float(v) for k, v in values.items() if k in (*ANGLES, "zoom") and v is not None}
    if not want:
        raise EditError("nothing to change")
    if "zoom" in want and not want["zoom"] > 0:
        raise EditError("zoom must be more than 0")
    fn = inserts.scene_construct(src, scene)
    stmts = _camera_stmts(src, fn)
    # when each camera call runs: move_camera from its event; set_camera_orientation
    # at the start of the next event after it in the code
    times = []
    for c in stmts:
        if c.func.attr == "move_camera":
            ev = next((e for e in events if e.get("call") and src.find_call(Span(*e["call"])) is c), None)
            if ev is not None:
                times.append((c, ev["start"], ev["start"] + ev["duration"]))
        else:
            nxt = [e["start"] for e in events if e.get("call_line", 0) > c.end_lineno]
            times.append((c, min(nxt) if nxt else 0.0, None))
    # a move_camera counts once the playhead is inside it (at its first frame the
    # angle still comes from before); its end angles are what change
    usable = [x for x in times if (x[1] < t - 1e-6 if x[2] is not None else x[1] <= t + 1e-6)]
    if not usable:
        body = fn.body
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and len(body) > 1:
            first = body[1]  # after a docstring
        args = ", ".join(f"{k}={fmt(round(v, 2))} * DEGREES" if k in ANGLES else f"{k}={fmt(round(v, 3))}"
                         for k, v in want.items())
        at = src.offset(first.lineno, 0)
        line = f"{src.indent_of(first.lineno)}self.set_camera_orientation({args}){src.newline}"
        return Plan([Edit(at, at, line)], f"self.set_camera_orientation({args}) added", None,
                    checks={"camera": True})
    call, _, end = usable[-1]
    edits = []
    for k, v in want.items():
        kw = Source.keyword(call, k)
        if kw is not None:
            if k in ANGLES:
                edits.append(_angle_text(src, kw.value, v))
            else:
                if number_of(kw.value) is None:
                    raise EditError(f"zoom is computed ({src.text(kw.value)}) at line {call.lineno}")
                edits.append(set_number(src, kw.value, round(v, 3)))
        else:
            text = f"{fmt(round(v, 2))} * DEGREES" if k in ANGLES else fmt(round(v, 3))
            edits.append(set_keyword(src, call, k, text))
    edits.sort(key=lambda e: e.start)
    note = ", ".join(f"{k} {fmt(round(v, 2))}{'°' if k in ANGLES else ''}" for k, v in want.items())
    checks = {"camera": True}
    if end is not None and end > t:
        checks["verify_at"] = end  # the move is running at t: check where it ends
    return Plan(edits, f"{call.func.attr}() at line {call.lineno}: {note}", None, checks=checks)


def check(kind: str, got: dict | None, center=None, width=None, values=None) -> str | None:
    if not got:
        return "the studio can't read the camera after the edit"
    if kind == "2d":
        if center is not None and (abs(got["center"][0] - center[0]) > 0.02 or abs(got["center"][1] - center[1]) > 0.02):
            return f"the camera ended at ({got['center'][0]:.2f}, {got['center'][1]:.2f})"
        if width is not None and abs(got["width"] - width) > 0.02 * width:
            return f"the camera ended {got['width']:.2f} wide"
        return None
    for k, v in (values or {}).items():
        if v is None:
            continue
        if k in ANGLES and abs(((got[k] - v + 180) % 360) - 180) > 0.5:
            return f"{k} ended at {got[k]:.1f}°"
        if k == "zoom" and abs(got["zoom"] - v) > 0.01 * v:
            return f"zoom ended at {got['zoom']:.2f}"
    return None
