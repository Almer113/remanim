"""Regression tests for the review after Phase 3 (docs/review_phase3.md), no Manim."""

import ast

import pytest

from studio.server.code.inserts import (plan_delete, plan_delete_clip, plan_duplicate, plan_group,
                                        plan_insert)
from studio.server.code.moves import edit_vector, move_candidates, override_target, scale_candidates
from studio.server.code.planner import plan_property_override
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

WRAP = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n{}\n"
API = {"FadeOut", "FadeIn", "Create", "Write", "Circle", "Square", "Dot", "Text", "Transform", "UP", "RIGHT",
       "VGroup", "rotation", "scene"}


def scene(*lines):
    return WRAP.format("\n".join("        " + ln for ln in lines))


def span(code, needle, nth=0):
    tree = ast.parse(code)
    hits = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and ast.get_source_segment(code, n) == needle), key=lambda n: (n.lineno, n.col_offset))
    n = hits[nth]
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def mv(code, needle, method="call", kind="static"):
    s = span(code, needle)
    return {"order": 1, "method": method, "kind": kind, "site": s, "func": "construct", "chain": [s]}


def obj(code, create, move=None, oid="Dot@1:0#0", **extra):
    c = mv(code, create, "create")
    p = {"create": c, **extra}
    if move:
        p["move"] = move
    return {"id": oid, "site": c["site"], "placement": p}


def ev(code, needle, start, dur, kind="play"):
    s = span(code, needle)
    return {"kind": kind, "start": start, "duration": dur, "call": s, "chain": [s]}


def run(code, edits):
    out = apply(code.encode(), edits).decode()
    ast.parse(out)
    return out


def vec(text, dx, dy):
    src = Source(f"x = {text}\n".encode())
    expr = src.tree.body[0].value
    e = edit_vector(src, expr, dx, dy)
    return apply(src.data, e).decode()[4:-1]


# -- code layer ------------------------------------------------------------------------------
def test_client_ancestor_index_must_be_a_plain_int():
    code = scene("row = VGroup(*[Dot() for _ in range(3)]).arrange(RIGHT)", "self.add(row)")
    grp = span(code, "VGroup(*[Dot() for _ in range(3)])")
    for bad in ["0]; __import__('os').system('calc'); row[0", -1, 1.5, True, None]:
        o = obj(code, "Dot()", ancestors=[{"index": bad, "site": grp}])
        assert override_target(Source(code.encode()), o) is None, bad
        for c in move_candidates(Source(code.encode()), o, 0.5, 0):
            assert "__import__" not in str([e.text for e in c.edits])
        assert plan_property_override(Source(code.encode()), o, "color", {"name": "RED"}) is None
    good = obj(code, "Dot()", ancestors=[{"index": 1, "site": grp}])
    assert override_target(Source(code.encode()), good)[0] == "row[1]"


@pytest.mark.parametrize("before, d, after", [
    ("RIGHT + UP", (-1, -1), "ORIGIN"),
    ("0.5 * RIGHT + 0.5 * UP", (-0.5, -0.5), "ORIGIN"),
    ("2 * RIGHT + UP", (-2, 0), "UP"),
    ("UP", (2, 0), "2 * RIGHT + UP"),        # x first: the way back of the line above
    ("-UP", (2, 0), "-UP + 2 * RIGHT"),
])
def test_vector_to_origin_and_term_order(before, d, after):
    assert vec(before, *d) == after


def test_move_to_origin_round_trip_restores_bytes():
    code = scene("x = Dot().move_to(RIGHT + UP)", "self.add(x)")
    o = obj(code, "Dot()", mv(code, "Dot().move_to(RIGHT + UP)", "move_to"))
    out = run(code, move_candidates(Source(code.encode()), o, -1, -1)[0].edits)
    assert "x = Dot().move_to(ORIGIN)" in out
    o2 = obj(out, "Dot()", mv(out, "Dot().move_to(ORIGIN)", "move_to"))
    assert run(out, move_candidates(Source(out.encode()), o2, 1, 1)[0].edits) == code


