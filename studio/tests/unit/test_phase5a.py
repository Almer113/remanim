"""Phase 5a: dead at() anchors, and drag refusals that say what puts an object back."""

import ast

from studio.server.code.source import Source
from studio.server.code.splice import apply
from studio.server.code.timeline import dead_anchors
from studio.server.project import _why_stuck

HEAD = "from manim_kit import *\n\nclass S(TimedScene):\n    def construct(self):\n"


def scene(*lines):
    return HEAD + "".join("        " + ln + "\n" for ln in lines)


def at_span(code, needle):
    src = Source(code.encode())
    n = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and src.text(n) == needle)
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def waits(code, *needles):
    return {"events": [{"kind": "wait", "call": at_span(code, x)} for x in needles]}


def test_an_anchor_that_stopped_waiting_is_removed():
    old = scene("self.at(1.0)", "self.play(FadeIn(a), run_time=1)", "self.at(1.5)", "self.play(FadeIn(b))")
    new = scene("self.at(1.8)", "self.play(FadeIn(a), run_time=1)", "self.at(1.5)", "self.play(FadeIn(b))")
    edits, note = dead_anchors(Source(old.encode()), waits(old, "self.at(1.0)", "self.at(1.5)"),
                               Source(new.encode()), waits(new, "self.at(1.8)"), "S")
    out = apply(new.encode(), edits).decode()
    assert "self.at(1.5)" not in out and "self.at(1.8)" in out
    assert "removed self.at(1.5) (line 7)" in note


def test_an_anchor_that_never_waited_stays():
    # at(2.0) documents a landing time even when the scene is already there
    old = scene("self.at(1.0)", "self.at(2.0)")
    new = scene("self.at(1.2)", "self.at(2.0)")
    edits, _ = dead_anchors(Source(old.encode()), waits(old, "self.at(1.0)"),
                            Source(new.encode()), waits(new, "self.at(1.2)"), "S")
    assert edits == []


def test_nothing_removed_when_the_edit_added_an_anchor():
    old = scene("self.at(1.0)", "self.play(FadeIn(a))")
    new = scene("self.at(1.0)", "self.at(1.5)", "self.play(FadeIn(a))")
    edits, _ = dead_anchors(Source(old.encode()), waits(old, "self.at(1.0)"),
                            Source(new.encode()), waits(new, "self.at(1.5)"), "S")
    assert edits == []


def test_anchor_inside_a_say_block_keeps_the_block_valid():
    old = scene('with self.say("Hi"):', "    self.at(1.5)")
    new = scene("self.at(2.0)", 'with self.say("Hi"):', "    self.at(1.5)")
    # counts differ (an at() was added before the line): left alone
    assert dead_anchors(Source(old.encode()), waits(old, "self.at(1.5)"),
                        Source(new.encode()), waits(new, "self.at(2.0)"), "S")[0] == []
    old = scene("self.at(1.0)", 'with self.say("Hi"):', "    self.at(1.5)")
    new = scene("self.at(1.8)", 'with self.say("Hi"):', "    self.at(1.5)")
    edits, _ = dead_anchors(Source(old.encode()), waits(old, "self.at(1.0)", "self.at(1.5)"),
                            Source(new.encode()), waits(new, "self.at(1.8)"), "S")
    out = apply(new.encode(), edits).decode()
    ast.parse(out)
    assert 'with self.say("Hi"):\n            pass\n' in out


def test_why_stuck_names_the_updater_line():
    obj = {"updaters": 1, "updater_at": ["animations.py", 88]}
    assert "updater (line 88)" in _why_stuck(obj, None, "animations.py")
    assert "updater redraws" in _why_stuck({"updaters": 1, "updater_at": ["mobject.py", 3]}, None, "x.py")


def test_why_stuck_names_the_animation():
    got = {"placement": {"move": {"kind": "animation", "site": [21, 8, 21, 40], "method": "move_to"}}}
    assert "animation on line 21 carries it" in _why_stuck({}, got, "x.py")
    got = {"placement": {"move": {"kind": "animate", "site": [102, 8, 102, 60], "method": "shift"}}}
    assert "line 102 moves it afterwards with .animate.shift()" in _why_stuck({}, got, "x.py")
    assert _why_stuck({}, {"placement": {"move": {"kind": "static", "site": [1, 0, 1, 1]}}}, "x.py") is None


