"""Phase 5 step 7: a curve's formula, checked before it is written."""

import ast

import pytest

from studio.server.code.graphs import describe_curve, plan_curve
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

API = {"PI", "TAU", "UP", "Axes", "MathTex", "np"}

CODE = """from manim import *
import numpy as np

K = 0.5


class G(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3, 1], y_range=[0, 5, 1])
        a = 2
        curve = axes.plot(lambda x: K * x**2, x_range=[-2, 2], color=BLUE)
        wave = axes.plot_parametric_curve(lambda t: np.array([t, np.sin(t), 0]), t_range=[0, 3])
        self.add(axes, curve, wave)
"""


def site_of(code, attr):
    src = Source(code.encode())
    call = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == attr)
    return src, {"site": [call.lineno, call.col_offset, call.end_lineno, call.end_col_offset]}


def edit(attr, text, code=CODE):
    src, obj = site_of(code, attr)
    return apply(code.encode(), plan_curve(src, obj, text, API).edits).decode()


def test_describe():
    src, obj = site_of(CODE, "plot")
    d = describe_curve(src, obj["site"])
    assert d["params"] == ["x"] and d["expr"] == "K * x**2"


def test_edit_uses_params_constants_locals_and_numpy():
    assert "lambda x: a * np.sin(x) + K" in edit("plot", "a * np.sin(x) + K")
    assert "lambda x: abs(x) * PI" in edit("plot", "abs(x) * PI")


def test_a_tuple_or_conditional_is_wrapped():
    assert "lambda x: (x if x > 0 else 0)" in edit("plot", "x if x > 0 else 0")


def test_unknown_names_and_code_are_refused():
    for bad, msg in [("y * 2", "y isn't defined"), ("__import__('os')", "isn't defined"),
                     ("x.__class__", "isn't something"), ("[x for x in range(3)]", "listcomp"),
                     ("x +", "not a formula"), ("open('f')", "open isn't defined"),
                     ("(lambda: 1)()", "lambda")]:
        with pytest.raises(EditError, match=msg):
            edit("plot", bad)


def test_same_formula_refused():
    with pytest.raises(EditError, match="already"):
        edit("plot", "K * x**2")
