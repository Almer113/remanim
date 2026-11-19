"""Regression tests for the review findings after Phase 5 (code layer)."""

import ast

import pytest

from studio.server.code import camera, graphs, inserts, moves, tex, transforms
from studio.server.code.census import classify
from studio.server.code.literals import find_literals, plan_literal
from studio.server.code.planner import plan_timing
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

H = "from manim import *\nclass S(Scene):\n    def construct(self):\n"


def sp(n):
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def calls(src, pred):
    return sorted((n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and pred(n)),
                  key=lambda n: (n.lineno, n.col_offset))


def named(name):
    return lambda n: getattr(n.func, "id", None) == name or getattr(n.func, "attr", None) == name


def run(code: bytes, plan) -> str:
    out = apply(code, plan.edits)
    assert Source(out).ok
    return out.decode()


# -- 1, 15: tex_to_color_map only when nothing can reach the parts ------------------------
FORMULA = "a^2 + b^2 = c^2"
GLYPHS = {"kind": "tex", "parts": [FORMULA],
          "map": [[0, 0, 1], [0, 1, 3], [0, 4, 5], [0, 6, 7], [0, 7, 9], [0, 10, 11], [0, 12, 13], [0, 13, 15]]}


def tex_plans(body: str, cls="MathTex"):
    code = (H + body).encode()
    src = Source(code)
    call = calls(src, named(cls))[0]
    obj = {"class": cls, "site": sp(call), "texts": [{"editable": True}]}
    try:
        return code, tex.candidates(src, obj, GLYPHS, [3], "RED")
    except EditError:
        return code, []


@pytest.mark.parametrize("body", [
    f'        self.eq = MathTex("{FORMULA}")\n        self.play(Indicate(self.eq[0][0:2]))\n',
    f'        g = VGroup(MathTex("{FORMULA}"), Text("x"))\n        self.play(Indicate(g[0][0][0:2]))\n',
    f'        eq = MathTex("{FORMULA}")\n        g = VGroup(eq)\n        self.play(Indicate(g[0][0][0:2]))\n',
    f'        eq = MathTex("{FORMULA}")\n        self.parts = eq\n',
    f'        eq = MathTex("{FORMULA}")\n        self.play(Indicate(eq.submobjects[0]))\n',
])
def test_isolation_refused_when_parts_are_reachable(body):
    _, plans = tex_plans(body)
    assert not any("tex_to_color_map" in p.note for p in plans)


def test_isolation_kept_for_a_plain_name_used_whole():
    code, plans = tex_plans(f'        eq = MathTex("{FORMULA}").shift(UP)\n'
                            '        eq.set_color(BLUE)\n        self.play(Write(eq))\n        self.add(eq)\n')
    assert "tex_to_color_map" in plans[0].note
    assert '"b": RED' in run(code, plans[0])


def test_isolation_kept_for_an_inline_formula():
    _, plans = tex_plans(f'        self.play(Write(MathTex("{FORMULA}")))\n')
    assert plans and "tex_to_color_map" in plans[0].note


def test_single_string_mathtex_has_no_part_head():
    code, plans = tex_plans(f'        eq = SingleStringMathTex("{FORMULA}")\n        self.add(eq)\n',
                            cls="SingleStringMathTex")
    assert [p.note for p in plans if "tex_to_color_map" in p.note] == []
    assert "eq[3].set_color(RED)" in run(code, plans[0])


# -- 4: adding to a dict with a trailing comma, or one entry per line ------------------------
def _t2c(code: bytes):
    src = Source(code)
    call = calls(src, named("Text"))[0]
    return apply(code, [tex._add_to_map(src, call, "t2c", "world", "BLUE")])


def test_add_to_dict_with_trailing_comma():
    out = _t2c(b't = Text("hello world", t2c={"hello": RED,})\n')
    assert Source(out).ok and b'{"hello": RED, "world": BLUE,}' in out


def test_add_to_black_style_dict():
    code = (H + '        t = Text("hello world", t2c={\n            "hello": RED,\n        })\n').encode()
    out = _t2c(code).decode()
    assert Source(out.encode()).ok
    assert '            "hello": RED,\n            "world": BLUE,\n        })' in out


