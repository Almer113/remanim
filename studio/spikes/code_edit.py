"""Spike S2: turn a drag in the viewer into the smallest edit of the .py file.

Two parts:

MoveRecorder  - while a scene replays, every positioning call on a mobject
                (shift, move_to, next_to, to_edge, place(), ...) is recorded
                on that mobject with the exact source span of the scene-file
                call that caused it. Creation counts as the first "move".
plan_move()   - given the call that last put the object where it is and a
                drag (dx, dy), returns byte-range edits:
                  * literal vector there (`.move_to(RIGHT * 3.6 + DOWN * 1.2)`,
                    `.shift(0.5 * UP)`): change only the numbers
                  * a `.shift(...)` already chained right after the call:
                    merge into it (and remove it if it becomes zero)
                  * anything else (`next_to`, `place(...)`, a constructor):
                    chain `.shift(<delta>)` right after the call
Edits are byte splices into the original file (never regenerated from the
AST), so every other byte, comment and blank line stays as it was.
"""

from __future__ import annotations

import ast
import itertools
import sys
from dataclasses import dataclass
from pathlib import Path

from manim import Mobject

from identity import Site, _site

MOVE_METHODS = ("shift", "move_to", "next_to", "to_edge", "to_corner", "align_to",
                "set_x", "set_y", "center", "arrange", "arrange_in_grid")
GROUP_LAYOUT = ("arrange", "arrange_in_grid")
_clock = itertools.count()


@dataclass
class Move:
    order: int
    method: str
    site: Site          # the innermost scene-file call on the stack
    kind: str           # "static", "animate", "updater", "laid_out"
    chain: list         # every scene-file call on the stack, outermost first
    group: object = None  # for "laid_out": the group whose arrange() placed it
    path: tuple = ()      # for "laid_out": index path from that group to the object


class MoveRecorder:
    def __init__(self, tracker):
        self.tracker = tracker  # identity.OriginTracker: knows the user files
        self.depth = 0
        self._orig = {}
        for name in MOVE_METHODS:
            orig = getattr(Mobject, name)
            self._orig[name] = orig
            setattr(Mobject, name, self._wrap(name, orig))

    def _wrap(self, name, orig):
        rec = self

        def method(mob, *a, **k):
            rec.depth += 1
            try:
                return orig(mob, *a, **k)
            finally:
                rec.depth -= 1
                if rec.depth == 0:  # outermost call only (next_to calls shift)
                    rec._record(mob, name)
        method.__name__ = name
        return method

    def _record(self, mob, name):
        f = sys._getframe(2)
        chain, kind, owner = [], "static", mob
        while f is not None:
            co = f.f_code
            if self.tracker._is_user(f):
                chain.append(_site(f))
            elif co.co_name == "update_target" and co.co_filename.endswith("mobject.py"):
                # mob.animate.<method>(...) is applied to mob.target right
                # away; the move belongs to the real mobject
                b = f.f_locals.get("self")
                if b is not None and hasattr(b, "mobject"):
                    if getattr(b.mobject, "target", None) is not mob:
                        return  # a part of the target moved (Blob.look_at moves pupils)
                    owner, kind = b.mobject, "animate"
            elif co.co_name == "update" and co.co_filename.endswith("mobject.py"):
                kind = "updater"
            f = f.f_back
        if not chain:
            return
        chain.reverse()
        mv = Move(next(_clock), name, chain[-1], kind, chain)
        owner.__dict__.setdefault("_studio_moves", []).append(mv)
        if name in GROUP_LAYOUT and kind == "static":
            # everything inside was placed by this layout call, even if the
            # group itself never reaches the screen
            def mark(m, path):
                for i, child in enumerate(m.submobjects):
                    child.__dict__.setdefault("_studio_moves", []).append(
                        Move(mv.order, name, mv.site, "laid_out", chain, group=owner, path=path + (i,)))
                    mark(child, path + (i,))
            mark(owner, ())

    def uninstall(self):
        for name, orig in self._orig.items():
            setattr(Mobject, name, orig)


class MorphRecorder:
    """Transform(a, b) makes a take b's shape: from then on, what is drawn
    as `a` is placed by b's code as much as a's. Remember b on a (only a b
    the user made: FadeIn and friends transform into internal copies)."""

    def __init__(self):
        from manim import Transform
        self._orig = Transform.begin

        def begin(anim):
            target = getattr(anim, "target_mobject", None)
            o = getattr(target, "_studio_origin", None)
            if target is not None and target is not anim.mobject and o is not None \
                    and o.site is not None and o.copied_from is None:
                anim.mobject.__dict__.setdefault("_studio_morphs", []).append(target)
            return self._orig(anim)
        Transform.begin = begin


