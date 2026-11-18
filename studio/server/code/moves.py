"""Canvas drags -> code: move, scale and rotate (code_spec.md §4.1, §4.2, §5).

Input is an object as the engine describes it (`placement`: the calls that
last moved, scaled and rotated it, its creation, Transform targets and named
ancestors); output is a ranked list of candidate edits. The caller applies
the first, replays the scene to the same moment and measures; if the object
didn't land where the drag put it, it tries the next (verify by replay).

Ported from the S2 spike (`spikes/code_edit.py`). Round trips close: a term,
a chained call or an inserted statement that returns to zero is removed, so
dragging back by the same amount restores the file byte for byte.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass

from .source import Source, Span
from .splice import Edit, EditError, fmt, number_of, set_number

DIRS = {"RIGHT": (1, 0), "LEFT": (-1, 0), "UP": (0, 1), "DOWN": (0, -1)}
EDGES = {"UL", "UR", "DL", "DR", "UP", "DOWN", "LEFT", "RIGHT"}
EPS = 1e-9
# a number this close to 0 or 1 is that number: far inside verification's 0.011,
# and it absorbs the remainder a calibrated (scaled-parent) drag back leaves
SNAP = 1e-3


@dataclass
class Candidate:
    note: str
    edits: list
    confirm: str | None = None  # a side effect the user must accept first
    kind: str = "local"         # local | override | helper | group | loop


# -- formatting ---------------------------------------------------------------------
def _num(v: float, like: str | None = None) -> str:
    return fmt(round(v, 4), like)


def _renum(src: Source, node, value: float) -> Edit:
    """Replace a number literal after a drag. A whole result is written
    whole (`3`), unless the literal it replaces is itself whole with a point
    (`1.0`): a drag there and back must give the original text, and a
    literal on its way back has the style of the in-between value."""
    a, b = src.span(node)
    old = src.text(node).lstrip("+-")
    v = round(float(value), 4)
    whole_point = old.replace(".", "", 1).isdigit() and "." in old and float(old) == int(float(old))
    like = old if (v != int(v) or whole_point) else None
    return Edit(a, b, fmt(v, like))


def _dir_term(v: float, pos: str, neg: str) -> str:
    name = pos if v > 0 else neg
    a = abs(v)
    return name if abs(a - 1) < EPS else f"{_num(a)} * {name}"


def delta_expr(dx: float, dy: float) -> str:
    """`0.4 * RIGHT + 0.25 * DOWN`: Manim constants, zero parts left out."""
    terms = []
    if abs(dx) > EPS:
        terms.append(_dir_term(dx, "RIGHT", "LEFT"))
    if abs(dy) > EPS:
        terms.append(_dir_term(dy, "UP", "DOWN"))
    return " + ".join(terms) or "ORIGIN"


def degrees_text(deg: float) -> str:
    return f"{_num(deg)} * DEGREES"


# -- statements -----------------------------------------------------------------------
def statement_of(src: Source, node):
    n = node
    while n is not None and not isinstance(n, ast.stmt):
        n = src.parent(n)
    return n


def block_of(src: Source, stmt) -> list | None:
    """The statement list that holds `stmt` (a function body, a with body, ...)."""
    p = src.parent(stmt)
    if p is None:
        return None
    for name in ("body", "orelse", "finalbody", "handlers"):
        lst = getattr(p, name, None)
        if isinstance(lst, list) and any(s is stmt for s in lst):
            return lst
    return None


def function_of(src: Source, node):
    n = src.parent(node)
    while n is not None and not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        n = src.parent(n)
    return n


def in_loop(src: Source, node) -> ast.AST | None:
    """The loop or comprehension inside the same function that repeats `node`."""
    n = src.parent(node)
    while n is not None and not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                                               ast.ClassDef, ast.Module)):
        if isinstance(n, (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp,
                          ast.DictComp, ast.GeneratorExp)):
            return n
        n = src.parent(n)
    return None


def insert_after(src: Source, stmt, code: str) -> Edit:
    """A new statement on its own line after `stmt`, same indentation."""
    if isinstance(stmt, ast.Return):
        raise EditError("can't add a statement after a return")
    end = src.line_end(stmt.end_lineno)
    indent = src.indent_of(stmt.lineno)
    nl = src.newline
    pre = "" if end == 0 or src.data[end - 1:end] == b"\n" else nl
    return Edit(end, end, f"{pre}{indent}{code}{nl}")


def remove_statement(src: Source, stmt) -> Edit | None:
    """Delete a statement that sits alone on its lines (None if it shares a
    line, or is the only statement of its block)."""
    blk = block_of(src, stmt)
    if blk is None or len(blk) < 2:
        return None
    first, last = src.line_text(stmt.lineno), src.line_text(stmt.end_lineno)
    if first[: stmt.col_offset].strip() or last[stmt.end_col_offset:].strip().lstrip(";").strip():
        return None
    return Edit(src.line_starts[stmt.lineno - 1], src.line_end(stmt.end_lineno), "")


def _is_self_call(call: ast.Call) -> bool:
    f = call.func
    return isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self"


def assigned_name(src: Source, span) -> tuple[str, ast.stmt] | None:
    """`name = <call at span>...` (the call, or the head of a method chain
    on it) -> (name, statement)."""
    if span is None or not src.ok:
        return None
    call = src.find_call(Span(*span))
    if call is None:
        return None
    stmt = statement_of(src, call)
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
        return None
    v = stmt.value
    while isinstance(v, ast.Call):
        if v is call:
            return stmt.targets[0].id, stmt
        f = v.func
        v = f.value if isinstance(f, ast.Attribute) else None
    return None


def _name_via_chain(src: Source, spans: list) -> tuple[str, ast.stmt] | None:
    for sp in spans or []:
        r = assigned_name(src, sp)
        if r:
            return r
    return None


# -- vectors --------------------------------------------------------------------------
def _terms(node):
    """Flatten a +/- chain into (sign, node) terms."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left, right = _terms(node.left), _terms(node.right)
        if left is None or right is None:
            return None
        s = -1 if isinstance(node.op, ast.Sub) else 1
        return left + [(sg * s, n) for sg, n in right]
    return [(1, node)]