def test_add_to_multiline_dict_without_trailing_comma():
    code = (H + '        t = Text("hello world", t2c={\n            "hello": RED\n        })\n').encode()
    out = _t2c(code).decode()
    assert Source(out.encode()).ok and '"hello": RED,\n            "world": BLUE\n' in out


# -- 2: loop passes found by value ----------------------------------------------------------
def at_plan(body: str, occ: int, start: float, duration: float, value: float):
    code = H + body
    src = Source(code.encode())
    c = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and src.text(n) == "self.at(t)")
    clip = {"kind": "wait", "call": sp(c), "call_name": "at", "start": start, "duration": duration,
            "occurrence": occ, "in_helper": False}
    return code, plan_timing(src, clip, "duration", value)


def test_loop_pass_refused_with_inner_loop():
    with pytest.raises(EditError):
        at_plan("        for t in (1.0, 3.0):\n            for j in range(2):\n"
                "                self.at(t)\n                self.play(FadeIn(Dot()))\n", 1, 2.0, 1.0, 1.0)


def test_loop_pass_refused_under_if():
    with pytest.raises(EditError):
        at_plan("        for t in (1.0, 3.0):\n            if t > 2:\n"
                "                self.at(t)\n            self.play(FadeIn(Dot()))\n", 0, 2.0, 1.0, 1.0)


def test_loop_pass_found_by_value_when_a_pass_made_no_event():
    # at(0.0) at time 0 makes no event: the first event (occurrence 0) is pass 2
    code, plan = at_plan("        for t in (0.0, 2.0, 4.0):\n            self.at(t)\n"
                         "            self.play(FadeIn(Dot()))\n", 0, 1.0, 1.0, 1.5)
    assert "(0.0, 2.5, 4.0)" in apply(code.encode(), plan.edits).decode()


def test_loop_pass_ambiguous_value_refused():
    with pytest.raises(EditError):
        at_plan("        for t in (2.0, 2.0):\n            self.at(t)\n"
                "            self.play(FadeIn(Dot()))\n", 0, 1.0, 1.0, 1.5)


def test_loop_pass_no_op_refused():
    with pytest.raises(EditError, match="already"):
        at_plan("        for t in (1.0, 3.0):\n            self.at(t)\n"
                "            self.play(FadeIn(Dot()))\n", 0, 0.5, 0.5, 0.501)


# -- 3: brace / duplicate / preset on a name given a new value ---------------------------------
REBOUND = (H + "        a = Circle()\n        self.add(a)\n        self.wait(1)\n"
           "        a = Square().shift(RIGHT * 3)\n        self.add(a)\n        self.wait(2)\n").encode()


def _rebound_setup():
    src = Source(REBOUND)
    waits = calls(src, named("wait"))
    events = [{"kind": "wait", "call": sp(waits[0]), "call_line": waits[0].lineno, "start": 0.0, "duration": 1.0},
              {"kind": "wait", "call": sp(waits[1]), "call_line": waits[1].lineno, "start": 1.0, "duration": 2.0}]
    obj = {"site": sp(calls(src, named("Circle"))[0]), "class": "Circle"}
    return src, events, obj


def test_composite_refuses_a_rebound_name():
    src, events, obj = _rebound_setup()
    with pytest.raises(EditError, match="new value"):
        inserts.plan_composite(src, "S", events, 15, False, "brace", 0, 0, 1.5, obj)


def test_duplicate_refuses_a_rebound_name():
    src, events, obj = _rebound_setup()
    with pytest.raises(EditError, match="new value"):
        inserts.plan_duplicate(src, "S", events, 15, False, obj, 1.5)


def test_composite_before_the_rebinding_still_works():
    src, events, obj = _rebound_setup()
    p = inserts.plan_composite(src, "S", events, 15, False, "brace", 0, 0, 0.5, obj)
    assert "Brace(a" in run(REBOUND, p)


# -- 12: the last construct() wins ---------------------------------------------------------
def test_scene_construct_takes_the_last_definition():
    src = Source((H + "        pass\n    def construct(self):\n        self.wait(2)\n").encode())
    assert inserts.scene_construct(src, "S").lineno == 5


# -- 5, 9, 13: 3D camera ----------------------------------------------------------------------
H3 = "from manim import *\nclass S(ThreeDScene):\n    def construct(self):\n"