def last_move(mob) -> Move | None:
    own = getattr(mob, "_studio_moves", [])
    if own:
        return own[-1]
    o = getattr(mob, "_studio_origin", None)
    if o is not None and o.site is not None:
        return Move(-1, "create", o.site, "static", list(o.chain))
    if o is not None and o.user_site is not None:
        # built inside a library call: that call's result may be it
        # (`grid.snapshot()`); verify-by-replay finds out
        return Move(-1, "create", o.user_site, "static", list(o.chain))
    return None


def candidates(mob, src: "Source", dx: float, dy: float) -> list:
    """Ranked edits that should move `mob` by (dx, dy) at the current time,
    as [(note, [Edit, ...]), ...]. The caller applies the first, replays,
    and falls back to the next if the object didn't move exactly
    (verify-by-replay)."""
    parts = [mob] + getattr(mob, "_studio_morphs", [])
    per_part = [_candidates_one(m, src, dx, dy) for m in parts]
    if any(not c for c in per_part):
        return []
    if len(per_part) == 1:
        return per_part[0]
    # Transform: move source and target together (best option of each,
    # then alternatives for the main part)
    rest = [e for c in per_part[1:] for e in c[0][1]]
    rest_note = " + ".join(c[0][0] for c in per_part[1:])
    return [(f"{n} + {rest_note}", e + rest) for n, e in per_part[0]]


def _candidates_one(mob, src, dx, dy) -> list:
    mv = last_move(mob)
    if mv is None:
        return []
    out = []
    if mv.kind == "laid_out":
        ins = _insert_after_layout(mob, mv, src, dx, dy)
        if ins:
            out.append(ins)
        e, note = plan_move(src, _group_last_move(mv), dx, dy)
        if e:
            out.append((f"move the whole group: {note}", e))
        return out
    in_helper = len(mv.chain) > 1
    if in_helper and mv.kind == "static":
        # made/placed inside a helper: edit THIS use of the helper first
        # (editing inside it would move every object it makes)
        # nearest enclosing call first: get_heading() inside get_panel()
        # should move the heading, not the whole panel
        for outer in reversed(mv.chain[:-1]):
            e, note = plan_move(src, Move(-1, "call", outer, "static", []), dx, dy)
            if e:
                # (plan_move merges into a .shift() already chained there)
                out.append((f"{note} on the call in {outer.func}() line {outer.line}", e))
                if len(out) == 2:
                    break
    e, note = plan_move(src, mv, dx, dy)
    if e:
        out.append((note + (" inside the helper (all its uses move)" if in_helper else ""), e))
    return out


def _group_last_move(mv) -> Move:
    """The group's last static placement at or after its layout call, in
    the same function (a later next_to()/move_to() re-centres the group)."""
    last = Move(mv.order, mv.method, mv.site, "static", mv.chain)
    for gm in getattr(mv.group, "_studio_moves", []):
        if gm.kind == "static" and gm.order >= mv.order and gm.site.func == mv.site.func:
            last = gm
    return last


def _insert_after_layout(mob, mv, src, dx, dy):
    """`<name>.shift(...)` as a new statement right after the layout
    statement: the object's own variable if it is in scope there, else
    a path from the group's variable (`row[0][1]`)."""
    # after the group's LAST placement (a later next_to()/move_to() would
    # re-centre the group and undo part of the shift), in the same function
    gm = _group_last_move(mv)
    stmt = src.statement_at(gm.site)
    if stmt is None or isinstance(stmt, ast.Return):
        return None
    name = src.name_of(mob)
    o = getattr(mob, "_studio_origin", None)
    if name is not None and (o is None or o.site.func != mv.site.func):
        name = None  # bound in another function: not in scope here
    if name is None:
        # the group's variable: assigned by the layout statement, or where
        # the group was made
        layout_stmt = src.statement_at(mv.site)
        gname = (src.assigned_name(layout_stmt) if layout_stmt is not None else None)             or src.name_of(mv.group)
        if gname is None or not mv.path:
            return None
        name = gname + "".join(f"[{i}]" for i in mv.path)
    line_end = src.line_starts[stmt.end_lineno] if stmt.end_lineno < len(src.line_starts) else len(src.data)
    first = src.data[src.line_starts[stmt.lineno - 1]:]
    indent = first[:len(first) - len(first.lstrip(b" \t"))].decode()
    nl = "\r\n" if src.data[line_end - 2:line_end] == b"\r\n" else "\n"
    return (f"new line {name}.shift() after the layout",
            [Edit(line_end, line_end, f"{indent}{name}.shift({delta_expr(dx, dy)}){nl}")])


# -- the code side ------------------------------------------------------------