def _axis_term(node):
    """(direction name, coefficient node or None, coefficient value) for
    `c * RIGHT`, `RIGHT * c`, `RIGHT / c`, `RIGHT`, `-UP`; None otherwise."""
    if isinstance(node, ast.Name) and node.id in DIRS:
        return node.id, None, 1.0
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and \
            isinstance(node.operand, ast.Name) and node.operand.id in DIRS:
        return node.operand.id, None, -1.0
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
        a, b = node.left, node.right
        if isinstance(node.op, ast.Div):
            if isinstance(a, ast.Name) and a.id in DIRS and number_of(b) not in (None, 0.0):
                return a.id, None, 1.0 / number_of(b)
            return None
        if isinstance(b, ast.Name) and b.id in DIRS:
            a, b = b, a
        if isinstance(a, ast.Name) and a.id in DIRS and number_of(b) is not None:
            return a.id, b, number_of(b)
    return None


def _vector_list(node):
    """`[x, y]`, `[x, y, 0]`, `np.array([...])` with numeric literals -> element nodes."""
    if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name)) and \
            (getattr(node.func, "attr", None) or getattr(node.func, "id", None)) == "array" and \
            len(node.args) == 1 and not node.keywords:
        node = node.args[0]
    if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) in (2, 3) and \
            all(number_of(e) is not None for e in node.elts):
        return node.elts
    return None


def eval_vector(expr) -> tuple[float, float] | None:
    elts = _vector_list(expr)
    if elts is not None:
        return number_of(elts[0]), number_of(elts[1])
    terms = _terms(expr)
    if not terms:
        return None
    x = y = 0.0
    for sign, node in terms:
        if isinstance(node, ast.Name) and node.id == "ORIGIN":
            continue
        t = _axis_term(node)
        if t is None:
            return None
        name, _, c = t
        x += sign * c * DIRS[name][0]
        y += sign * c * DIRS[name][1]
    return x, y


def _parent_binop(root, node):
    for n in ast.walk(root):
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)) and \
                (n.left is node or n.right is node):
            return n
    return None


