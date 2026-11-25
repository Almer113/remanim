"""Tier of every statement (code_spec.md §2), from the Phase 0 census.

`api` is the set of names that count as known API (Manim, manim_kit,
style, builtins). The engine worker sends it once, so this module never
imports Manim.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict

BUILTINS = {"range", "len", "min", "max", "abs", "round", "list", "tuple", "zip", "enumerate",
            "float", "int", "str", "sum", "sorted", "reversed"}

# calls whose lambda arguments are formulas, not code: graphs and surfaces,
# point maps (`apply_function`), and the kit grid's matrix of time
PLOTTERS = {"plot", "plot_parametric_curve", "plot_polar_graph", "plot_implicit_curve", "get_graph",
            "plot_surface", "FunctionGraph", "ParametricFunction", "ImplicitFunction", "Surface",
            "ParametricSurface", "OpenGLSurface", "get_area", "plot_derivative_graph",
            "apply_function", "apply_complex_function", "ApplyPointwiseFunction", "ApplyComplexFunction",
            "ClippedGrid"}

# methods that read or set state and are part of the editable vocabulary
METHODS_T1 = {
    "play", "wait", "add", "remove", "at", "say", "line", "bring_to_front", "bring_to_back",
    "shift", "move_to", "next_to", "to_edge", "to_corner", "align_to", "arrange", "arrange_in_grid",
    "scale", "rotate", "flip", "stretch", "set_color", "set_fill", "set_stroke", "set_opacity",
    "set_z_index", "fade", "set_width", "set_height", "scale_to_fit_width", "scale_to_fit_height",
    "animate", "save_state", "copy", "set_value", "increment_value", "add_background_rectangle",
    "set_camera_orientation", "move_camera", "begin_ambient_camera_rotation",
    "stop_ambient_camera_rotation", "add_fixed_in_frame_mobjects", "set_mode", "look_at",
    "plot", "get_graph", "coords_to_point", "c2p", "match_style", "match_width", "match_height",
    "surround", "lock_to_target", "fade_all", "set_x", "set_y", "center",
}
READERS = {"get_top", "get_bottom", "get_left", "get_right", "get_center", "get_corner",
           "get_start", "get_end", "get_width", "get_height", "get_value", "point_from_proportion",
           "get_x", "get_y", "get_critical_point", "get_edge_center", "to_screen", "get_entries",
           "get_columns", "get_rows", "get_part_by_tex", "get_parts_by_tex", "get_vertices",
           "get_boundary_point", "get_tip", "get_vector", "get_angle", "width", "height"}


class Census:
    def __init__(self, api: set[str], helpers: set[str]):
        self.api = api
        self.helpers = helpers
        self.lines: dict[int, int] = {}
        self.tiers = Counter()
        self.by_kind = defaultdict(Counter)
        self.examples = defaultdict(list)

    # -- expressions -------------------------------------------------------
    def expr_tier(self, e) -> int:
        """1 literal-ish, 2 computed / relational, 3 code-only."""
        if e is None:
            return 1
        if isinstance(e, ast.Constant):
            return 1
        if isinstance(e, ast.Name):
            return 1  # constants and plain variables
        if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
            return max([1] + [self.expr_tier(x) for x in e.elts])
        if isinstance(e, ast.Dict):
            return max([1] + [self.expr_tier(x) for x in list(e.keys) + list(e.values) if x is not None])
        if isinstance(e, ast.UnaryOp):
            return self.expr_tier(e.operand)
        if isinstance(e, ast.BinOp):
            return max(self.expr_tier(e.left), self.expr_tier(e.right))
        if isinstance(e, ast.Starred):
            return max(2, self.expr_tier(e.value))
        if isinstance(e, ast.Call):
            return self.call_tier(e)
        if isinstance(e, ast.Attribute):
            if e.attr in READERS or e.attr == "animate":
                return max(2 if e.attr != "animate" else 1, self.expr_tier(e.value))
            if isinstance(e.value, ast.Name) and (e.value.id in ("self", "np", "config") or e.value.id.isupper()):
                return 2
            return max(2, self.expr_tier(e.value))
        if isinstance(e, ast.Subscript):
            return max(2, self.expr_tier(e.value), self.expr_tier(e.slice))
        if isinstance(e, ast.Slice):
            return max(2, *(self.expr_tier(x) for x in (e.lower, e.upper, e.step)))
        if isinstance(e, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)):
            inner = [self.expr_tier(g.iter) for g in e.generators]
            inner += [3 for g in e.generators if g.ifs]
            body = e.elt if not isinstance(e, ast.DictComp) else e.value
            return max([2, self.expr_tier(body)] + inner)
        if isinstance(e, ast.JoinedStr):
            return 2
        if isinstance(e, ast.FormattedValue):
            return max(2, self.expr_tier(e.value))
        if isinstance(e, ast.IfExp):
            # `0.7 if k < 3 else 0.45`: both branches' values (and the
            # condition's) are editable literals; the choice itself is code
            return max(2, self.cond_tier(e.test), self.expr_tier(e.body), self.expr_tier(e.orelse))
        if isinstance(e, (ast.Compare, ast.BoolOp, ast.Lambda)):
            return 3
        return 3

    def cond_tier(self, e) -> int:
        """A condition inside a conditional expression: comparisons of
        tier-1/2 values are tier 2 (their literals are editable)."""
        if isinstance(e, ast.Compare):
            return max([2, self.expr_tier(e.left)] + [self.expr_tier(c) for c in e.comparators])
        if isinstance(e, ast.BoolOp):
            return max([2] + [self.cond_tier(v) for v in e.values])
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            return max(2, self.cond_tier(e.operand))
        return self.expr_tier(e)

    def curve_tier(self, e) -> int:
        """A lambda handed to a plotting call (`axes.plot(lambda x: x**2)`):
        a formula of its parameters, tier 2 when the body is (its numbers
        are editable; Phase 5 step 7 edits the formula itself)."""
        if isinstance(e, ast.Lambda) and not e.args.vararg and not e.args.kwarg:
            return max(2, self.expr_tier(e.body))
        return self.expr_tier(e)

    def call_tier(self, c: ast.Call) -> int:
        f = c.func
        fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        arg = self.curve_tier if fname in PLOTTERS else self.expr_tier
        args = [arg(a) for a in c.args] + [arg(k.value) for k in c.keywords]
        worst = max([1] + args)
        if isinstance(f, ast.Name):
            if f.id in self.api or f.id in self.helpers:
                base = 1
            else:
                base = 2
            if f.id in ("always_redraw", "always"):
                return 3
            return max(base, worst)
        if isinstance(f, ast.Attribute):
            if f.attr in ("add_updater", "remove_updater", "add_fixed_orientation_mobjects"):
                return 3
            recv = self.expr_tier(f.value)
            if isinstance(f.value, ast.Name) and f.value.id == "np":
                return max(2, worst)
            if f.attr in METHODS_T1:
                return max(recv, worst)
            if f.attr in READERS:
                return max(2, recv, worst)
            return max(2, recv, worst)
        return 3

    # -- statements -----------------------------------------------------------
    def stmt(self, s, where: str):
        if isinstance(s, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            value = s.value
            t = self.expr_tier(value)
            if isinstance(s, ast.Assign) and any(not isinstance(tg, (ast.Name, ast.Tuple)) for tg in s.targets):
                t = max(t, 2)
            if isinstance(s, ast.AugAssign):
                t = max(t, 2)
            self.add(t, s, where)
        elif isinstance(s, ast.Expr):
            self.add(self.expr_tier(s.value), s, where)
        elif isinstance(s, ast.Return):
            self.add(self.expr_tier(s.value), s, where)
        elif isinstance(s, ast.With):
            narr = all(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Attribute)
                       and i.context_expr.func.attr in ("say", "voiceover") for i in s.items)
            self.add(1 if narr else 3, s, where, header=True)
            for b in s.body:
                self.stmt(b, where)
        elif isinstance(s, ast.For):
            # A loop over values the GUI can edit (a literal list, range(3), a
            # named constant, a group, a slice of one): the header's own
            # values are editable; a constant is edited where it is made.
            it = s.iter
            simple_target = all(isinstance(t, ast.Name) for t in ast.walk(s.target)
                                if not isinstance(t, (ast.Tuple, ast.List, ast.Store)))
            self.add(2 if simple_target and self.expr_tier(it) <= 2 else 3, s, where, header=True)
            for b in s.body + s.orelse:
                self.stmt(b, where)
        elif isinstance(s, ast.If):
            self.add(3, s, where, header=True)
            for b in s.body + s.orelse:
                self.stmt(b, where)
        elif isinstance(s, (ast.Pass,)):
            return
        else:  # while, try, nested def/class, del, global, ...
            self.add(3, s, where, header=True)

    @staticmethod
    def kind(s) -> str:
        """What the statement is for: timeline, object, layout, style, logic."""
        if isinstance(s, (ast.For, ast.If, ast.While, ast.Try, ast.FunctionDef, ast.ClassDef)):
            return "logic"
        if isinstance(s, ast.With):
            return "timeline"
        v = getattr(s, "value", None)
        calls = [n for n in ast.walk(v)] if v is not None else []
        attrs = {n.func.attr for n in calls if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        if attrs & {"play", "wait", "at", "say", "line", "add", "remove", "move_camera",
                    "set_camera_orientation", "begin_ambient_camera_rotation", "lock_to_target", "fade_all"}:
            return "timeline"
        if attrs & {"shift", "move_to", "next_to", "to_edge", "to_corner", "align_to", "arrange",
                    "arrange_in_grid", "scale", "rotate", "set_x", "set_y", "center",
                    "scale_to_fit_width", "scale_to_fit_height"} or                 any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("place",)
                    for n in calls):
            if isinstance(s, ast.Assign):
                return "object"  # made and placed in one statement
            return "layout"
        if attrs & {"set_color", "set_fill", "set_stroke", "set_opacity", "fade", "set_z_index"}:
            return "style"
        if isinstance(s, (ast.Assign, ast.Return)) and isinstance(v, ast.Call):
            return "object"
        return "logic"

    def add(self, tier, s, where, header=False):
        self.tiers[tier] += 1
        self.lines[s.lineno] = max(self.lines.get(s.lineno, 0), tier)
        self.by_kind[self.kind(s)][tier] += 1
        if len(self.examples[tier]) < 400:
            self.examples[tier].append((where, s.lineno))


def classify(tree: ast.Module, api: set[str]) -> Census:
    helpers = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    c = Census(set(api) | BUILTINS, helpers)
    for node in tree.body:
        bodies = []
        if isinstance(node, ast.FunctionDef):
            bodies.append((node.name, node.body))
        elif isinstance(node, ast.ClassDef):
            bodies += [(f"{node.name}.{m.name}", m.body) for m in node.body if isinstance(m, ast.FunctionDef)]
        for where, body in bodies:
            for s in body:
                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
                    continue  # docstring
                c.stmt(s, where)
    return c


def summary(c: Census) -> dict:
    total = sum(c.tiers.values()) or 1
    return {"statements": sum(c.tiers.values()), "tiers": {str(t): c.tiers[t] for t in (1, 2, 3)},
            "pct": {str(t): round(100 * c.tiers[t] / total, 1) for t in (1, 2, 3)},
            "lines": {str(k): v for k, v in sorted(c.lines.items())}}
