"""Code layer: spans, formatting, keyword edits, timing/property plans.
No Manim needed."""

import pytest

from studio.server.code.planner import plan_property, plan_timing
from studio.server.code.source import Source, Span
from studio.server.code.splice import EditError, apply, fmt, inverse, set_keyword


def src(text: str, crlf=False) -> Source:
    data = text.replace("\n", "\r\n") if crlf else text
    return Source(data.encode("utf-8"))


def call_at(s: Source, line: int, name: str):
    import ast
    for n in ast.walk(s.tree):
        if isinstance(n, ast.Call) and n.lineno == line and Source.call_name(n) == name:
            return n
    raise AssertionError(name)


# -- formatting ------------------------------------------------------------------
@pytest.mark.parametrize("v, like, out", [
    (0.25, "0.5", "0.25"), (1.0, "0.5", "1.0"), (2.0, "2", "2"), (2.5, "2", "2.5"),
    (0.5, ".25", ".5"), (3.0, "2.", "3."), (1 / 3, None, "0.3333"), (-0.0, None, "0"),
    (1.23456789, "1.0", "1.2346"),
])
def test_fmt(v, like, out):
    assert fmt(v, like) == out


# -- keyword edits ----------------------------------------------------------------
CASES = [
    'self.play(FadeIn(a))\n',
    'self.play(FadeIn(a), run_time=2)\n',
    'self.play()\n',
    'self.play(\n    FadeIn(a),\n    Write(b),\n)\n',
    'self.play(\n    FadeIn(a),\n    Write(b)\n)\n',
    'self.play(FadeIn(a),\n          Write(b))\n',
]


@pytest.mark.parametrize("text", CASES)
@pytest.mark.parametrize("crlf", [False, True])
def test_add_then_remove_keyword_round_trips(text, crlf):
    s = src(text, crlf)
    call = call_at(s, 1, "play")
    if Source.keyword(call, "rate_func"):
        pytest.skip()
    added = apply(s.data, [set_keyword(s, call, "rate_func", "linear")])
    s2 = Source(added)
    assert s2.ok, added
    call2 = call_at(s2, 1, "play")
    assert s2.text(Source.keyword(call2, "rate_func").value) == "linear"
    removed = apply(added, [set_keyword(s2, call2, "rate_func", None)])
    assert removed == s.data


def test_inverse_restores_bytes():
    s = src('self.play(FadeIn(a), run_time=2)\nself.wait(0.5)\n')
    call = call_at(s, 1, "play")
    edits = [set_keyword(s, call, "run_time", "3.25")]
    new = apply(s.data, edits)
    assert apply(new, inverse(s.data, edits)) == s.data


# -- timing plans ---------------------------------------------------------------
SCENE = '''class A(Scene):
    def construct(self):
        self.play(FadeIn(a), run_time=1.5)
        self.play(FadeIn(b))
        self.wait(0.5)
        self.wait()
        self.at(4)
        self.play(FadeIn(c), b.animate.shift(UP))
        self.play(FadeIn(d, run_time=2), FadeOut(e))
        self.play(FadeIn(f), run_time=rt)
'''


def clip(line, name, kind, **k):
    s = Source(SCENE.encode())
    n = call_at(s, line, name)
    return dict(kind=kind, call=Span.of(n).as_list(), call_name=name, **k)


def run(c, field, value):
    s = Source(SCENE.encode())
    p = plan_timing(s, c, field, value)
    new = apply(s.data, p.edits)
    assert Source(new).ok
    return new.decode().splitlines()


def test_play_runtime_literal():
    assert run(clip(3, "play", "play"), "duration", 2)[2].endswith("run_time=2.0)")


def test_play_runtime_added():
    assert run(clip(4, "play", "play"), "duration", 0.8)[3].endswith("self.play(FadeIn(b), run_time=0.8)")


def test_wait_literal_and_bare():
    assert run(clip(5, "wait", "wait"), "duration", 1.25)[4].endswith("self.wait(1.25)")
    assert run(clip(6, "wait", "wait"), "duration", 2)[5].endswith("self.wait(2)")


def test_at_moves_anchor():
    c = clip(7, "at", "wait", start=3.0)
    assert run(c, "duration", 1.5)[6].endswith("self.at(4.5)")


def test_anim_runtime_call_and_builder():
    lines = run(clip(8, "play", "anim", anim_index=0), "duration", 0.7)
    assert "FadeIn(c, run_time=0.7)" in lines[7]
    lines = run(clip(8, "play", "anim", anim_index=1), "duration", 1.2)
    assert "b.animate(run_time=1.2).shift(UP)" in lines[7]