def edit_vector(src: Source, expr, dx: float, dy: float) -> list[Edit] | None:
    """Edits that add (dx, dy) to a literal vector expression, touching only
    the numbers that change; None if the expression isn't that shape."""
    elts = _vector_list(expr)
    if elts is not None:
        out = []
        for i, d in ((0, dx), (1, dy)):
            if abs(d) > EPS:
                out.append(_renum(src, elts[i], number_of(elts[i]) + d))
        return out
    terms = _terms(expr)
    if not terms:
        return None
    parsed, origin = [], None
    for sign, node in terms:
        if isinstance(node, ast.Name) and node.id == "ORIGIN":
            origin = node
            continue
        t = _axis_term(node)
        if t is None:
            return None  # not a pure literal vector
        parsed.append((sign, node, *t))
    if not parsed and origin is not None and len(terms) == 1:
        a, b = src.span(expr)
        return [Edit(a, b, delta_expr(dx, dy))]
    edits, removed = [], set()
    for axis, d in ((0, dx), (1, dy)):
        if abs(d) < EPS:
            continue
        cands = [p for p in parsed if DIRS[p[2]][axis] != 0]
        if not cands:
            _, b = src.span(expr)
            edits.append(Edit(b, b, f" + {delta_expr(d if axis == 0 else 0, d if axis == 1 else 0)}"))
            continue
        # prefer a term with a written number, else the first one
        sign, node, name, coef, value = next((p for p in cands if p[3] is not None), cands[0])
        unit = DIRS[name][axis] * sign      # +1 if the term points along +axis
        new = round(value + d * unit, 4)
        parent = _parent_binop(expr, node)
        if abs(new) < SNAP and parent is not None and len(parsed) + (origin is not None) > 1:
            if parent.right is node:
                _, a = src.span(parent.left)
                _, b = src.span(node)
                edits.append(Edit(a, b, ""))       # drop " + 0 * RIGHT"
                removed.add(id(node))
                continue
            if isinstance(parent.op, ast.Add):
                a, _ = src.span(node)
                b, _ = src.span(parent.right)
                edits.append(Edit(a, b, ""))       # drop "0 * RIGHT + "
                removed.add(id(node))
                continue
        a, b = src.span(node)
        if abs(abs(new) - 1) < SNAP and (coef is not None or isinstance(node, ast.BinOp)):
            # back to a unit: written the way people write it (`UP`, not `1 * UP`),
            # so dragging `shift(UP)` away and back restores the bytes
            edits.append(Edit(a, b, name if new > 0 else f"-{name}"))
        elif coef is not None:
            edits.append(_renum(src, coef, new))
        elif isinstance(node, ast.BinOp):          # RIGHT / 2 -> RIGHT * 0.75
            edits.append(Edit(a, b, f"{name} * {_num(new)}"))
        else:                                      # RIGHT -> 1.4 * RIGHT, -UP -> -1.25 * UP
            edits.append(Edit(a, b, f"{_num(new)} * {name}"))
    return edits


# -- one placing call -------------------------------------------------------------------
def _chained_after(src: Source, call: ast.Call, method: str) -> ast.Call | None:
    """`<call>.method(...)` directly after `call`."""
    p = src.parent(call)
    if isinstance(p, ast.Attribute) and p.value is call and p.attr == method:
        q = src.parent(p)
        if isinstance(q, ast.Call) and q.func is p:
            return q
    return None


def _chain_end(src: Source, call: ast.Call) -> ast.Call:
    """The last call of `call.a(...).b(...)...` (call itself if nothing follows)."""
    c = call
    while True:
        p = src.parent(c)
        if not (isinstance(p, ast.Attribute) and p.value is c):
            return c
        q = src.parent(p)
        if not (isinstance(q, ast.Call) and q.func is p):
            return c
        c = q


def _remove_chained(src: Source, call: ast.Call) -> Edit:
    """Drop `.method(...)` from `x.method(...)`."""
    _, a = src.span(call.func.value)
    _, b = src.span(call)
    return Edit(a, b, "")


def _drop_or(src: Source, call: ast.Call, fallback):
    """A call that has become a no-op: remove it if it is chained, remove
    its statement if it stands alone, else make the fallback edit."""
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Call):
        return [_remove_chained(src, call)]
    stmt = statement_of(src, call)
    if isinstance(stmt, ast.Expr) and stmt.value is call:
        e = remove_statement(src, stmt)
        if e is not None:
            return [e]
    return fallback()


def _shift_edits(src: Source, call: ast.Call, dx, dy):
    v = eval_vector(call.args[0])
    if v is not None and abs(v[0] + dx) < SNAP and abs(v[1] + dy) < SNAP:
        return _drop_or(src, call, lambda: edit_vector(src, call.args[0], dx, dy))
    return edit_vector(src, call.args[0], dx, dy)