@pytest.mark.parametrize("k", [3, 1.5, 1.2, 0.7, 2.5])
def test_scale_drag_and_back_restores_bytes(k):
    code = scene("x = Square().scale(2)", "self.add(x)")
    o = obj(code, "Square()", oid="Square@1:0#0")
    o["placement"]["scale"] = mv(code, "Square().scale(2)", "scale")
    out = run(code, scale_candidates(Source(code.encode()), o, round(k, 4))[0].edits)
    s = out.split(".scale(")[1].split(")")[0]
    o2 = obj(out, "Square()", oid="Square@1:0#0")
    o2["placement"]["scale"] = mv(out, f"Square().scale({s})", "scale")
    back = run(out, scale_candidates(Source(out.encode()), o2, round(1 / k, 4))[0].edits)
    assert back == code, back


def test_chained_scale_dragged_back_is_removed():
    code = scene("x = Square()", "self.add(x)")
    o = obj(code, "Square()", oid="Square@1:0#0")
    out = run(code, scale_candidates(Source(code.encode()), o, 3)[0].edits)
    assert "Square().scale(3)" in out
    o2 = obj(out, "Square()", oid="Square@1:0#0")
    o2["placement"]["scale"] = mv(out, "Square().scale(3)", "scale")
    assert run(out, scale_candidates(Source(out.encode()), o2, 0.3333)[0].edits) == code


def test_delete_with_non_ascii_text_on_the_line_keeps_other_code():
    code = WRAP.format('        a = 1\n        t = Text("Привет мир, 日本"); f()\n        self.add(t)')
    o = {"id": "Text@1:0#0", "site": span(code, 'Text("Привет мир, 日本")')}
    with pytest.raises(EditError):   # it shares its line with f(): refused, not wiped
        plan_delete(Source(code.encode()), "S", o, API)


def test_delete_keeps_trailing_comment_lines_removable():
    code = scene("c = Circle()", "self.add(c)  # show it", "self.wait(1)")
    o = {"id": "Circle@1:0#0", "site": span(code, "Circle()")}
    out = run(code, plan_delete(Source(code.encode()), "S", o, API).edits)
    assert "Circle" not in out and "show it" not in out and "self.wait(1)" in out


def test_remove_argument_with_non_ascii_before_it():
    code = scene('c = Circle()', 'self.play(Write(Text("ü")),', '          FadeIn(c))')
    o = {"id": "Circle@1:0#0", "site": span(code, "Circle()")}
    out = run(code, plan_delete(Source(code.encode()), "S", o, API).edits)
    assert 'self.play(Write(Text("ü")))\n' in out
    code = scene("c = Circle()", "self.play(", '    Write(Text("éééééééééé")),', "    FadeIn(c),", ")")
    o = {"id": "Circle@1:0#0", "site": span(code, "Circle()")}
    out = run(code, plan_delete(Source(code.encode()), "S", o, API).edits)
    assert out.endswith('        self.play(\n            Write(Text("éééééééééé")),\n        )\n')


def test_delete_clip_in_one_line_with_is_refused():
    code = scene("c = Circle()", "with self.voiceover(text='hi'): self.play(FadeIn(c))")
    clip = {"call": span(code, "self.play(FadeIn(c))")}
    with pytest.raises(EditError):
        plan_delete_clip(Source(code.encode()), "S", clip, None)


def test_insert_into_one_line_construct_is_refused():
    code = "from manim import *\n\nclass S(Scene):\n    def construct(self): pass\n"
    with pytest.raises(EditError):
        plan_insert(Source(code.encode()), "S", [], 15, False, "Circle", 0, 0, 0)