def test_refusals():
    s = Source(SCENE.encode())
    with pytest.raises(EditError, match="computed"):
        plan_timing(s, clip(10, "play", "play"), "duration", 2)
    with pytest.raises(EditError, match="stretch"):
        plan_timing(s, clip(9, "play", "play", anim_runtimes=[True, False]), "duration", 2)
    with pytest.raises(EditError, match="more than 0"):
        plan_timing(s, clip(5, "wait", "wait"), "duration", 0)
    with pytest.raises(EditError, match="helper"):
        plan_timing(s, clip(3, "play", "play", in_helper=True, func="fade_all"), "duration", 2)


def test_rate_func_set_and_default():
    lines = run(clip(3, "play", "play", default_rate_func="smooth"), "rate_func", "linear")
    assert lines[2].endswith("run_time=1.5, rate_func=linear)")


# -- property plans ---------------------------------------------------------------
PROPS = '''class A(Scene):
    def construct(self):
        c = Circle(radius=1, color=BLUE)
        t = Text("Hi", font_size=36)
        s = Square(2)
        m = MathTex(r"a^2")
'''


def obj(line, cls, params=()):
    s = Source(PROPS.encode())
    n = call_at(s, line, cls)
    return dict(site=Span.of(n).as_list(), **{"class": cls}, params=list(params))


def prop(o, name, value):
    s = Source(PROPS.encode())
    p = plan_property(s, o, name, value)
    new = apply(s.data, p.edits)
    assert Source(new).ok
    return new.decode().splitlines()


def test_property_edits():
    assert "Circle(radius=1.5, color=BLUE)" in prop(obj(3, "Circle"), "radius", {"number": 1.5})[2]
    assert "Circle(radius=1, color=ACCENT)" in prop(obj(3, "Circle"), "color", {"name": "ACCENT"})[2]
    assert "Circle(radius=1, color=BLUE, stroke_width=6)" in \
        prop(obj(3, "Circle"), "stroke_width", {"number": 6})[2]
    assert "Circle(color=BLUE)" in prop(obj(3, "Circle"), "radius", {"default": True})[2]
    assert 'Text("Say \\"hi\\"", font_size=36)' in \
        prop(obj(4, "Text", ["text"]), "text", {"string": 'Say "hi"'})[3]
    assert "Square(3)" in prop(obj(5, "Square", ["side_length"]), "side_length", {"number": 3})[4]
    assert 'MathTex(r"b^2")' in prop(obj(6, "MathTex", ["tex_strings"]), "tex_strings", {"string": "b^2"})[5]


def test_text_positional_string():
    o = obj(4, "Text", ["text"])
    assert 'Text("Bye", font_size=36)' in prop(o, "text", {"string": "Bye"})[3]


def test_rate_func_outside_star_import_is_qualified():
    # `from manim import *` has no bare ease_out_back; rate_functions.<name> it is
    lines = run(clip(3, "play", "play", default_rate_func="smooth"), "rate_func", "ease_out_back")
    assert lines[2].endswith("rate_func=rate_functions.ease_out_back)")
    lines = run(clip(3, "play", "play", default_rate_func="smooth"), "rate_func", "there_and_back")
    assert lines[2].endswith("rate_func=there_and_back)")


def test_long_nested_keyword_moves_the_rest_to_its_own_line():
    import ast
    code = ("class Q(Scene):\n    def construct(self):\n"
            "        self.play(FadeIn(title), FadeIn(blob, shift=UP * 0.2), run_time=0.8)\n")
    s = Source(code.encode())
    call = next(n for n in ast.walk(s.tree) if isinstance(n, ast.Call) and s.text(n) == "FadeIn(title)")
    e = set_keyword(s, call, "rate_func", "rate_functions.ease_out_back")
    out = apply(s.data, [e]).decode()
    assert out.splitlines()[2:] == [
        "        self.play(FadeIn(title,",
        "                         rate_func=rate_functions.ease_out_back),",
        "                  FadeIn(blob, shift=UP * 0.2), run_time=0.8)"]
    assert apply(apply(s.data, [e]), inverse(s.data, [e])) == s.data


def test_write_waits_for_a_reader_to_let_go(tmp_path):
    """Review after Phase 6: on Windows the replace failed while the engine
    had the file open for reading, so an undo was refused (and the corpus
    run left edits on disk). It now waits a little and tries again."""
    import threading
    import time

    from studio.server.code.splice import write_atomic
    p = tmp_path / "scene.py"
    p.write_bytes(b"x = 1\n")
    f = open(p, "rb")  # no delete sharing on Windows: os.replace fails while open
    threading.Thread(target=lambda: (time.sleep(0.15), f.close()), daemon=True).start()
    write_atomic(p, b"x = 2\n")
    assert p.read_bytes() == b"x = 2\n"
    assert not (tmp_path / "scene.py.studio-tmp").exists()
