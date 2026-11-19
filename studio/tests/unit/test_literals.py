"""Phase 5 step 2: tier-2 literal editing and the census patterns behind it."""

import ast

import pytest

from studio.server.code.census import classify
from studio.server.code.literals import find_literals, plan_literal
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

API = {"Scene", "Text", "Circle", "Dot", "Axes", "FadeIn", "Create", "UP", "RIGHT", "LEFT", "BLUE", "RED",
       "ORIGIN", "DEGREES", "VGroup", "ClippedGrid", "rotation", "TAU", "smooth"}

HEAD = "from manim import *\n\nLEVELS = [0.5, 1, 2]\n\nclass S(Scene):\n    TARGET = 6.0\n\n    def construct(self):\n"


def scene(*lines):
    return HEAD + "".join("        " + ln + "\n" for ln in lines)


def lits(code):
    src = Source(code.encode())
    return src, classify(src.tree, API), find_literals(src, classify(src.tree, API))


def edit(code, text, value, line=None):
    src, census, found = lits(code)
    lit = next(x for x in found if x["text"] == text
               and (x["span"][0] == line if line is not None else x["scope"] != "constant"))
    plan = plan_literal(src, census, lit["span"], value)
    out = apply(code.encode(), plan.edits).decode()
    ast.parse(out)
    return out, plan


def tier(code, needle):
    src = Source(code.encode())
    c = classify(src.tree, API)
    line = next(i for i, ln in enumerate(code.splitlines(), 1) if needle in ln)
    return c.lines[line]


# -- census patterns ---------------------------------------------------------------
def test_conditional_expression_is_tier_2():
    assert tier(scene("for k in range(5):", "    rt = 0.7 if k < 3 else 0.45"), "rt =") == 2
    assert tier(scene("rt = 0.7 if not (1 < 2 and 3 > 2) else 0.45"), "rt =") == 2


def test_if_statement_stays_tier_3():
    assert tier(scene("if True:", "    pass"), "if True") == 3


def test_loops_over_values_are_tier_2():
    code = scene("dots = VGroup(Dot(), Dot())", "for level in LEVELS:", "    pass",
                 "for d in dots[1:]:", "    d.set_color(RED)", "for i, d in enumerate(dots):", "    pass")
    assert tier(code, "for level") == 2
    assert tier(code, "for d in") == 2
    assert tier(code, "for i, d") == 2


def test_loop_with_fancy_target_stays_tier_3():
    assert tier(scene("box = [0]", "for box[0] in range(3):", "    pass"), "for box") == 3


def test_curve_lambdas_are_tier_2_updaters_are_not():
    code = scene("axes = Axes()", "c = axes.plot(lambda x: 0.5 * x ** 2, x_range=[-2, 2])",
                 "d = Dot()", "d.add_updater(lambda m: m.move_to(UP))",
                 "g = ClippedGrid(('ellipse', ORIGIN, 3, 2), matrix_of=lambda t: rotation(TAU * t))")
    assert tier(code, "axes.plot") == 2
    assert tier(code, "add_updater") == 3
    assert tier(code, "ClippedGrid") == 2


def test_a_condition_in_a_curve_stays_tier_3():
    assert tier(scene("axes = Axes()", "c = axes.plot(lambda x: x if x > 0 else 0)"), "axes.plot") == 2
    assert tier(scene("axes = Axes()", "c = axes.plot(lambda x: x > 0)"), "axes.plot") == 3


# -- finding values ----------------------------------------------------------------
def test_finds_numbers_strings_and_constants():
    code = scene('t = Text("Hi", font_size=36).shift(UP * 1.4 + -0.5 * RIGHT)')
    _, _, found = lits(code)
    texts = [x["text"] for x in found if x["scope"] == "method"]
    assert texts == ['"Hi"', "36", "UP", "1.4", "-0.5", "RIGHT"]


def test_module_and_class_constants_are_found():
    _, _, found = lits(scene("pass"))
    consts = {x["text"] for x in found if x["scope"] == "constant"}
    assert consts == {"0.5", "1", "2", "6.0"}


def test_skips_tier_3_fstrings_docstrings_and_units():
    code = scene('"""doc"""', 'x = f"n={3}"', "a = 30 * DEGREES", "d = Dot()",
                 "d.add_updater(lambda m: m.shift(UP * 0.1))")
    _, _, found = lits(code)
    texts = [x["text"] for x in found if x["scope"] == "method"]
    assert texts == ["30"]


