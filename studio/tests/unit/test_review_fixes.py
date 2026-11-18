"""Regression tests for the post-Phase-2 review (studio/docs/review_phase2.md).
Code layer and server guards only: no Manim needed."""

import ast

import pytest

from studio.server.code.planner import plan_property, plan_timing
from studio.server.code.source import Source, Span
from studio.server.code.splice import EditError, apply, set_keyword


def src(text: str) -> Source:
    return Source(text.encode("utf-8"))


def calls(s: Source, name: str):
    return [n for n in ast.walk(s.tree) if isinstance(n, ast.Call) and Source.call_name(n) == name]


def clip_for(s: Source, call: ast.Call, kind: str, name: str, **kw) -> dict:
    return {"kind": kind, "call": Span.of(call).as_list(), "call_name": name, "start": 0.0,
            "duration": 1.0, "anim_runtimes": [], **kw}


# -- code written into the file is only ever a value ------------------------------
@pytest.mark.parametrize("value", ["__import__('os').system('calc') or smooth", "smooth; x", "a b",
                                   "lambda t: t", "import", "smooth)"])
def test_rate_func_must_be_a_name(value):
    s = src("self.play(FadeIn(x))\n")
    with pytest.raises(EditError):
        plan_timing(s, clip_for(s, calls(s, "play")[0], "play", "play"), "rate_func", value)


def test_rate_func_dotted_name_ok():
    s = src("self.play(FadeIn(x))\n")
    plan = plan_timing(s, clip_for(s, calls(s, "play")[0], "play", "play", default_rate_func="smooth"),
                       "rate_func", "rate_functions.ease_in_sine")
    assert b"rate_func=rate_functions.ease_in_sine" in apply(s.data, plan.edits)


@pytest.mark.parametrize("prop", ["x=1, y", "color=RED) or (", "1a", "class"])
def test_property_name_must_be_identifier(prop):
    s = src("c = Circle(radius=1)\n")
    obj = {"site": Span.of(calls(s, "Circle")[0]).as_list(), "class": "Circle", "params": []}
    with pytest.raises(EditError):
        plan_property(s, obj, prop, {"number": 2})


@pytest.mark.parametrize("value", [{"name": "os.system('x')"}, {"name": "1abc"},
                                   {"number": float("inf")}, {"number": "nan"}])
def test_property_values_checked(value):
    s = src("c = Circle(radius=1)\n")
    obj = {"site": Span.of(calls(s, "Circle")[0]).as_list(), "class": "Circle", "params": []}
    with pytest.raises(EditError):
        plan_property(s, obj, "radius", value)


# -- splices ------------------------------------------------------------------------
def test_keyword_after_trailing_comma_on_close_line():
    s = Source(b"f(\r\n    a,\r\n    b,)\r\n")
    out = apply(s.data, [set_keyword(s, calls(s, "f")[0], "k", "2")])
    assert out == b"f(\r\n    a,\r\n    b, k=2,)\r\n"
    assert Source(out).ok


def test_bom_line_one_spans():
    s = Source(b"\xef\xbb\xbfx = f(1)\r\ny = 2\r\n")
    call = calls(s, "f")[0]
    assert s.text(call) == "f(1)"
    out = apply(s.data, [set_keyword(s, call, "k", "2")])
    assert out == b"\xef\xbb\xbfx = f(1, k=2)\r\ny = 2\r\n"


def test_wait_with_only_keywords():
    s = src("self.wait(frozen_frame=False)\n")
    plan = plan_timing(s, clip_for(s, calls(s, "wait")[0], "wait", "wait"), "duration", 2)
    out = apply(s.data, plan.edits)
    assert out == b"self.wait(2, frozen_frame=False)\n"


def test_tiny_duration_refused_after_rounding():
    s = src("self.wait(1)\n")
    with pytest.raises(EditError):
        plan_timing(s, clip_for(s, calls(s, "wait")[0], "wait", "wait"), "duration", 0.00004)