def cam3(body: str, values: dict, t=0.5):
    code = (H3 + body).encode()
    src = Source(code)
    w = calls(src, named("wait"))[0]
    events = [{"kind": "wait", "call": sp(w), "call_line": w.lineno, "start": 0.0, "duration": 1.0}]
    return code, camera.plan_camera_3d(src, "S", events, t, values)


def test_camera_positional_angles():
    code, p = cam3("        self.set_camera_orientation(75 * DEGREES, -30 * DEGREES)\n        self.wait(1)\n",
                   {"phi": 60, "theta": 10})
    assert "self.set_camera_orientation(60 * DEGREES, 10 * DEGREES)" in run(code, p)


def test_camera_two_missing_keywords_in_one_insert():
    code, p = cam3("        self.set_camera_orientation()\n        self.wait(1)\n", {"phi": 60, "zoom": 1.2})
    assert "self.set_camera_orientation(phi=60 * DEGREES, zoom=1.2)" in run(code, p)


def test_camera_in_loop_asks_first():
    code, p = cam3("        for k in range(2):\n            self.set_camera_orientation(phi=70 * DEGREES)\n"
                   "            self.wait(1)\n", {"phi": 60})
    assert p.confirm and "loop" in p.confirm


def test_camera_one_line_construct_refused():
    code = b"from manim import *\nclass S(ThreeDScene):\n    def construct(self): self.wait(1)\n"
    src = Source(code)
    w = calls(src, named("wait"))[0]
    events = [{"kind": "wait", "call": sp(w), "call_line": 3, "start": 0.0, "duration": 1.0}]
    with pytest.raises(EditError, match="one line"):
        camera.plan_camera_3d(src, "S", events, 0.0, {"phi": 60})


# -- 6, 14: curve formulas --------------------------------------------------------------------
def curve(text: str, head: str = "import numpy as np\n", lam="lambda t: (t, t)"):
    code = (head + f"c = ax.plot_parametric_curve({lam}, t_range=[0, 1])\n").encode()
    src = Source(code)
    call = calls(src, named("plot_parametric_curve"))[0]
    return code, graphs.plan_curve(src, {"site": sp(call)}, text, {"np"})


def test_curve_tuple_starting_with_bracket_is_wrapped():
    code, p = curve("(t + 1) * 2, t")
    out = run(code, p)
    assert len(ast.parse(out).body[-1].value.args) == 1


def test_curve_already_wrapped_tuple_not_double_wrapped():
    code, p = curve("(t * 2, t)")
    assert "lambda t: (t * 2, t)," in run(code, p)


@pytest.mark.parametrize("text", ["t # comment", "(t,\n t)"])
def test_curve_comment_or_newline_refused(text):
    with pytest.raises(EditError):
        curve(text)


@pytest.mark.parametrize("text", [
    "np.savetxt('x', [t]), t", "np.load('x'), t", "open('x'), t", "eval('1'), t",
    "__import__('os'), t", "getattr(np, 'sin')(t), t", "np.random.rand(), t", "t.__class__, t",
])
def test_curve_non_maths_calls_refused(text):
    with pytest.raises(EditError):
        curve(text)


def test_curve_other_module_refused():
    with pytest.raises(EditError, match="maths"):
        curve("os.system('x'), t", head="import os\nimport numpy as np\n")
    with pytest.raises(EditError):
        curve("sin(t), t", head="from numpy import savetxt as sin\n")


def test_curve_maths_allowed():
    code, p = curve("np.sin(t) + np.sqrt(abs(t)), np.pi * np.heaviside(t, 0.5)")
    assert "np.sin(t)" in run(code, p)
    code, p = curve("math.cos(t), np.arccosh(t + 2)", head="import math\nimport numpy as np\n")
    assert "math.cos(t)" in run(code, p)


def test_curve_user_function_allowed():
    code, p = curve("func(t), t", head="import numpy as np\ndef func(x):\n    return x\n")
    assert "func(t)" in run(code, p)


def test_curve_other_lambdas_params_not_bound():
    code = (H + "        f = lambda q: q\n        c = ax.plot(lambda x: x, x_range=[0, 1])\n").encode()
    src = Source(code)
    call = calls(src, named("plot"))[0]
    with pytest.raises(EditError, match="isn't defined"):
        graphs.plan_curve(src, {"site": sp(call)}, "q * x", set())


