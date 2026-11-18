"""Library drops, presets, duplicate, group, delete (code/inserts.py), no Manim.
Trace events are written by hand the way the engine reports them."""

import ast

import pytest

from studio.server.code.inserts import (new_file_text, plan_delete, plan_delete_clip, plan_duplicate,
                                        plan_group, plan_insert, plan_preset)
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

API = {"FadeOut", "FadeIn", "Create", "Write", "Circle", "Square", "UP", "DOWN", "LEFT", "RIGHT", "BLUE", "VGroup",
       "Text", "Indicate", "ORIGIN"}


def span(code, needle, nth=0):
    tree = ast.parse(code)
    hits = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and ast.get_source_segment(code, n) == needle), key=lambda n: (n.lineno, n.col_offset))
    n = hits[nth]
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def ev(code, needle, start, dur, kind="play"):
    s = span(code, needle)
    return {"kind": kind, "start": start, "duration": dur, "call": s, "chain": [s]}


def run(code, plan):
    out = apply(code.encode(), plan.edits).decode()
    ast.parse(out)
    return out


BLANK = new_file_text("Demo")


def test_new_file_template_parses_and_reads_like_code():
    ast.parse(BLANK)
    assert "class Demo(TimedScene):" in BLANK and "TARGET = 5.0" in BLANK
    with pytest.raises(EditError):
        new_file_text("not a name")


def test_drop_on_blank_scene():
    p = plan_insert(Source(BLANK.encode()), "Demo", [], 15, True, "Circle", -1.6, 0.8, 1.0)
    out = run(BLANK, p)
    assert out.endswith("        apply_background()\n"
                        "        circle = Circle(radius=1, color=ACCENT).move_to(1.6 * LEFT + 0.8 * UP)\n"
                        "        self.at(1)\n"
                        "        self.play(Create(circle), run_time=0.8)\n")
    # a second drop at a later time goes after the first, with its own name
    ev1 = ev(out, "self.at(1)", 0, 1, "wait")
    ev2 = ev(out, "self.play(Create(circle), run_time=0.8)", 1, 0.8)
    p2 = plan_insert(Source(out.encode()), "Demo", [ev1, ev2], 15, True, "Text", 0, 2.5, 2.5, region="title")
    out2 = run(out, p2)
    assert out2.endswith('        text = place(Text("Text", font_size=BODY_SIZE, color=FG), "title")\n'
                         "        self.at(2.5)\n"
                         "        self.play(Write(text), run_time=1)\n")


def test_drop_before_a_later_clip_in_a_timed_scene():
    code = BLANK + ("        sq = Square()\n        self.at(3)\n        self.play(Create(sq), run_time=1)\n")
    evs = [ev(code, "self.at(3)", 0, 3, "wait"), ev(code, "self.play(Create(sq), run_time=1)", 3, 1)]
    out = run(code, plan_insert(Source(code.encode()), "Demo", evs, 15, True, "Dot", 0, 0, 1.0))
    assert "        sq = Square()\n        dot = Dot(color=ACCENT)\n        self.at(1)\n" \
           "        self.play(FadeIn(dot), run_time=0.6)\n        self.at(3)\n" in out


SEQ = ("from manim import *\n\nclass S(Scene):\n    def construct(self):\n"
       "        c = Circle()\n        self.play(Create(c), run_time=1)\n        self.wait(3)\n"
       "        self.play(FadeOut(c), run_time=1)\n")


def test_sequential_drop_splits_the_wait():
    evs = [ev(SEQ, "self.play(Create(c), run_time=1)", 0, 1), ev(SEQ, "self.wait(3)", 1, 3, "wait"),
           ev(SEQ, "self.play(FadeOut(c), run_time=1)", 4, 1)]
    p = plan_insert(Source(SEQ.encode()), "S", evs, 15, False, "Square", 2, 0, 2.0)
    out = run(SEQ, p)
    assert ("        self.wait(1)\n        square = Square(side_length=2, color=BLUE).move_to(2 * RIGHT)\n"
            "        self.play(Create(square), run_time=0.8)\n        self.wait(1.2)\n"
            "        self.play(FadeOut(c)") in out
    assert "later" not in p.note  # the FadeOut keeps its time


def test_sequential_drop_after_the_end_adds_a_wait():
    evs = [ev(SEQ, "self.play(Create(c), run_time=1)", 0, 1), ev(SEQ, "self.wait(3)", 1, 3, "wait"),
           ev(SEQ, "self.play(FadeOut(c), run_time=1)", 4, 1)]
    out = run(SEQ, plan_insert(Source(SEQ.encode()), "S", evs, 15, False, "Dot", 0, 0, 6.0))
    assert out.endswith("FadeOut(c), run_time=1)\n        dot = Dot(color=YELLOW)\n        self.wait(1)\n"
                        "        self.play(FadeIn(dot), run_time=0.6)\n")