def test_at_time_is_rounded():
    s = src("self.at(3)\n")
    c = clip_for(s, calls(s, "at")[0], "wait", "at", start=1.0666667)
    plan = plan_timing(s, c, "duration", 1.9)
    assert apply(s.data, plan.edits) == b"self.at(2.97)\n"


# -- the right call ------------------------------------------------------------------
def test_run_time_goes_into_animate_call():
    s = src("self.play(x.animate(rate_func=linear).shift(RIGHT), y.animate.shift(UP))\n")
    c = clip_for(s, calls(s, "play")[0], "anim", "play", anim_index=0)
    out = apply(s.data, plan_timing(s, c, "duration", 3).edits)
    assert out == b"self.play(x.animate(rate_func=linear, run_time=3).shift(RIGHT), y.animate.shift(UP))\n"


def test_existing_animate_run_time_is_changed():
    s = src("self.play(x.animate(run_time=1).shift(RIGHT))\n")
    out = apply(s.data, plan_timing(s, clip_for(s, calls(s, "play")[0], "play", "play"), "duration", 3).edits)
    assert out == b"self.play(x.animate(run_time=3).shift(RIGHT))\n"


# -- side effects are confirmed -------------------------------------------------------
def test_edit_inside_loop_needs_confirm():
    s = src("for i in range(3):\n    self.wait(1)\n")
    plan = plan_timing(s, clip_for(s, calls(s, "wait")[0], "wait", "wait"), "duration", 2)
    assert plan.confirm and "loop" in plan.confirm


def test_edit_outside_loop_no_confirm():
    s = src("def construct(self):\n    for i in range(3):\n        pass\n    self.wait(1)\n")
    plan = plan_timing(s, clip_for(s, calls(s, "wait")[0], "wait", "wait"), "duration", 2)
    assert plan.confirm is None


def test_computed_property_needs_confirm():
    s = src("c = Circle(radius=r * 2)\n")
    obj = {"site": Span.of(calls(s, "Circle")[0]).as_list(), "class": "Circle", "params": []}
    plan = plan_property(s, obj, "radius", {"number": 1.5})
    assert plan.confirm and "computed" in plan.confirm


# -- strings ---------------------------------------------------------------------------
@pytest.mark.parametrize("old, new", [('"""a"""', 'say "hi"'), ("'''a'''", "it's"), ("r'a'", "two\nlines"),
                                      ('"a"', 'back\\slash "q"'), ("'a'", "x\ry")])
def test_string_edits_parse_and_round_trip(old, new):
    s = src(f"t = Text({old})\n")
    obj = {"site": Span.of(calls(s, "Text")[0]).as_list(), "class": "Text", "params": ["text"]}
    out = apply(s.data, plan_property(s, obj, "text", {"string": new}).edits)
    tree = ast.parse(out)
    assert tree.body[0].value.args[0].value == new


# -- server guards -------------------------------------------------------------------
def test_normalise_rejects_tool_folders_and_outside():
    from aiohttp import web
    from studio.server.app import normalise
    assert normalise("./order_matters.py") == "order_matters.py"
    for bad in ["../x.py", "studio/server/app.py", ".venv/Lib/site-packages/manim/__init__.py",
                "nope.py", "README.md"]:
        with pytest.raises(web.HTTPBadRequest):
            normalise(bad)


@pytest.mark.parametrize("origin, ok", [("http://localhost:8770", True), ("http://127.0.0.1:8770", True),
                                        ("http://localhost:9999", False), ("http://evil.example:8770", False),
                                        ("null", False), ("file://", False)])
def test_same_server_origin(origin, ok):
    from studio.server.app import _same_server
    assert _same_server(origin, "127.0.0.1:8770") == ok


@pytest.mark.parametrize("host, ok", [("127.0.0.1:8770", True), ("localhost:8770", True), ("[::1]:8770", True),
                                      ("evil.example:8770", False), ("127.0.0.1.evil.example", False)])
def test_host_names(host, ok):
    from studio.server.app import LOCAL_HOSTS, _host_name
    assert (_host_name(host) in LOCAL_HOSTS) == ok
