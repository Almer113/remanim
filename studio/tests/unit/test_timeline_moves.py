"""Moving clips and groups in the code layer (Phase 4 step 4-5), no Manim."""

import ast

import pytest

from studio.server.code.planner import plan_timing
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply
from studio.server.code.timeline import plan_anim_offset, plan_merge, plan_shift, plan_split

HEAD = "from manim_kit import *\n\nclass S(TimedScene):\n    TARGET = 6\n\n    def construct(self):\n"
SEQ = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n"


def scene(*lines, head=HEAD):
    return head + "".join("        " + ln + "\n" for ln in lines)


def span(code, needle, nth=0):
    tree = ast.parse(code)
    hits = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and ast.get_source_segment(code, n) == needle), key=lambda n: (n.lineno, n.col_offset))
    n = hits[nth]
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def ev(code, needle, start, dur, kind="play", n=1):
    s = span(code, needle)
    return {"kind": kind, "start": start, "duration": dur, "call": s, "chain": [s], "call_line": s[0],
            "anims": [{}] * n}


def clip(code, needle, n, play_index=0):
    return {"call": span(code, needle), "anims": [{}] * n, "play_index": play_index, "lock": None,
            "kind": "play"}


def run(code, plan):
    out = apply(code.encode(), plan.edits).decode()
    ast.parse(out)
    return out


# -- clip(): offsets inside a play -----------------------------------------------------
def test_offset_wraps_and_unwraps_byte_exact():
    play = "self.play(Create(a, run_time=1), Write(b, run_time=0.8))"
    code = scene(play)
    out = run(code, plan_anim_offset(Source(code.encode()), clip(code, play, 2), 1, 0.6, 15))
    assert "self.play(Create(a, run_time=1), clip(Write(b, run_time=0.8), start=0.6))" in out
    p2 = "self.play(Create(a, run_time=1), clip(Write(b, run_time=0.8), start=0.6))"
    more = run(out, plan_anim_offset(Source(out.encode()), clip(out, p2, 2), 1, 0.9, 15))
    assert "start=0.9" in more
    back = run(out, plan_anim_offset(Source(out.encode()), clip(out, p2, 2), 1, 0, 15))
    assert back == code


def test_offset_spreads_a_play_runtime():
    play = "self.play(FadeIn(t), b.animate.shift(UP), run_time=0.8)"
    code = scene(play)
    p = plan_anim_offset(Source(code.encode()), clip(code, play, 2), 1, 0.3, 15)
    out = run(code, p)
    assert "self.play(FadeIn(t, run_time=0.8), clip(b.animate.shift(UP), start=0.3, length=0.8))" in out
    assert "run_time=0.8)" not in out.split("clip(")[1]


def test_offset_refuses_negative_and_starred():
    play = "self.play(FadeIn(t))"
    code = scene(play)
    with pytest.raises(EditError, match="before its group"):
        plan_anim_offset(Source(code.encode()), clip(code, play, 1), 0, -0.5, 15)
    play = "self.play(*[FadeIn(m) for m in ms])"
    code = scene(play)
    with pytest.raises(EditError, match="one to one"):
        plan_anim_offset(Source(code.encode()), clip(code, play, 3), 0, 0.5, 15)


def test_offset_adds_the_kit_import():
    play = "self.play(FadeIn(t), FadeIn(u))"
    code = scene(play, head=SEQ)
    out = run(code, plan_anim_offset(Source(code.encode()), clip(code, play, 2), 1, 0.5, 15))
    assert "from manim_kit import *" in out


def test_trim_inside_clip_sets_length_and_spreads_play_runtime():
    play = "self.play(FadeIn(t), clip(Write(u), start=0.5))"
    code = scene(play)
    c = {"kind": "anim", "call": span(code, play), "anim_index": 1, "anims": [{}, {}], "start": 0, "duration": 1}
    assert "clip(Write(u), start=0.5, length=1.5)" in run(code, plan_timing(Source(code.encode()), c, "duration", 1.5))
    play = "self.play(FadeIn(t), FadeIn(u), run_time=0.8)"
    code = scene(play)
    c = {"kind": "anim", "call": span(code, play), "anim_index": 0, "anims": [{}, {}], "start": 0, "duration": 0.8}
    out = run(code, plan_timing(Source(code.encode()), c, "duration", 1.2))
    assert "self.play(FadeIn(t, run_time=1.2), FadeIn(u, run_time=0.8))" in out


