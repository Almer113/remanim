"""Phase 5 step 8: switching a transform's kind."""

import ast

import pytest

from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply
from studio.server.code.transforms import pair, plan_kind

HEAD = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n"


def scene(*lines):
    return HEAD + "".join("        " + ln + "\n" for ln in lines)


def play_span(code, k=0):
    src = Source(code.encode())
    plays = [n for n in ast.walk(src.tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "play"]
    plays.sort(key=lambda n: n.lineno)
    n = plays[k]
    return src, [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def switch(code, kind, index=0):
    src, sp = play_span(code)
    return apply(code.encode(), plan_kind(src, sp, index, kind).edits).decode()


def test_switch_keeps_arguments():
    code = scene("a, b = Square(), Circle()", "self.play(Transform(a, b), run_time=2)", "self.play(FadeOut(b))")
    assert "self.play(ReplacementTransform(a, b), run_time=2)" in switch(code, "ReplacementTransform")
    src, sp = play_span(code)
    assert pair(src, sp, 0)["kind"] == "Transform"


def test_refused_when_later_code_uses_what_leaves_the_screen():
    code = scene("a, b = Square(), Circle()", "self.play(Transform(a, b))", "self.play(a.animate.shift(UP))")
    with pytest.raises(EditError, match="line 7 uses it"):
        switch(code, "ReplacementTransform")
    code = scene("a, b = Square(), Circle()", "self.play(ReplacementTransform(a, b))", "self.play(FadeOut(b))")
    with pytest.raises(EditError, match="b is no longer on screen"):
        switch(code, "Transform")


def test_a_name_bound_again_is_another_object():
    code = scene("a, b = Square(), Circle()", "self.play(Transform(a, b))", "a = Dot()", "self.add(a)")
    assert "ReplacementTransform(a, b)" in switch(code, "ReplacementTransform")


def test_from_copy_keeps_both():
    code = scene("a, b = Square(), Circle()", "self.play(Transform(a, b))", "self.play(a.animate.shift(UP))")
    assert "TransformFromCopy(a, b)" in switch(code, "TransformFromCopy")


def test_not_a_transform():
    code = scene("a = Square()", "self.play(FadeIn(a))")
    with pytest.raises(EditError, match="isn't a Transform"):
        switch(code, "Transform")


def _play_span(code):
    src = Source(code.encode())
    c = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "play")
    return [c.lineno, c.col_offset, c.end_lineno, c.end_col_offset]


def test_key_map_added_and_extended():
    from studio.server.code.transforms import plan_key_map
    code = 'self.play(TransformMatchingTex(a, b))\n'
    out = apply(code.encode(), plan_key_map(Source(code.encode()), _play_span(code), 0, "x", "y").edits).decode()
    assert out == 'self.play(TransformMatchingTex(a, b, key_map={"x": "y"}))\n'
    code = 'self.play(TransformMatchingTex(a, b, key_map={"x": "y"}))\n'
    out = apply(code.encode(), plan_key_map(Source(code.encode()), _play_span(code), 0, r"\pi", "z").edits).decode()
    assert out == 'self.play(TransformMatchingTex(a, b, key_map={"x": "y", r"\\pi": "z"}))\n'


def test_key_map_refusals():
    from studio.server.code.transforms import plan_key_map
    for code, why in (('self.play(TransformMatchingShapes(a, b))\n', "shape"),
                      ('self.play(Transform(a, b))\n', "only TransformMatchingTex"),
                      ('self.play(TransformMatchingTex(a, b, key_map=km))\n', "computed")):
        with pytest.raises(EditError, match=why):
            plan_key_map(Source(code.encode()), _play_span(code), 0, "x", "y")