def _call_for(src: Source, mv: dict):
    call = src.find_call(Span(*mv["site"]))
    if call is None:
        return None
    if mv.get("kind") == "animate":
        # the site is the self.play(...) call; find the .animate.<method>(...)
        inner = [c for c in ast.walk(call) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                 and c.func.attr == mv["method"] and ".animate" in src.text(c.func.value)]
        return inner[0] if len(inner) == 1 else None
    return call


def plan_shift_on(src: Source, mv: dict, dx: float, dy: float) -> tuple[list, str] | None:
    """Edits that move what the call at mv["site"] placed by (dx, dy)."""
    call = _call_for(src, mv)
    if call is None or (mv.get("kind") != "animate" and _is_self_call(call)):
        return None
    name = Source.call_name(call)
    # 1. the call itself takes a literal vector
    if isinstance(call.func, ast.Attribute) and name in ("shift", "move_to") and len(call.args) == 1 \
            and not call.keywords:
        e = _shift_edits(src, call, dx, dy) if name == "shift" else edit_vector(src, call.args[0], dx, dy)
        if e is not None:
            return e, f"{name}() numbers changed (line {call.lineno})"
    where = " inside the .animate" if mv.get("kind") == "animate" else ""
    # a later call in the same chain may place it again (`helper().next_to(eq, UP)`):
    # the shift goes at the end, or into a shift already there
    end = _chain_end(src, call)
    if end is not call and Source.call_name(end) == "shift" and len(end.args) == 1 and not end.keywords:
        e = _shift_edits(src, end, dx, dy)
        if e is not None:
            return e, f"chained shift() numbers changed{where} (line {end.lineno})"
    # 2. a .shift(...) chained right after it: merge
    # (x.animate.next_to(...).shift(...) is fine: the builder applies them in order)
    outer = _chained_after(src, call, "shift")
    if outer is not None and len(outer.args) == 1 and not outer.keywords:
        e = _shift_edits(src, outer, dx, dy)
        if e is not None:
            return e, f"chained shift() numbers changed{where} (line {outer.lineno})"
    # 3. chain a new .shift(...)
    _, b = src.span(end)
    on = name if end is call else f"{name}()...{Source.call_name(end)}"
    return [Edit(b, b, f".shift({delta_expr(dx, dy)})")], \
        f"shift() chained on {on}(){where} (line {call.lineno})"


def plan_scale_on(src: Source, mv: dict, k: float, about: str | None = None) -> tuple[list, str] | None:
    call = _call_for(src, mv)
    if call is None or _is_self_call(call) or mv.get("kind") == "animate":
        return None
    about_kw = f", about_edge={about}" if about else ""

    def literal(c):
        if Source.call_name(c) in ("scale", "scale_to_fit_width", "scale_to_fit_height", "set_width",
                                   "set_height") and isinstance(c.func, ast.Attribute) and len(c.args) == 1 \
                and number_of(c.args[0]) is not None:
            kws = {kw.arg: src.text(kw.value) for kw in c.keywords}
            if Source.call_name(c) == "scale" and kws.get("about_edge") != about:
                return None
            if Source.call_name(c) == "scale" and set(kws) - {"about_edge"}:
                return None
            if Source.call_name(c) != "scale" and (about or c.keywords):
                return None
            return c
        return None

    for c in (call, _chained_after(src, call, "scale")):
        c = literal(c) if c is not None else None
        if c is None:
            continue
        new = number_of(c.args[0]) * k
        if Source.call_name(c) == "scale" and abs(new - 1) < 1e-6:
            return _drop_or(src, c, lambda: [set_number(src, c.args[0], 1)]), \
                f"{Source.call_name(c)}() removed (line {c.lineno})"
        return [_renum(src, c.args[0], new)], f"{Source.call_name(c)}() number changed (line {c.lineno})"
    _, b = src.span(call)
    return [Edit(b, b, f".scale({_num(k)}{about_kw})")], \
        f"scale() chained on {Source.call_name(call)}() (line {call.lineno})"


# -- angles ---------------------------------------------------------------------------
_ANGLE_NAMES = {"PI": math.pi, "TAU": math.tau, "DEGREES": math.pi / 180}