# -- moving groups -----------------------------------------------------------------------
def timed_scene():
    code = scene("self.at(0.5)", "self.play(FadeIn(a), run_time=1)", "self.play(FadeIn(b), run_time=1)",
                 "self.at(4)", "self.play(FadeOut(a), run_time=1)")
    events = [ev(code, "self.at(0.5)", 0, 0.5, "wait"), ev(code, "self.play(FadeIn(a), run_time=1)", 0.5, 1),
              ev(code, "self.play(FadeIn(b), run_time=1)", 1.5, 1), ev(code, "self.at(4)", 2.5, 1.5, "wait"),
              ev(code, "self.play(FadeOut(a), run_time=1)", 4, 1)]
    return code, events


def test_shift_edits_the_at_and_ripples_later_ats_and_target():
    code, events = timed_scene()
    p = plan_shift(Source(code.encode()), "S", events, [], [0], [], 0.5, 15, True, True)
    out = run(code, p)
    assert "self.at(1)" in out and "self.at(4.5)" in out and "TARGET = 6.5" in out
    assert p.checks["starts"]["plays"] == {0: 1.0}
    back = plan_shift(Source(out.encode()), "S", events, [], [0], [], -0.5, 15, True, True)
    # events are stale here, but the literals round-trip
    assert run(out, back) == code


def test_shift_without_ripple_leaves_later_ats():
    code, events = timed_scene()
    out = run(code, plan_shift(Source(code.encode()), "S", events, [], [0], [], 0.5, 15, True, False))
    assert "self.at(1)" in out and "self.at(4)" in out and "TARGET = 6\n" in out


def test_shift_unanchored_play_inserts_at_and_refuses_earlier():
    code, events = timed_scene()
    out = run(code, plan_shift(Source(code.encode()), "S", events, [], [1], [], 0.5, 15, True, False))
    assert "        self.at(2)\n        self.play(FadeIn(b), run_time=1)" in out
    with pytest.raises(EditError, match="as soon as"):
        plan_shift(Source(code.encode()), "S", events, [], [1], [], -0.5, 15, True, False)


def test_shift_multi_select_carries_a_following_group():
    code, events = timed_scene()
    p = plan_shift(Source(code.encode()), "S", events, [], [0, 1], [], 0.3, 15, True, False)
    out = run(code, p)
    assert out.count("self.at(") == 2 and "self.at(0.8)" in out


def test_shift_earlier_than_the_code_before_is_refused():
    code, events = timed_scene()
    with pytest.raises(EditError, match="can't start before 2.50"):
        plan_shift(Source(code.encode()), "S", events, [], [2], [], -2.0, 15, True, False)


def test_shift_back_to_where_an_inserted_at_does_nothing_removes_it():
    code, events = timed_scene()
    out = run(code, plan_shift(Source(code.encode()), "S", events, [], [1], [], 0.5, 15, True, False))
    ev2 = [ev(out, "self.at(0.5)", 0, 0.5, "wait"), ev(out, "self.play(FadeIn(a), run_time=1)", 0.5, 1),
           ev(out, "self.at(2)", 1.5, 0.5, "wait"), ev(out, "self.play(FadeIn(b), run_time=1)", 2, 1),
           ev(out, "self.at(4)", 3, 1, "wait"), ev(out, "self.play(FadeOut(a), run_time=1)", 4, 1)]
    back = run(out, plan_shift(Source(out.encode()), "S", ev2, [], [1], [], -0.5, 15, True, False))
    assert back == code


def test_shift_sequential_edits_the_wait_before_and_after():
    code = scene("self.play(FadeIn(a))", "self.wait(1)", "self.play(FadeIn(b))", "self.wait(2)",
                 "self.play(FadeOut(a))", head=SEQ)
    events = [ev(code, "self.play(FadeIn(a))", 0, 1), ev(code, "self.wait(1)", 1, 1, "wait"),
              ev(code, "self.play(FadeIn(b))", 2, 1), ev(code, "self.wait(2)", 3, 2, "wait"),
              ev(code, "self.play(FadeOut(a))", 5, 1)]
    out = run(code, plan_shift(Source(code.encode()), "S", events, [], [1], [], 0.5, 15, False, False))
    assert "self.wait(1.5)" in out and "self.wait(1.5)" in out.split("FadeIn(b)")[1]
    rip = run(code, plan_shift(Source(code.encode()), "S", events, [], [1], [], 0.5, 15, False, True))
    assert "self.wait(1.5)" in rip and "self.wait(2)" in rip
    gone = run(code, plan_shift(Source(code.encode()), "S", events, [], [1], [], -1, 15, False, True))
    assert "self.wait(1)" not in gone
    with pytest.raises(EditError, match="only 1 s"):
        plan_shift(Source(code.encode()), "S", events, [], [1], [], -1.5, 15, False, True)