def test_drop_during_a_play_starts_after_it():
    evs = [ev(SEQ, "self.play(Create(c), run_time=1)", 0, 1)]
    p = plan_insert(Source(SEQ.encode()), "S", evs, 15, False, "Dot", 0, 0, 0.5)
    assert "starts at 1.00 s" in p.note


def test_preset_on_object_and_kit_import():
    code = SEQ
    obj = {"site": span(code, "Circle()"), "id": "Circle@5:12#0"}
    evs = [ev(code, "self.play(Create(c), run_time=1)", 0, 1), ev(code, "self.wait(3)", 1, 3, "wait")]
    out = run(code, plan_preset(Source(code.encode()), "S", evs, 15, False, obj, "Indicate", 1.0))
    assert "Create(c), run_time=1)\n        self.play(Indicate(c), run_time=1)\n        self.wait(2)\n" in out
    out2 = run(code, plan_insert(Source(code.encode()), "S", [], 15, False, "Blob", 0, 0, 0))
    assert "from manim import *\nfrom manim_kit import *\n" in out2


def test_names_never_clash():
    code = SEQ.replace("c = Circle()", "circle = Circle()").replace("(c)", "(circle)")
    p = plan_insert(Source(code.encode()), "S", [], 15, False, "Circle", 0, 0, 0)
    assert "circle_2 = Circle(" in run(code, p)


def test_duplicate():
    obj = {"site": span(SEQ, "Circle()"), "id": "Circle@5:12#0"}
    evs = [ev(SEQ, "self.play(Create(c), run_time=1)", 0, 1), ev(SEQ, "self.wait(3)", 1, 3, "wait")]
    out = run(SEQ, plan_duplicate(Source(SEQ.encode()), "S", evs, 15, False, obj, 1.0))
    assert ("Create(c), run_time=1)\n        c_2 = c.copy().shift(0.5 * RIGHT + 0.5 * DOWN)\n"
            "        self.play(FadeIn(c_2), run_time=0.6)\n        self.wait(2.4)\n") in out


def test_group_after_the_later_creation():
    code = ("from manim import *\n\nclass S(Scene):\n    def construct(self):\n        a = Circle()\n"
            "        self.add(a)\n        b = Square()\n        self.add(b)\n")
    objs = [{"site": span(code, "Circle()")}, {"site": span(code, "Square()")}]
    out = run(code, plan_group(Source(code.encode()), "S", objs))
    assert "        b = Square()\n        group = VGroup(a, b)\n        self.add(b)\n" in out
    with pytest.raises(EditError):
        plan_group(Source(code.encode()), "S", objs[:1])


def test_delete_object_with_its_uses():
    code = BLANK + ("        circle = Circle().move_to(LEFT)\n        sq = Square()\n        self.at(1)\n"
                    "        self.play(Create(circle), run_time=0.8)\n        self.at(2)\n"
                    "        self.play(Create(sq), circle.animate.shift(UP), run_time=1)\n"
                    "        circle.set_color(BLUE)\n")
    obj = {"site": span(code, "Circle()"), "id": "x"}
    out = run(code, plan_delete(Source(code.encode()), "Demo", obj, API))
    assert "circle" not in out
    assert "        sq = Square()\n        self.at(2)\n        self.play(Create(sq), run_time=1)\n" in out


def test_delete_refuses_other_readers():
    code = SEQ + "        d = Dot().next_to(c, UP)\n"
    obj = {"site": span(code, "Circle()"), "id": "x"}
    with pytest.raises(EditError, match="line 9"):
        plan_delete(Source(code.encode()), "S", obj, API)


def test_insert_then_delete_restores_bytes():
    p = plan_insert(Source(BLANK.encode()), "Demo", [], 15, True, "Square", 1, 0, 1.0)
    out = run(BLANK, p)
    obj = {"site": span(out, "Square(side_length=2, color=ACCENT)"), "id": "x"}
    assert run(out, plan_delete(Source(out.encode()), "Demo", obj, API | {"ACCENT"})) == BLANK


def test_delete_clip_and_animation():
    code = SEQ.replace("FadeOut(c), run_time=1)", "FadeOut(c), Create(Square()), run_time=1)")
    clip = {"call": span(code, "self.play(FadeOut(c), Create(Square()), run_time=1)"), "kind": "play"}
    out = run(code, plan_delete_clip(Source(code.encode()), "S", clip, 1))
    assert "self.play(FadeOut(c), run_time=1)" in out
    out2 = run(code, plan_delete_clip(Source(code.encode()), "S", clip, None))
    assert "FadeOut" not in out2 and out2.endswith("self.wait(3)\n")
    wclip = {"call": span(code, "self.wait(3)"), "kind": "wait"}
    assert "wait" not in run(code, plan_delete_clip(Source(code.encode()), "S", wclip, None))