# -- editing ------------------------------------------------------------------------
def test_edit_branch_of_a_conditional():
    code = scene("for k in range(5):", "    rt = 0.7 if k < 3 else 0.45")
    out, plan = edit(code, "0.45", {"number": 0.5})
    assert "rt = 0.7 if k < 3 else 0.5" in out and plan.confirm is None


def test_edit_keeps_number_style_and_sign():
    out, _ = edit(scene("d = Dot().shift(-0.5 * RIGHT)"), "-0.5", {"number": -1})
    assert "d = Dot().shift(-1.0 * RIGHT)" in out
    out, _ = edit(scene("d = Dot().shift(2 * RIGHT)"), "2", {"number": 3})
    assert "shift(3 * RIGHT)" in out


def test_edit_string_keeps_quotes():
    out, _ = edit(scene("t = Text('Hi')"), "'Hi'", {"string": "It's"})
    assert "Text('It\\'s')" in out


def test_edit_constant_name():
    out, _ = edit(scene("c = Circle(color=BLUE)"), "BLUE", {"name": "RED"})
    assert "Circle(color=RED)" in out


def test_edit_constant_asks_and_names_its_users():
    code = scene("for level in LEVELS:", "    pass")
    out, plan = edit(code, "2", {"number": 3}, line=3)
    assert "LEVELS = [0.5, 1, 3]" in out
    assert "line" in plan.confirm and "they all change" in plan.confirm


def test_refusals():
    code = scene("d = Dot().shift(2 * RIGHT)")
    src, census, found = lits(code)
    two = next(x for x in found if x["text"] == "2" and x["scope"] == "method")
    with pytest.raises(EditError, match="already"):
        plan_literal(src, census, two["span"], {"number": 2})
    with pytest.raises(EditError, match="isn't a string"):
        plan_literal(src, census, two["span"], {"string": "x"})
    with pytest.raises(EditError, match="not a name"):
        right = next(x for x in found if x["text"] == "RIGHT")
        plan_literal(src, census, right["span"], {"name": "os.system('x')"})
    with pytest.raises(EditError, match="isn't there"):
        plan_literal(src, census, [1, 0, 1, 4], {"number": 1})


def test_value_inside_a_helper_asks_first():
    code = "from manim import *\n\ndef get_dot():\n    return Dot().shift(2 * UP)\n"
    src, census, found = lits(code)
    two = next(x for x in found if x["text"] == "2")
    assert "every use" in plan_literal(src, census, two["span"], {"number": 3}).confirm


def test_round_trip_closes():
    code = scene("d = Dot().shift(UP * 1.4)")
    out, _ = edit(code, "1.4", {"number": 2})
    src, census, found = lits(out)
    two = next(x for x in found if x["text"] == "2.0")
    back = apply(out.encode(), plan_literal(src, census, two["span"], {"number": 1.4}).edits).decode()
    assert back == code


def test_non_ascii_columns():
    code = scene('t = Text("a² + b²", font_size=36)')
    src, census, found = lits(code)
    n = next(x for x in found if x["text"] == "36")
    out = apply(code.encode(), plan_literal(src, census, n["span"], {"number": 40}).edits).decode()
    assert 'Text("a² + b²", font_size=40)' in out


def test_several_parts_in_one_edit():
    from studio.server.code.literals import plan_literals
    code = scene('eq = MathTex("a^2", "+", "b^2")')
    src, census, found = lits(code)
    a2 = next(x for x in found if x["text"] == '"a^2"')
    b2 = next(x for x in found if x["text"] == '"b^2"')
    plus = next(x for x in found if x["text"] == '"+"')
    plan = plan_literals(src, census, [{"span": a2["span"], "value": {"string": "x^2"}},
                                       {"span": plus["span"], "value": {"string": "+"}},
                                       {"span": b2["span"], "value": {"string": "y^2"}}])
    out = apply(code.encode(), plan.edits).decode()
    assert 'MathTex("x^2", "+", "y^2")' in out
    with pytest.raises(EditError, match="already"):
        plan_literals(src, census, [{"span": plus["span"], "value": {"string": "+"}}])