def test_shift_a_narration_line_with_a_play():
    code = scene("self.at(1)", 'with self.say("Hi"):', "    self.play(FadeIn(a), run_time=1)", "self.at(4)",
                 "self.wait(1)")
    events = [ev(code, "self.at(1)", 0, 1, "wait"), ev(code, "self.play(FadeIn(a), run_time=1)", 1, 1),
              ev(code, "self.at(4)", 2, 2, "wait")]
    s = span(code, 'self.say("Hi")')
    lines = [{"index": 0, "kind": "say", "call": s, "chain": [s], "start": 1, "requested": 1}]
    p = plan_shift(Source(code.encode()), "S", events, lines, [0], [0], 1.0, 15, True, True)
    out = run(code, p)
    assert "self.at(2)" in out and "self.at(5)" in out and out.count("self.at(") == 2
    assert p.checks["starts"] == {"plays": {0: 2.0}, "lines": {0: 2.0}}


# -- merge and split ------------------------------------------------------------------------
def test_merge_a_later_play_into_an_earlier_one_and_split_it_back():
    p1, p2 = "self.play(FadeIn(a), run_time=1)", "self.play(Write(b), run_time=0.8)"
    code = scene("self.at(0.5)", p1, "self.at(2)", p2)
    c1 = {**clip(code, p1, 1, 0), "start": 0.5, "anims": [{"offset": 0, "run_time": 1}]}
    c2 = {**clip(code, p2, 1, 1), "start": 2.0, "anims": [{"offset": 0, "run_time": 0.8}]}
    p = plan_merge(Source(code.encode()), "S", c2, None, c1, 0.6, 15)
    out = run(code, p)
    assert "self.play(FadeIn(a, run_time=1), clip(Write(b), start=0.6, length=0.8))" in out
    assert "self.at(2)" in out and "Write(b), run_time" not in out
    assert p.checks["merged"] == {"play": 0, "first": 1, "offsets": [0.6], "plays": -1}
    joined = "self.play(FadeIn(a, run_time=1), clip(Write(b), start=0.6, length=0.8))"
    cj = {**clip(out, joined, 2, 0), "start": 0.5,
          "anims": [{"offset": 0, "run_time": 1}, {"offset": 0.6, "run_time": 0.8}]}
    back = run(out, plan_split(Source(out.encode()), "S", cj, 1, 2.0, [], 15, True))
    assert "self.play(FadeIn(a, run_time=1))\n        self.at(2)\n        self.play(Write(b), run_time=0.8)\n" in back


def test_merge_refuses_code_in_between_and_other_kwargs():
    p1, p2 = "self.play(FadeIn(a))", "self.play(Write(b), rate_func=linear)"
    code = scene(p1, "self.add(c)", p2)
    c1, c2 = {**clip(code, p1, 1, 0), "start": 0}, {**clip(code, p2, 1, 1), "start": 1}
    with pytest.raises(EditError, match="other code between"):
        plan_merge(Source(code.encode()), "S", c2, None, c1, 0.5, 15)
    code = scene(p1, p2)
    c1, c2 = {**clip(code, p1, 1, 0), "start": 0}, {**clip(code, p2, 1, 1), "start": 1}
    with pytest.raises(EditError, match="rate_func"):
        plan_merge(Source(code.encode()), "S", c2, None, c1, 0.5, 15)


def test_merge_one_of_several_and_multi_line_layout():
    p1 = "self.play(\n            FadeIn(a),\n            FadeIn(b),\n        )"
    p2 = "self.play(Write(c), Write(d))"
    code = scene("self.play(", "    FadeIn(a),", "    FadeIn(b),", ")", p2)
    c1 = {**clip(code, p1, 2, 0), "start": 0}
    c2 = {**clip(code, p2, 2, 1), "start": 1}
    out = run(code, plan_merge(Source(code.encode()), "S", c2, 1, c1, 0.25, 15))
    assert "            FadeIn(b),\n            clip(Write(d), start=0.25),\n        )" in out
    assert "self.play(Write(c))" in out