def test_curve_names_bound_later_not_counted():
    code = (H + "        c = ax.plot(lambda x: x, x_range=[0, 1])\n        k = 2\n").encode()
    src = Source(code)
    call = calls(src, named("plot"))[0]
    with pytest.raises(EditError, match="isn't defined"):
        graphs.plan_curve(src, {"site": sp(call)}, "k * x", set())


# -- 7: only point-placed objects have their point edited ---------------------------------------
AXES = {"ax": {"o": [-3.0, -2.0], "ex": [0.5, 0.0], "ey": [0.0, 1.0]}}


def shift_on(code: str):
    src = Source(code.encode())
    call = src.tree.body[0].value
    tok = moves.COORDS.set(AXES)
    try:
        r = moves.plan_shift_on(src, {"site": sp(call), "kind": "create"}, 1.0, 0.0)
    finally:
        moves.COORDS.reset(tok)
    return apply(code.encode(), r[0]).decode()


@pytest.mark.parametrize("code", ["l = Line(ax.c2p(0, 0), ax.c2p(2, 4))\n", "v = Vector(ax.c2p(1, 2))\n",
                                  "p = Polygon(ax.c2p(0,0), ax.c2p(1,0), ax.c2p(0,1))\n"])
def test_shape_with_points_is_shifted_not_deformed(code):
    out = shift_on(code)
    assert out.startswith(code.rstrip("\n")) and ".shift(RIGHT)" in out


def test_dot_point_still_edited():
    assert shift_on("d = Dot(ax.c2p(0, 0))\n") == "d = Dot(ax.c2p(2, 0))\n"
    assert shift_on("d = LabeledDot('a', point=ax.c2p(0, 0))\n") == "d = LabeledDot('a', point=ax.c2p(2, 0))\n"


# -- 8, 11: literals ---------------------------------------------------------------------------
API = {"Scene", "Circle", "UP", "RIGHT", "Text", "MathTex"}


def literal(code: str, text: str, value: dict):
    src = Source(code.encode())
    c = classify(src.tree, API)
    lit = next(x for x in find_literals(src, c) if x["text"] == text)
    p = plan_literal(src, c, lit["span"], value)
    return apply(code.encode(), p.edits).decode(), p


def test_negative_base_of_power_is_bracketed():
    out, _ = literal(H + "        c = Circle(radius=3 ** 2)\n", "3", {"number": -3})
    assert "radius=(-3) ** 2" in out and eval("(-3) ** 2") == 9
    out, _ = literal(H + "        c = Circle(radius=2 ** 3)\n", "3", {"number": -1})
    assert "2 ** -1" in out


def test_negative_renum_after_drag_is_bracketed():
    src = Source(b"x = 3 ** 2\n")
    node = src.tree.body[0].value.left
    assert apply(src.data, [moves._renum(src, node, -2)]) == b"x = (-2) ** 2\n"


def test_literal_in_other_scene_method_asks_first():
    code = H + "        self.go()\n    def go(self):\n        c = Circle(radius=2)\n"
    _, p = literal(code, "2", {"number": 3})
    assert p.confirm and "S.go" in p.confirm
    _, p = literal(H + "        c = Circle(radius=2)\n", "2", {"number": 3})
    assert p.confirm is None


# -- 10: transform kinds ---------------------------------------------------------------------
def kind(body: str, new: str):
    code = (H + body).encode()
    src = Source(code)
    play = calls(src, named("play"))[0]
    return transforms.plan_kind(src, sp(play), 0, new)


def test_kind_store_after_load_on_one_line_sees_the_use():
    with pytest.raises(EditError, match="line 5"):
        kind("        self.play(Transform(a, b))\n        a = a.copy()\n", "ReplacementTransform")


def test_kind_non_name_argument_asks_first():
    p = kind("        self.play(Transform(eq[0], b))\n", "ReplacementTransform")
    assert p.confirm and "eq[0]" in p.confirm


def test_kind_in_loop_asks_first():
    p = kind("        for i in range(2):\n            self.play(Transform(a, b))\n", "ReplacementTransform")
    assert p.confirm and "loop" in p.confirm


def test_kind_from_copy_to_transform_warns_about_shape():
    p = kind("        self.play(Transform(a, b))\n        self.play(a.animate.shift(UP))\n", "TransformFromCopy")
    assert p.confirm and "keeps its own shape" in p.confirm
