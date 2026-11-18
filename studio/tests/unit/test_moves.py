"""Move / scale / rotate planning (code/moves.py), no Manim: placements are
built by hand the way the engine reports them."""

import ast

import pytest

from studio.server.code.moves import (delta_expr, edit_vector, move_candidates, override_target,
                                      rotate_candidates, scale_candidates)
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply


def span(code: str, needle: str, nth: int = 0):
    """[line, col, end_line, end_col] of the call whose text is `needle`."""
    tree = ast.parse(code)
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.get_source_segment(code, n) == needle]
    hits.sort(key=lambda n: (n.lineno, n.col_offset))
    n = hits[nth]
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def mv(code, needle, method="call", kind="static", chain=None, func="construct", **kw):
    s = span(code, needle)
    return {"order": kw.pop("order", 1), "method": method, "kind": kind, "site": s, "func": func,
            "chain": chain or [s], **kw}


def obj(code, create, move=None, oid="Circle@1:0#0", **extra):
    c = mv(code, create, "create")
    c["order"] = -1
    p = {"create": c}
    if move:
        p["move"] = move
    p.update(extra)
    return {"id": oid, "site": c["site"], "placement": p}


def first(code, cands):
    assert cands, "no candidate"
    return apply(code.encode(), cands[0].edits).decode()


WRAP = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n{}\n"


def scene(*lines):
    return WRAP.format("\n".join("        " + ln for ln in lines))


# -- formatting -----------------------------------------------------------------------
def test_delta_expr():
    assert delta_expr(0.4, -0.25) == "0.4 * RIGHT + 0.25 * DOWN"
    assert delta_expr(-1, 0) == "LEFT"
    assert delta_expr(0, 2) == "2 * UP"
    assert delta_expr(0, 0) == "ORIGIN"


@pytest.mark.parametrize("before,d,after", [
    ("UP * 0.5", (0.4, -0.25), "UP * 0.25 + 0.4 * RIGHT"),
    ("0.5 * UP", (0, 0.25), "0.75 * UP"),
    ("2 * RIGHT + DOWN", (0.5, 0), "2.5 * RIGHT + DOWN"),
    ("RIGHT", (0.4, 0), "1.4 * RIGHT"),
    ("-UP", (0, -0.25), "-1.25 * UP"),
    ("UP / 2", (0, 0.25), "UP * 0.75"),
    ("ORIGIN", (1, 0), "RIGHT"),
    ("[1, 2, 0]", (0.5, -1), "[1.5, 1, 0]"),
    ("np.array([1.0, 2.0, 0])", (0.5, 0), "np.array([1.5, 2.0, 0])"),
    ("LEFT * 3 - 0.5 * UP", (0, 0.25), "LEFT * 3 - 0.25 * UP"),
    ("UP * 0.25 + 0.4 * RIGHT", (-0.4, 0.25), "UP * 0.5"),   # a term back to 0 is removed
    ("0.4 * RIGHT + UP", (-0.4, 0), "UP"),
])
def test_edit_vector(before, d, after):
    code = f"x = {before}\n"
    src = Source(code.encode())
    e = edit_vector(src, src.tree.body[0].value, *d)
    assert apply(code.encode(), e).decode() == f"x = {after}\n"


def test_edit_vector_refuses_computed():
    src = Source(b"x = r * UP\n")
    assert edit_vector(src, src.tree.body[0].value, 1, 0) is None


# -- moves --------------------------------------------------------------------------------
def test_literal_shift_numbers_and_back():
    code = scene("blob = Circle().to_corner(DL, buff=0.7).shift(UP * 0.5)", "self.add(blob)")
    m = mv(code, "Circle().to_corner(DL, buff=0.7).shift(UP * 0.5)", "shift")
    o = obj(code, "Circle()", m)
    out = first(code, move_candidates(Source(code.encode()), o, 0.4, -0.25))
    assert "shift(UP * 0.25 + 0.4 * RIGHT)" in out
    m2 = mv(out, "Circle().to_corner(DL, buff=0.7).shift(UP * 0.25 + 0.4 * RIGHT)", "shift")
    back = first(out, move_candidates(Source(out.encode()), obj(out, "Circle()", m2), -0.4, 0.25))
    assert back == code


def test_chain_shift_then_remove():
    code = scene("title = Text(\"hi\").to_edge(UP)", "self.add(title)")
    m = mv(code, 'Text("hi").to_edge(UP)', "to_edge")
    o = obj(code, 'Text("hi")', m)
    out = first(code, move_candidates(Source(code.encode()), o, 0.4, 0))
    assert 'title = Text("hi").to_edge(UP).shift(0.4 * RIGHT)' in out
    # the next drag sees to_edge as the last move; the chained shift merges, then vanishes
    m2 = mv(out, 'Text("hi").to_edge(UP)', "to_edge")
    back = first(out, move_candidates(Source(out.encode()), obj(out, 'Text("hi")', m2), -0.4, 0))
    assert back == code