DIRS = {"RIGHT": (1, 0), "LEFT": (-1, 0), "UP": (0, 1), "DOWN": (0, -1), "ORIGIN": (0, 0)}


@dataclass
class Edit:
    start: int  # byte offsets into the file
    end: int
    text: str


class Source:
    def __init__(self, data: bytes):
        self.data = data
        self.tree = ast.parse(data)
        self.line_starts = [0]
        for i, b in enumerate(data):
            if b == 0x0A:
                self.line_starts.append(i + 1)

    def offset(self, line: int, col: int) -> int:
        return self.line_starts[line - 1] + col  # ast cols are UTF-8 byte offsets

    def span(self, node) -> tuple[int, int]:
        return (self.offset(node.lineno, node.col_offset),
                self.offset(node.end_lineno, node.end_col_offset))

    def text(self, node) -> str:
        a, b = self.span(node)
        return self.data[a:b].decode("utf-8")

    def statement_at(self, site: Site):
        """The innermost simple statement containing the call at `site`."""
        best = None
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.Return)) \
                    and node.lineno <= site.line <= node.end_lineno:
                if best is None or node.lineno >= best.lineno:
                    best = node
        return best

    @staticmethod
    def assigned_name(stmt) -> str | None:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            return stmt.targets[0].id
        return None

    def name_of(self, mob) -> str | None:
        """The variable a mobject was assigned to where it was made:
        `neq = MathTex(...)` -> "neq". The creation call must be the
        right-hand side, or the head of a method chain on it."""
        o = getattr(mob, "_studio_origin", None)
        if o is None or o.site is None:
            return None
        stmt = self.statement_at(o.site)
        name = self.assigned_name(stmt) if stmt is not None else None
        if name is None:
            return None
        want = (o.site.line, o.site.col, o.site.end_line, o.site.end_col)
        v = stmt.value
        while True:
            if isinstance(v, ast.Call) and (v.lineno, v.col_offset, v.end_lineno, v.end_col_offset) == want:
                return name
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute):
                v = v.func.value
            else:
                return None

    def find_call(self, site: Site) -> tuple[ast.Call | None, ast.AST | None]:
        """The Call node for the call at `site`, and its parent node.

        Python reports a method call `recv.name(...)` from the method name
        onwards when the receiver spans lines, and from the receiver start
        otherwise; both are accepted. The end position must match exactly."""
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                if not isinstance(child, ast.Call) or                         (child.end_lineno, child.end_col_offset) != (site.end_line, site.end_col):
                    continue
                if (child.lineno, child.col_offset) == (site.line, site.col):
                    return child, parent
                f = child.func
                if isinstance(f, ast.Attribute) and f.end_lineno == site.line and                         f.end_col_offset - len(f.attr) == site.col:
                    return child, parent
        return None, None


def fmt(v: float, like: str | None = None) -> str:
    """Shortest decimal form, with a decimal point if the original had one
    (0.25 + 0.25 -> "0.5"; "1.0" stays "1.0", never "1")."""
    for d in range(1 if like and "." in like else 0, 4):
        s = f"{v:.{d}f}"
        if abs(float(s) - v) < 1e-9:
            return s
    return f"{v:.2f}"


def delta_expr(dx: float, dy: float) -> str:
    terms = []
    if abs(dx) > 1e-9:
        terms.append(f"{fmt(abs(dx))} * {'RIGHT' if dx > 0 else 'LEFT'}")
    if abs(dy) > 1e-9:
        terms.append(f"{fmt(abs(dy))} * {'UP' if dy > 0 else 'DOWN'}")
    return " + ".join(terms)