def eval_angle(node) -> float | None:
    """Radians of a literal angle expression (numbers, PI, TAU, DEGREES)."""
    if isinstance(node, ast.Name):
        return _ANGLE_NAMES.get(node.id)
    if number_of(node) is not None:
        return number_of(node)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = eval_angle(node.operand)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = eval_angle(node.left), eval_angle(node.right)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        return None if b == 0 else a / b
    return None


def _degrees_coef(node):
    """The number node in `n * DEGREES` / `DEGREES * n`, else None."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        a, b = node.left, node.right
        if isinstance(b, ast.Name) and b.id == "DEGREES" and number_of(a) is not None:
            return a
        if isinstance(a, ast.Name) and a.id == "DEGREES" and number_of(b) is not None:
            return b
    return None


def edit_angle(src: Source, expr, deg: float) -> list[Edit] | None:
    """Add `deg` degrees to a literal angle expression; [] when it becomes 0
    is decided by the caller (eval_angle of the result)."""
    coef = _degrees_coef(expr)
    if coef is not None:
        return [_renum(src, coef, number_of(coef) + deg)]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Sub)):
        c = _degrees_coef(expr.right)
        if c is not None and eval_angle(expr.left) is not None:
            sign = 1 if isinstance(expr.op, ast.Add) else -1
            new = round(sign * number_of(c) + deg, 4)
            if abs(new) < 1e-6:
                _, a = src.span(expr.left)
                _, b = src.span(expr)
                return [Edit(a, b, "")]               # drop " + 15 * DEGREES"
            return [_renum(src, c, new * sign)]
    if eval_angle(expr) is None:
        return None
    _, b = src.span(expr)
    op = "+" if deg >= 0 else "-"
    return [Edit(b, b, f" {op} {degrees_text(abs(deg))}")]


def plan_rotate_on(src: Source, mv: dict, deg: float) -> tuple[list, str] | None:
    call = _call_for(src, mv)
    if call is None or _is_self_call(call) or mv.get("kind") == "animate":
        return None
    for c in (call, _chained_after(src, call, "rotate")):
        if c is None or Source.call_name(c) != "rotate" or not isinstance(c.func, ast.Attribute) \
                or not c.args or c.keywords or len(c.args) > 1:
            continue
        old = eval_angle(c.args[0])
        if old is None:
            continue
        if abs(math.degrees(old) + deg) < 1e-4:
            return _drop_or(src, c, lambda: edit_angle(src, c.args[0], deg)), f"rotate() removed (line {c.lineno})"
        e = edit_angle(src, c.args[0], deg)
        if e is not None:
            return e, f"rotate() angle changed (line {c.lineno})"
    _, b = src.span(call)
    return [Edit(b, b, f".rotate({degrees_text(deg)})")], \
        f"rotate() chained on {Source.call_name(call)}() (line {call.lineno})"


# -- overrides (code_spec §5) -----------------------------------------------------------
def override_target(src: Source, obj: dict) -> tuple[str, ast.stmt] | None:
    """The shortest expression that reaches `obj` from a name, and the
    statement after which an override may go: `row[0][1]` after the row's
    last placement, `dots[2]` after `dots = [Dot(...) for ...]`."""
    p = obj.get("placement") or {}
    anc = p.get("ancestors") or []
    path: list[int] = []
    for a in anc:
        path.insert(0, a["index"])
        named = assigned_name(src, a.get("site")) or _name_via_chain(src, a.get("chain"))
        if not named:
            continue
        name, bind = named
        after = bind
        mv = a.get("move")
        if mv and mv.get("kind") == "static":
            for sp in [mv["site"]] + list(reversed(mv.get("chain") or [])):
                c = src.find_call(Span(*sp))
                st = statement_of(src, c) if c is not None else None
                if st is not None and block_of(src, st) is block_of(src, bind):
                    if st.lineno > after.lineno:
                        after = st
                    break
        after = _later_in_block(src, after, obj)
        return name + "".join(f"[{i}]" for i in path), after
    # an item of a list comprehension bound to a name: dots[2]
    site = obj.get("site")
    call = src.find_call(Span(*site)) if site else None
    comp = in_loop(src, call) if call is not None else None
    if isinstance(comp, ast.ListComp) and len(comp.generators) == 1 and not comp.generators[0].ifs \
            and comp.elt is call:
        stmt = statement_of(src, comp)
        if isinstance(stmt, ast.Assign) and stmt.value is comp and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            occ = _occurrence(obj.get("id"))
            if occ is not None:
                return f"{stmt.targets[0].id}[{occ}]", _later_in_block(src, stmt, obj)
    return None


def _occurrence(oid: str | None) -> int | None:
    try:
        return int(str(oid).rsplit("#", 1)[1])
    except (IndexError, ValueError):
        return None


def _later_in_block(src: Source, after, obj) -> ast.stmt:
    """After the object's own last placement too, if that is later in the
    same block (a loop that fills the group)."""
    blk = block_of(src, after)
    p = obj.get("placement") or {}
    for key in ("move", "create"):
        mv = p.get(key)
        if not mv:
            continue
        for sp in [mv["site"]] + list(mv.get("chain") or []):
            c = src.find_call(Span(*sp))
            st = statement_of(src, c) if c is not None else None
            while st is not None and blk is not None and not any(s is st for s in blk):
                st = statement_of(src, src.parent(st))
            if st is not None and st.lineno > after.lineno:
                after = st
    return after


def _next_shift_line(src: Source, after, expr: str):
    """`expr.shift(<vector>)` standing alone right after `after`, or None."""
    blk = block_of(src, after)
    if blk is None:
        return None
    i = next((j for j, st in enumerate(blk) if st is after), None)
    if i is None or i + 1 >= len(blk):
        return None
    st = blk[i + 1]
    c = st.value if isinstance(st, ast.Expr) else None
    if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "shift" \
            and len(c.args) == 1 and not c.keywords and src.text(c.func.value) == expr \
            and eval_vector(c.args[0]) is not None:
        return c
    return None


def _new_line(src: Source, after, expr: str, method: str, arg: str, delta=None) -> tuple[list, str]:
    """A new `expr.method(arg)` line after `after`; for a shift, folded into
    the one a previous drag wrote there (so a drag back removes it)."""
    if method == "shift" and delta is not None:
        c = _next_shift_line(src, after, expr)
        if c is not None:
            e = _shift_edits(src, c, *delta)
            if e is not None:
                return e, f"{expr}.shift() numbers changed (line {c.lineno})"
    return [insert_after(src, after, f"{expr}.{method}({arg})")], \
        f"new line {expr}.{method}() after line {after.end_lineno}"


def _override(src: Source, target, method: str, arg: str, delta=None) -> Candidate | None:
    if target is None:
        return None
    expr, after = target
    try:
        edits, note = _new_line(src, after, expr, method, arg, delta)
    except EditError:
        return None
    return Candidate(note, edits, kind="override")


# -- candidates ---------------------------------------------------------------------------
def _site_stmt(src: Source, span):
    c = src.find_call(Span(*span)) if span else None
    return (c, statement_of(src, c)) if c is not None else (None, None)


def _tuple_names(stmt) -> list[str]:
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Tuple):
        return [e.id for e in stmt.targets[0].elts if isinstance(e, ast.Name)]
    return []


def _for(src, obj, P, mv, op, plan_on, method, arg, what, delta=None) -> list[Candidate]:
    """Shared ranking for move / scale / rotate of one object."""
    out: list[Candidate] = []
    target = override_target(src, obj) if obj is not None else None
    call, stmt = _site_stmt(src, mv["site"])
    loop = in_loop(src, call) if call is not None else None
    chain = mv.get("chain") or []
    in_helper = len(chain) > 1
    if mv["kind"] == "laid_out":
        ov = _override(src, target, method, arg, delta)
        if ov:
            out.append(ov)
        group = next((a for a in (P.get("ancestors") or []) if a.get("site") == mv.get("group_site")), None)
        gmv = (group or {}).get("move") or {"site": mv["site"], "method": mv["method"], "kind": "static",
                                             "chain": chain}
        r = plan_on(src, gmv)
        if r:
            out.append(Candidate(f"{r[1]}: the whole group", r[0], kind="group",
                                 confirm=f"{what} the whole group this object was laid out in "
                                         f"(arrange at line {mv['site'][0]})"))
        return out
    if in_helper and mv["kind"] in ("static", "animation"):
        n = 0
        for outer in reversed(chain[:-1]):
            oc, ost = _site_stmt(src, outer)
            if oc is None or isinstance(ost, ast.Return):
                continue
            names = _tuple_names(ost)
            if names and ost.value is oc:
                for nm in names:   # the helper returns a tuple: name the part on a new line
                    try:
                        edits, note = _new_line(src, ost, nm, method, arg, delta)
                        out.append(Candidate(note, edits))
                    except EditError:
                        pass
                break
            r = plan_on(src, {"site": outer, "method": "call", "kind": "static"})
            if r:
                out.append(Candidate(f"{r[1]}, on this use of {mv['func']}()", r[0]))
                n += 1
                if n == 2:
                    break
    if loop is not None:
        ov = _override(src, target, method, arg, delta)
        if ov:
            out.append(ov)
    r = plan_on(src, mv)
    if r:
        confirm, kind = None, "local"
        if in_helper:
            confirm, kind = (f"line {mv['site'][0]} is inside {mv['func']}(): this {what} every "
                             f"object that helper makes"), "helper"
        elif loop is not None:
            confirm, kind = (f"line {mv['site'][0]} runs inside the loop at line {loop.lineno}: this "
                             f"{what} every object the loop makes"), "loop"
        out.append(Candidate(r[1], r[0], confirm, kind))
    if loop is None and not in_helper:
        ov = _override(src, target, method, arg, delta)
        if ov:
            out.append(ov)
    return out


def _check(src: Source, obj: dict):
    if not src.ok:
        raise EditError("the file doesn't parse")
    P = obj.get("placement") or {}
    if not P.get("create"):
        raise EditError("this object isn't made by code in the scene file")
    return P


def move_candidates(src: Source, obj: dict, dx: float, dy: float) -> list[Candidate]:
    P = _check(src, obj)
    mv = P.get("move") or P["create"]
    if mv["kind"] == "updater":
        raise EditError(f"its position is set every frame by an updater (line {mv['site'][0]}); "
                        "change it in the code")
    arg = delta_expr(dx, dy)
    parts = [(obj, P, mv)] + [(None, m, m.get("move") or m["create"]) for m in P.get("morphs") or []
                              if m.get("create")]
    per = [_for(src, o, p, m, "move", lambda s, x: plan_shift_on(s, x, dx, dy), "shift", arg, "moves", (dx, dy))
           for o, p, m in parts]
    if len(per) == 1:
        return per[0]
    if any(not c for c in per[1:]):
        return per[0]
    # Transform(a, b): move source and target together
    rest = [e for c in per[1:] for e in c[0].edits]
    note = " + ".join(c[0].note for c in per[1:])
    return [Candidate(f"{c.note} + {note} (the shape it turns into)", c.edits + rest, c.confirm, c.kind)
            for c in per[0]] + per[0]


def scale_candidates(src: Source, obj: dict, k: float, about: str | None = None) -> list[Candidate]:
    P = _check(src, obj)
    if about is not None and about not in EDGES:
        raise EditError(f"not an edge: {about!r}")
    if not (k > 0 and math.isfinite(k)):
        raise EditError("a scale must be a number more than 0")
    # scale after the last placement, so the centre (or the corner) stays put
    mv = P.get("move") or P["create"]
    if mv["kind"] in ("updater", "animate", "animation"):
        mv = P.get("scale") or P["create"]
    if P.get("scale", {}).get("order", -2) > mv.get("order", -1) and P["scale"]["kind"] == "static":
        mv = P["scale"]
    arg = _num(k) + (f", about_edge={about}" if about else "")
    return _for(src, obj, P, mv, "scale", lambda s, x: plan_scale_on(s, x, k, about), "scale", arg, "scales")


def rotate_candidates(src: Source, obj: dict, deg: float) -> list[Candidate]:
    P = _check(src, obj)
    if not math.isfinite(deg):
        raise EditError("not an angle")
    mv = P.get("move") or P["create"]
    if mv["kind"] in ("updater", "animate", "animation"):
        mv = P.get("rotate") or P["create"]
    if P.get("rotate", {}).get("order", -2) > mv.get("order", -1) and P["rotate"]["kind"] == "static":
        mv = P["rotate"]
    return _for(src, obj, P, mv, "rotate", lambda s, x: plan_rotate_on(s, x, deg), "rotate",
                degrees_text(deg), "rotates")