def test_split_refuses_inside_the_group_and_single_clip():
    p = "self.play(FadeIn(a, run_time=2), FadeIn(b, run_time=1))"
    code = scene(p)
    c = {**clip(code, p, 2, 0), "start": 0, "anims": [{"offset": 0, "run_time": 2}, {"offset": 0, "run_time": 1}]}
    with pytest.raises(EditError, match="runs until 2.00"):
        plan_split(Source(code.encode()), "S", c, 1, 1.0, [], 15, True)
    p = "self.play(FadeIn(a))"
    code = scene(p)
    with pytest.raises(EditError, match="only one clip"):
        plan_split(Source(code.encode()), "S", {**clip(code, p, 1), "start": 0}, 0, 3, [], 15, True)


# -- reorder ---------------------------------------------------------------------------------
from studio.server.code.timeline import plan_reorder, plan_scene_order  # noqa: E402


def test_reorder_timed_swaps_statements_and_keeps_anchors():
    pa, pb = "self.play(FadeIn(a), run_time=1)", "self.play(Write(b), run_time=1)  # b"
    code = scene("self.at(0.5)", pa, "self.at(2)", pb)
    events = [ev(code, "self.at(0.5)", 0, 0.5, "wait"), ev(code, pa, 0.5, 1), ev(code, "self.at(2)", 1.5, 0.5, "wait"),
              ev(code, "self.play(Write(b), run_time=1)", 2, 1)]
    events[1]["anims"] = [{"class": "FadeIn"}]
    events[3]["anims"] = [{"class": "Write"}]
    p = plan_reorder(Source(code.encode()), "S", events, 1, 0, False, True)
    out = run(code, p)
    assert out == scene("self.at(0.5)", pb, "self.at(2)", pa)
    assert p.checks["order"] == [["Write"], ["FadeIn"]]


def test_reorder_sequential_moves_one_statement():
    pa, pb, pc = "self.play(FadeIn(a))", "self.play(FadeIn(b))", "self.play(FadeIn(c))"
    code = scene(pa, pb, pc, head=SEQ)
    events = [ev(code, pa, 0, 1), ev(code, pb, 1, 1), ev(code, pc, 2, 1)]
    for e, c in zip(events, "abc"):
        e["anims"] = [{"class": c}]
    out = run(code, plan_reorder(Source(code.encode()), "S", events, 2, 0, False, False))
    assert out == scene(pc, pa, pb, head=SEQ)
    p = plan_reorder(Source(code.encode()), "S", events, 0, 2, True, False)
    assert run(code, p) == scene(pb, pc, pa, head=SEQ) and p.checks["order"] == [["b"], ["c"], ["a"]]


def test_reorder_refuses_shared_names():
    code = scene("t = Text('x')", "self.play(Write(t))", "self.play(t.animate.shift(UP))", head=SEQ)
    events = [ev(code, "self.play(Write(t))", 0, 1), ev(code, "self.play(t.animate.shift(UP))", 1, 1)]
    with pytest.raises(EditError, match="both use t"):
        plan_reorder(Source(code.encode()), "S", events, 1, 0, False, False)


def test_scene_order_swaps_strings_and_the_docstring():
    code = ('"""Demo.\n\nRender order: A, B, C.\n"""\n\nclass A: pass\nclass B: pass\nclass C: pass\n\n'
            "SCENES = ['A', 'B',\n          'C']\n")
    out = run(code, plan_scene_order(Source(code.encode()), ["C", "A", "B"], ["A", "B", "C"]))
    assert "SCENES = ['C', 'A',\n          'B']" in out and "Render order: C, A, B." in out
    with pytest.raises(EditError, match="same scenes"):
        plan_scene_order(Source(code.encode()), ["A", "B"], ["A", "B", "C"])
    bare = "class A: pass\nclass B: pass\n"
    assert run(bare, plan_scene_order(Source(bare.encode()), ["B", "A"], ["A", "B"])).endswith('\nSCENES = ["B", "A"]\n')


def test_scene_order_follows_a_wrapped_docstring_list():
    code = ('"""Demo.\n\nRender order: Alpha, Beta,\nGamma.\n"""\n\nclass Alpha: pass\nclass Beta: pass\n'
            'class Gamma: pass\n\nSCENES = ["Alpha", "Beta", "Gamma"]\n')
    out = run(code, plan_scene_order(Source(code.encode()), ["Beta", "Alpha", "Gamma"], ["Alpha", "Beta", "Gamma"]))
    assert "Render order: Beta, Alpha,\nGamma." in out
    assert 'SCENES = ["Beta", "Alpha", "Gamma"]' in out