def test_standalone_shift_statement_removed_at_zero():
    code = scene("c = Circle()", "c.shift(0.5 * LEFT)", "self.add(c)")
    m = mv(code, "c.shift(0.5 * LEFT)", "shift")
    out = first(code, move_candidates(Source(code.encode()), obj(code, "Circle()", m), 0.5, 0))
    assert "c.shift" not in out and out.count("\n") == code.count("\n") - 1


def test_helper_use_first_then_inside_with_confirm():
    code = ("from manim import *\n\ndef get_title():\n    return Text('t').to_edge(UP)\n\n"
            "class S(Scene):\n    def construct(self):\n        title = get_title()\n        self.add(title)\n")
    inner = span(code, "Text('t').to_edge(UP)")
    outer = span(code, "get_title()")
    m = {"order": 1, "method": "to_edge", "kind": "static", "site": inner, "func": "get_title",
         "chain": [outer, inner]}
    o = {"id": "Text@4:11#0", "site": span(code, "Text('t')"), "placement": {"create": m, "move": m}}
    cands = move_candidates(Source(code.encode()), o, 0, -0.25)
    assert "title = get_title().shift(0.25 * DOWN)" in first(code, cands)
    assert cands[0].confirm is None
    assert cands[-1].kind == "helper" and "every object" in cands[-1].confirm


def test_tuple_helper_names_the_part():
    code = ("from manim import *\n\ndef get_pair():\n    a = Circle()\n    b = Square()\n    return a, b\n\n"
            "class S(Scene):\n    def construct(self):\n        p, q = get_pair()\n        self.add(p, q)\n")
    inner = span(code, "Square()")
    outer = span(code, "get_pair()")
    m = {"order": -1, "method": "create", "kind": "static", "site": inner, "func": "get_pair",
         "chain": [outer, inner]}
    o = {"id": "Square@5:8#0", "site": inner, "placement": {"create": m}}
    cands = move_candidates(Source(code.encode()), o, 1, 0)
    notes = [c.note for c in cands]
    assert notes[0].startswith("new line p.shift()") and notes[1].startswith("new line q.shift()")
    assert "p, q = get_pair()\n        q.shift(RIGHT)\n" in apply(code.encode(), cands[1].edits).decode()


def test_laid_out_child_override_then_whole_group():
    code = scene("row = VGroup(Square(), Square()).arrange(RIGHT)", "row.to_edge(UP)", "self.add(row)")
    lay = span(code, "VGroup(Square(), Square()).arrange(RIGHT)")
    gsite = span(code, "VGroup(Square(), Square())")
    m = {"order": 2, "method": "arrange", "kind": "laid_out", "site": lay, "func": "construct",
         "chain": [lay], "path": [1], "group_site": gsite}
    gmove = mv(code, "row.to_edge(UP)", "to_edge", order=3)
    o = obj(code, "Square()", m, oid="Square@5:21#0",
            ancestors=[{"index": 1, "class": "VGroup", "site": gsite, "func": "construct", "chain": [gsite],
                        "move": gmove}])
    o["placement"]["create"]["site"] = span(code, "Square()", 1)
    cands = move_candidates(Source(code.encode()), o, 0, 0.5)
    out = first(code, cands)
    assert "row.to_edge(UP)\n        row[1].shift(0.5 * UP)\n" in out
    assert cands[1].kind == "group" and cands[1].confirm
    assert "row.to_edge(UP).shift(0.5 * UP)" in apply(code.encode(), cands[1].edits).decode()


def test_loop_object_override_first():
    code = scene("labels = VGroup()", "for i in range(3):", "    lab = Integer(i).move_to(RIGHT * i)",
                 "    labels.add(lab)", "self.add(labels)")
    lsite = span(code, "VGroup()")
    m = mv(code, "Integer(i).move_to(RIGHT * i)", "move_to")
    o = obj(code, "Integer(i)", m, oid="Integer@7:18#2",
            ancestors=[{"index": 2, "class": "VGroup", "site": lsite, "func": "construct", "chain": [lsite]}])
    cands = move_candidates(Source(code.encode()), o, 0, -0.5)
    assert cands[0].kind == "override"
    out = first(code, cands)
    assert "        labels.add(lab)\n        labels[2].shift(0.5 * DOWN)\n        self.add(labels)" in out
    assert cands[1].kind == "loop" and "every object the loop makes" in cands[1].confirm