def _terms(node):
    """Flatten a +/- chain into (sign, node) terms."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left = _terms(node.left)
        right = _terms(node.right)
        if left is None or right is None:
            return None
        s = -1 if isinstance(node.op, ast.Sub) else 1
        return left + [(sg * s, n) for sg, n in right]
    return [(1, node)]


def _axis_term(node):
    """(axis, direction sign, Constant node or None) for `c * RIGHT`,
    `RIGHT * c`, `RIGHT`; None if not that shape."""
    if isinstance(node, ast.Name) and node.id in DIRS and node.id != "ORIGIN":
        return node.id, None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        a, b = node.left, node.right
        if isinstance(b, ast.Name):
            a, b = b, a
        if isinstance(a, ast.Name) and a.id in DIRS and a.id != "ORIGIN" and \
                isinstance(b, ast.Constant) and isinstance(b.value, (int, float)):
            return a.id, b
    return None


def _parent_binop(root, node):
    for n in ast.walk(root):
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)) and \
                (n.left is node or n.right is node):
            return n
    return None


def edit_vector(src: Source, expr, dx: float, dy: float) -> list[Edit] | None:
    """Edits that add (dx, dy) to a literal vector expression, touching only
    the numbers that change; None if the expression isn't that shape."""
    terms = _terms(expr)
    if not terms:
        return None
    parsed = []
    for sign, node in terms:
        t = _axis_term(node)
        if t is None:
            if isinstance(node, ast.Name) and node.id == "ORIGIN":
                continue
            return None  # not a pure literal vector
        parsed.append((sign, node, *t))
    edits = []
    for axis, d in ((0, dx), (1, dy)):
        if abs(d) < 1e-9:
            continue
        cands = [p for p in parsed if DIRS[p[2]][axis] != 0 and p[3] is not None]
        if cands:
            sign, node, name, const = cands[0]
            unit = DIRS[name][axis] * sign  # +1 if the term points +axis
            new = const.value + d * unit
            parent = _parent_binop(expr, node)
            if abs(new) < 1e-9 and parent is not None and parent.right is node:
                # `... + 0 * RIGHT`: drop the term with its operator
                _, a = src.span(parent.left)
                _, b = src.span(node)
                edits.append(Edit(a, b, ""))
                continue
            a, b = src.span(const)
            edits.append(Edit(a, b, fmt(round(new, 4), src.text(const))))
        else:
            a, b = src.span(expr)
            add = delta_expr(d if axis == 0 else 0, d if axis == 1 else 0)
            edits.append(Edit(b, b, f" + {add}"))
    return edits


def eval_vector(expr) -> tuple[float, float] | None:
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
        name, const = t
        c = sign * (const.value if const is not None else 1)
        x += c * DIRS[name][0]
        y += c * DIRS[name][1]
    return x, y


def _shift_edits(src: Source, shift_call, dx, dy, chained: bool):
    """Edit a .shift(vec) call. A chained shift that becomes zero is removed,
    so dragging back restores the original text."""
    v = eval_vector(shift_call.args[0])
    if v is not None and chained and abs(v[0] + dx) < 1e-9 and abs(v[1] + dy) < 1e-9:
        _, a = src.span(shift_call.func.value)
        _, b = src.span(shift_call)
        return [Edit(a, b, "")]
    return edit_vector(src, shift_call.args[0], dx, dy)


def plan_move(src: Source, move: Move, dx: float, dy: float) -> tuple[list[Edit], str]:
    """Edits that move the object placed by `move`."""
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return [], "no-op"
    call, parent = src.find_call(move.site)
    if call is None:
        return [], "call not found"
    if move.kind == "animate":
        # the site is the self.play(...) call; find the .animate.<method>(...)
        inner = [c for c in ast.walk(call) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Attribute) and c.func.attr == move.method
                 and ".animate" in src.text(c.func.value)]
        if len(inner) != 1:
            return [], f"{len(inner)} .animate.{move.method}() calls in that play()"
        call = inner[0]
    # 1. the call itself takes a literal vector
    if isinstance(call.func, ast.Attribute) and call.func.attr in ("shift", "move_to") \
            and len(call.args) == 1 and not call.keywords:
        if call.func.attr == "shift":
            chained = isinstance(call.func.value, ast.Call)
            v = eval_vector(call.args[0])
            stmt = src.statement_at(move.site)
            if not chained and v is not None and abs(v[0] + dx) < 1e-9 and abs(v[1] + dy) < 1e-9 \
                    and isinstance(stmt, ast.Expr) and stmt.value is call:
                # `name.shift(v)` on its own line, now zero: remove the line
                a = src.line_starts[stmt.lineno - 1]
                b = src.line_starts[stmt.end_lineno] if stmt.end_lineno < len(src.line_starts) else len(src.data)
                return [Edit(a, b, "")], "shift() statement removed"
            e = _shift_edits(src, call, dx, dy, chained)
        else:
            e = edit_vector(src, call.args[0], dx, dy)
        if e is not None:
            return e, f"{call.func.attr}(): numbers changed"
    # 2. a .shift(...) chained right after it: merge
    outer = None
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                node.func.value is call and node.func.attr == "shift" and len(node.args) == 1:
            outer = node
            break
    if outer is not None:
        e = _shift_edits(src, outer, dx, dy, chained=True)
        if e is not None:
            return e, "chained shift(): numbers changed"
    # 3. chain a new .shift(...) after the call
    _, b = src.span(call)
    return [Edit(b, b, f".shift({delta_expr(dx, dy)})")], "shift() chained"


def apply(data: bytes, edits: list[Edit]) -> bytes:
    out = data
    for e in sorted(edits, key=lambda e: e.start, reverse=True):
        out = out[:e.start] + e.text.encode("utf-8") + out[e.end:]
    return out