# -- at() times from a loop over a literal (clip share) -----------------------------
from studio.server.code.planner import plan_timing  # noqa: E402


def at_clip(code, occurrence, start):
    return {"kind": "wait", "call": at_span(code, "self.at(t)"), "call_name": "at", "start": start,
            "duration": 0.5, "occurrence": occurrence, "in_helper": False}


def test_at_time_from_a_zipped_literal():
    code = scene("for t, s in zip((5.5, 7.8, 9.8), topics):", "    self.at(t)", "    self.play(FadeIn(s))")
    plan = plan_timing(Source(code.encode()), at_clip(code, 1, 7.0), "duration", 1.0)
    out = apply(code.encode(), plan.edits).decode()
    assert "zip((5.5, 8.0, 9.8), topics)" in out and "pass 2 of the loop" in plan.note
    assert plan.confirm is None  # one pass only: nothing else changes


def test_at_time_from_a_tuple_of_tuples():
    code = scene('for t, mode in ((4.6, "happy"), (7.4, "sad")):', "    self.at(t)")
    plan = plan_timing(Source(code.encode()), at_clip(code, 0, 4.0), "duration", 0.8)
    assert "((4.8, \"happy\"), (7.4, \"sad\"))" in apply(code.encode(), plan.edits).decode()


def test_at_time_in_a_nested_loop_is_refused():
    import pytest
    from studio.server.code.splice import EditError
    code = scene("for i in range(2):", "    for t in (1.0, 2.0):", "        self.at(t)")
    with pytest.raises(EditError, match="computed"):
        plan_timing(Source(code.encode()), at_clip(code, 1, 1.5), "duration", 1.0)


def test_at_time_reassigned_in_the_loop_is_refused():
    import pytest
    from studio.server.code.splice import EditError
    code = scene("for t in (1.0, 2.0):", "    t += 0.5", "    self.at(t)")
    with pytest.raises(EditError, match="computed"):
        plan_timing(Source(code.encode()), at_clip(code, 0, 1.0), "duration", 1.0)


# -- at(a + 1.2): an anchor relative to a spoken line ------------------------------
def offset_clip(code, needle, start, duration):
    return {"kind": "wait", "call": at_span(code, needle), "call_name": "at", "start": start,
            "duration": duration, "occurrence": 0, "in_helper": False}


def test_at_offset_from_a_line_moves_only_the_offset():
    code = scene("a, c = self.line('Hi')", "self.at(a + 1.2)")
    # waits 2.0 -> 2.5 until a + 1.2 = 4.5 (start 2.5, a = 3.3): 2.6 s means a + 1.3
    plan = plan_timing(Source(code.encode()), offset_clip(code, "self.at(a + 1.2)", 2.5, 2.0), "duration", 2.1)
    assert "self.at(a + 1.3)" in apply(code.encode(), plan.edits).decode()


def test_at_offset_below_target_and_sign_flip():
    code = scene("self.at(self.TARGET - 0.6)")
    plan = plan_timing(Source(code.encode()), offset_clip(code, "self.at(self.TARGET - 0.6)", 1.0, 1.0), "duration", 1.1)
    assert "self.at(self.TARGET - 0.5)" in apply(code.encode(), plan.edits).decode()
    code = scene("self.at(c + 0.1)")
    plan = plan_timing(Source(code.encode()), offset_clip(code, "self.at(c + 0.1)", 1.0, 1.0), "duration", 0.7)
    assert "self.at(c - 0.2)" in apply(code.encode(), plan.edits).decode()


def test_at_offset_from_an_expression_is_still_refused():
    import pytest
    from studio.server.code.splice import EditError
    code = scene("for k in range(3):", "    self.at(0.3 + 3.2 * k)")
    with pytest.raises(EditError, match="computed"):
        plan_timing(Source(code.encode()), offset_clip(code, "self.at(0.3 + 3.2 * k)", 1.0, 1.0), "duration", 1.1)