def test_timed_drop_inside_a_play_writes_no_dead_at():
    code = WRAP.replace("(Scene)", "(TimedScene)").format(
        "        sq = Square()\n        self.play(Create(sq), run_time=4)")
    events = [ev(code, "self.play(Create(sq), run_time=4)", 0, 4)]
    p = plan_insert(Source(code.encode()), "S", events, 15, True, "Dot", 1, 1, 2.0)
    out = run(code, p.edits)
    assert "self.at(" not in out and p.checks["start"] == 4.0
    p2 = plan_duplicate(Source(code.encode()), "S", events, 15, True,
                        {"id": "Square@1:0#0", "site": span(code, "Square()")}, 2.0)
    assert "self.at(" not in run(code, p2.edits) and p2.checks["start"] == 4.0


def test_wait_used_up_is_never_wait_0():
    for line in ["self.wait(1)  # beat", "self.wait(1); self.add(c)"]:
        code = scene("c = Circle()", "self.add(c)", line)
        events = [ev(code, "self.wait(1)", 0, 1, "wait")]
        p = plan_insert(Source(code.encode()), "S", events, 15, False, "Text", 0, 0, 0.0)
        out = run(code, p.edits)
        assert "wait(0)" not in out, out
    code = scene("self.wait(1)")
    p = plan_insert(Source(code.encode()), "S", [ev(code, "self.wait(1)", 0, 1, "wait")], 15, False,
                    "Text", 0, 0, 0.0)
    assert "wait(0)" not in run(code, p.edits)


def test_no_trailing_newline():
    code = scene("c = Circle()", "self.play(Create(c), run_time=1)").rstrip("\n")
    events = [ev(code, "self.play(Create(c), run_time=1)", 0, 1)]
    out = run(code, plan_insert(Source(code.encode()), "S", events, 15, False, "Dot", 0, 0, 1.0).edits)
    assert "run_time=1)\n" in out
    code2 = scene("c = Circle()", "d = Dot()").rstrip("\n")
    objs = [{"id": "Circle@1:0#0", "site": span(code2, "Circle()")}, {"id": "Dot@1:0#0", "site": span(code2, "Dot()")}]
    assert run(code2, plan_group(Source(code2.encode()), "S", objs).edits).endswith(
        "d = Dot()\n        group = VGroup(c, d)\n")


def test_group_uses_the_binding_of_the_selected_object():
    code = scene("a = Circle()", "b = Dot()", "self.play(FadeOut(a))", "a = Square()", "self.add(a, b)")
    objs = [{"id": "Square@1:0#0", "site": span(code, "Square()")}, {"id": "Dot@1:0#0", "site": span(code, "Dot()")}]
    out = run(code, plan_group(Source(code.encode()), "S", objs).edits)
    assert "a = Square()\n        group = VGroup(a, b)" in out
    # the Circle, whose name is reused before the group could be made: refused
    objs[0] = {"id": "Circle@1:0#0", "site": span(code, "Circle()")}
    code2 = scene("a = Circle()", "b = Dot()", "a = Square()", "c = Dot()", "self.add(a, b, c)")
    objs2 = [{"id": "Circle@1:0#0", "site": span(code2, "Circle()")},
             {"id": "Dot@1:0#1", "site": span(code2, "Dot()", 1)}]
    with pytest.raises(EditError):
        plan_group(Source(code2.encode()), "S", objs2)


def test_delete_treats_the_files_own_names_as_its_own():
    code = scene("c = Circle()", "rotation = Square()", "self.add(c)", "self.play(Transform(c, rotation))",
                 "self.add(rotation)")
    o = {"id": "Circle@1:0#0", "site": span(code, "Circle()")}
    with pytest.raises(EditError) as e:   # Transform(c, rotation) also uses `rotation`: ask
        plan_delete(Source(code.encode()), "S", o, API)
    assert "line" in str(e.value)


def test_new_file_scene_name_never_shadows_a_library_class():
    import asyncio
    from studio.server.app import ROOT, handle
    path = ROOT / "circle.py"
    if path.exists():
        pytest.skip("a circle.py exists")
    try:
        r = asyncio.run(handle({"type": "file.new", "name": "circle.py"}))
        assert r["scene"] == "CircleScene"
    finally:
        path.unlink(missing_ok=True)
