"""Spike S5: how much of our real scene code could the studio edit?

Static census. Every simple statement inside a scene's construct() and in
module-level helper functions is put in a tier:

  tier 1  fully editable in the GUI: calls to known Manim / manim_kit /
          style API (or our own helpers), whose arguments are literals,
          constants (RIGHT, BLUE, TITLE_SIZE), arithmetic of those, or plain
          variable names. Example:
            blob = Blob(BLOB_COLOR, height=2.0).to_corner(DL, buff=0.7)
            self.play(FadeIn(title), run_time=0.8)
  tier 2  tweakable: the GUI shows it and can change its numbers and
          strings, but not its structure: arguments that read other
          objects (blob.get_top() + UP * 1.4), index into groups (rule[0]),
          comprehensions, f-strings, numpy math, simple for-loops over a
          literal range or list
  tier 3  code only: lambdas and updaters, always_redraw, while loops,
          if/else on computed values, nested defs, try, anything else

Compound statements (with/for/if) count once for their own line; their
bodies are classified statement by statement. Narration blocks
(`with self.say(...)`) count as tier 1.

  .venv/Scripts/python studio/spikes/s5_census.py pythagoras.py order_matters.py ...
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import manim  # noqa: E402

API = set(dir(manim))
for mod in ("manim_kit", "style"):
    try:
        API |= set(dir(__import__(mod)))
    except Exception:
        pass
API |= {"range", "len", "min", "max", "abs", "round", "list", "tuple", "zip", "enumerate",
        "float", "int", "str", "sum", "sorted", "reversed"}
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
    def __init__(self, tree: ast.Module, helpers: set[str]):
        self.helpers = helpers
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
        if isinstance(e, ast.Compare) or isinstance(e, ast.BoolOp) or isinstance(e, ast.IfExp):
            return 3
        if isinstance(e, ast.Lambda):
            return 3
        return 3

    def call_tier(self, c: ast.Call) -> int:
        f = c.func
        args = [self.expr_tier(a) for a in c.args] + [self.expr_tier(k.value) for k in c.keywords]
        worst = max([1] + args)
        if isinstance(f, ast.Name):
            if f.id in API or f.id in self.helpers:
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
            it = s.iter
            simple = isinstance(it, (ast.List, ast.Tuple)) or (
                isinstance(it, ast.Call) and isinstance(it.func, ast.Name)
                and it.func.id in ("range", "enumerate", "zip"))
            self.add(2 if simple and self.expr_tier(it) <= 2 else 3, s, where, header=True)
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
        self.by_kind[self.kind(s)][tier] += 1
        if len(self.examples[tier]) < 400:
            self.examples[tier].append((where, s.lineno))


def census(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    helpers = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    helpers |= {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    c = Census(tree, helpers)
    scope = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            scope.append((node.name, node.body))
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, ast.FunctionDef):
                    scope.append((f"{node.name}.{m.name}", m.body))
    for where, body in scope:
        for s in body:
            if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
                continue  # docstring
            c.stmt(s, where)
    total = sum(c.tiers.values())
    ex = {t: [f"{w}:{ln}: {lines[ln - 1].strip()[:90]}" for w, ln in c.examples[t]] for t in (1, 2, 3)}
    return {"statements": total, "tiers": {t: c.tiers[t] for t in (1, 2, 3)},
            "by_kind": {k: dict(v) for k, v in c.by_kind.items()},
            "pct": {t: round(100 * c.tiers[t] / total, 1) for t in (1, 2, 3)}, "examples": ex}


def main() -> int:
    files = sys.argv[1:] or ["test_scene.py", "pythagoras.py", "order_matters.py", "gradient_descent.py"]
    out = {}
    grand = Counter()
    for f in files:
        r = census(ROOT / f)
        out[f] = r
        grand.update(r["tiers"])
        print(f"{f:22} {r['statements']:4} statements | tier 1 {r['pct'][1]:5}%  tier 2 {r['pct'][2]:5}%"
              f"  tier 3 {r['pct'][3]:5}%")
    n = sum(grand.values())
    kinds = defaultdict(Counter)
    for r in out.values():
        for k, v in r["by_kind"].items():
            kinds[k].update(v)
    for k in ("timeline", "object", "layout", "style", "logic"):
        v = kinds[k]
        m = sum(v.values()) or 1
        print(f"  {k:9} {m:4} | tier 1 {100 * v[1] / m:5.1f}%  tier 2 {100 * v[2] / m:5.1f}%  tier 3 {100 * v[3] / m:5.1f}%")
    print(f"{'ALL':22} {n:4} statements | tier 1 {100 * grand[1] / n:5.1f}%  tier 2 {100 * grand[2] / n:5.1f}%"
          f"  tier 3 {100 * grand[3] / n:5.1f}%")
    dest = ROOT / "media" / "studio_spikes" / "s5"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "census.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