def test_list_comprehension_item():
    code = scene("dots = [Dot(RIGHT * x) for x in (-1, 0, 1)]", "self.add(*dots)")
    o = obj(code, "Dot(RIGHT * x)", None, oid="Dot@5:16#1")
    t = override_target(Source(code.encode()), o)
    assert t is not None and t[0] == "dots[1]"
    out = first(code, move_candidates(Source(code.encode()), o, 0, 0.3))
    assert "dots = [Dot(RIGHT * x) for x in (-1, 0, 1)]\n        dots[1].shift(0.3 * UP)\n" in out


def test_animate_vector():
    code = scene("c = Circle()", "self.play(c.animate.shift(2 * RIGHT), run_time=1)")
    m = mv(code, "self.play(c.animate.shift(2 * RIGHT), run_time=1)", "shift", kind="animate")
    out = first(code, move_candidates(Source(code.encode()), obj(code, "Circle()", m), 0.4, -0.25))
    assert "c.animate.shift(2.4 * RIGHT + 0.25 * DOWN)" in out


def test_updater_refused():
    code = scene("c = Circle()", "c.add_updater(lambda m: m.move_to(ORIGIN))")
    m = mv(code, "m.move_to(ORIGIN)", "move_to", kind="updater")
    with pytest.raises(EditError, match="updater"):
        move_candidates(Source(code.encode()), obj(code, "Circle()", m), 1, 0)


def test_never_chains_on_self_calls():
    code = scene("c = Circle()", "self.add(c)")
    m = mv(code, "self.add(c)", "shift", kind="animation")
    cands = move_candidates(Source(code.encode()), obj(code, "Circle()", m), 1, 0)
    assert not any("self.add(c).shift" in apply(code.encode(), c.edits).decode() for c in cands)


# -- scale and rotate -----------------------------------------------------------------------
def test_scale_literal_multiplies_then_vanishes():
    code = scene("c = Circle().scale(0.8)", "self.add(c)")
    m = mv(code, "Circle().scale(0.8)", "scale")
    o = obj(code, "Circle()", mv(code, "Circle()", "create", order=0), scale=m)
    out = first(code, scale_candidates(Source(code.encode()), o, 1.2))
    assert "Circle().scale(0.96)" in out
    o2 = obj(code, "Circle()", mv(code, "Circle()", "create", order=0), scale=m)
    out2 = first(code, scale_candidates(Source(code.encode()), o2, 1.25))
    assert "c = Circle()\n" in out2  # 0.8 * 1.25 = 1: the scale() goes


def test_scale_chained_after_placement_with_edge():
    code = scene("t = Text('a').next_to(ORIGIN, UP)", "self.add(t)")
    m = mv(code, "Text('a').next_to(ORIGIN, UP)", "next_to")
    out = first(code, scale_candidates(Source(code.encode()), obj(code, "Text('a')", m), 1.5, "DL"))
    assert "next_to(ORIGIN, UP).scale(1.5, about_edge=DL)" in out


def test_rotate_chain_and_edit_and_back():
    code = scene("s = Square()", "self.add(s)")
    o = obj(code, "Square()")
    out = first(code, rotate_candidates(Source(code.encode()), o, 15))
    assert "s = Square().rotate(15 * DEGREES)" in out
    m = mv(out, "Square().rotate(15 * DEGREES)", "rotate")
    o2 = obj(out, "Square()", None, rotate=m)
    assert "Square().rotate(45 * DEGREES)" in first(out, rotate_candidates(Source(out.encode()), o2, 30))
    assert first(out, rotate_candidates(Source(out.encode()), obj(out, "Square()", None, rotate=m), -15)) == code


def test_rotate_pi_literal_gets_degrees_term_and_loses_it():
    code = scene("s = Square().rotate(PI/2)", "self.add(s)")
    m = mv(code, "Square().rotate(PI/2)", "rotate")
    out = first(code, rotate_candidates(Source(code.encode()), obj(code, "Square()", None, rotate=m), 15))
    assert "rotate(PI/2 + 15 * DEGREES)" in out
    m2 = mv(out, "Square().rotate(PI/2 + 15 * DEGREES)", "rotate")
    back = first(out, rotate_candidates(Source(out.encode()), obj(out, "Square()", None, rotate=m2), -15))
    assert back == code


@pytest.mark.parametrize("before,back", [
    ("LEFT * 3", "LEFT * 3"),
    ("2 * RIGHT + 0.5 * UP", "2 * RIGHT + 0.5 * UP"),
    ("0.5 * UP", "0.5 * UP"),
    # whole numbers written with a point can't be told from integers on the way
    # back (the in-between literal is 0.75): they come back as integers
    ("UP * 1.0", "UP"),
    ("[2., -1.0, 0]", "[2, -1, 0]"),
    # a unit comes back as the bare name, the way people write it
    ("UP", "UP"),
    ("RIGHT + UP", "RIGHT + UP"),
    ("-UP", "-UP"),
    ("1 * UP", "UP"),
    # a division is rewritten as a product on the way out and stays one
    ("RIGHT / 2 + UP", "RIGHT * 0.5 + UP"),
])
def test_vector_drag_and_back(before, back):
    code = f"x = {before}\n"
    src = Source(code.encode())
    mid = apply(code.encode(), edit_vector(src, src.tree.body[0].value, 0.4, -0.25))
    src2 = Source(mid)
    assert apply(mid, edit_vector(src2, src2.tree.body[0].value, -0.4, 0.25)).decode() == f"x = {back}\n"


def test_property_override_for_one_item():
    from studio.server.code.planner import plan_property_override
    code = scene("dots = [Dot(RIGHT * x) for x in (-1, 0, 1)]", "self.add(*dots)")
    o = obj(code, "Dot(RIGHT * x)", None, oid="Dot@5:16#2")
    src = Source(code.encode())
    p = plan_property_override(src, o, "color", {"name": "RED"})
    out = apply(code.encode(), p.edits).decode()
    assert "dots = [Dot(RIGHT * x) for x in (-1, 0, 1)]\n        dots[2].set_color(RED)\n" in out
    p2 = plan_property_override(src, o, "fill_opacity", {"number": 0.5})
    assert "dots[2].set_fill(opacity=0.5)" in apply(code.encode(), p2.edits).decode()
    p3 = plan_property_override(src, o, "z_index", {"number": 2})
    assert "dots[2].set(z_index=2)" in apply(code.encode(), p3.edits).decode()
    assert plan_property_override(src, o, "color", {"default": True}) is None


def test_shift_chained_inside_an_animate_builder():
    code = scene("u = Circle()", "self.play(u.animate.scale(0.3).next_to(ORIGIN, DOWN), run_time=1)")
    m = mv(code, "self.play(u.animate.scale(0.3).next_to(ORIGIN, DOWN), run_time=1)", "next_to", kind="animate")
    out = first(code, move_candidates(Source(code.encode()), obj(code, "Circle()", m), 0.4, -0.25))
    assert "u.animate.scale(0.3).next_to(ORIGIN, DOWN).shift(0.4 * RIGHT + 0.25 * DOWN)" in out
    m2 = mv(out, "self.play(u.animate.scale(0.3).next_to(ORIGIN, DOWN).shift(0.4 * RIGHT + 0.25 * DOWN), "
                 "run_time=1)", "next_to", kind="animate")
    back = first(out, move_candidates(Source(out.encode()), obj(out, "Circle()", m2), -0.4, 0.25))
    assert back == code


def test_calibrated_drag_back_leaves_no_remainder():
    # a parent scaled by 1.4: the way out is 0.4 / 1.4, the way back a measured ratio
    code = "x = a.shift(UP)\n"
    src = Source(code.encode())
    mid = apply(code.encode(), edit_vector(src, src.tree.body[0].value.args[0], 0.2857, -0.1786))
    src2 = Source(mid)
    back = apply(mid, edit_vector(src2, src2.tree.body[0].value.args[0], -0.2854, 0.1789)).decode()
    assert back == code


def test_shift_goes_after_a_later_placement_in_the_chain():
    from studio.server.code.moves import plan_shift_on
    code = scene("eq = Square()", "tri = Circle().next_to(eq, UP, buff=0.6)")
    src = Source(code.encode())
    edits, note = plan_shift_on(src, mv(code, "Circle()", "create"), 0.4, -0.25)
    out = apply(code.encode(), edits).decode()
    assert "tri = Circle().next_to(eq, UP, buff=0.6).shift(0.4 * RIGHT + 0.25 * DOWN)" in out
    src2 = Source(out.encode())
    edits2, _ = plan_shift_on(src2, mv(out, "Circle()", "create"), -0.4, 0.25)
    assert apply(out.encode(), edits2).decode() == code


def test_new_shift_line_is_merged_on_the_way_back():
    code = WRAP.format("        a, b = make()\n        self.add(a, b)")
    make = span(code, "make()")
    m = mv(code, "self.add(a, b)", "shift", chain=[make, span(code, "self.add(a, b)")], func="make")
    o = obj(code, "make()", m)
    out = first(code, move_candidates(Source(code.encode()), o, 0.4, -0.25))
    assert "a, b = make()\n        a.shift(0.4 * RIGHT + 0.25 * DOWN)\n" in out
    o2 = obj(out, "make()", mv(out, "self.add(a, b)", "shift", chain=[span(out, "make()"),
                                                                       span(out, "self.add(a, b)")], func="make"))
    assert first(out, move_candidates(Source(out.encode()), o2, -0.4, 0.25)) == code
