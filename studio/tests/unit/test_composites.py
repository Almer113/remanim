"""Phase 5 step 12: composite presets read like hand-written code."""

import ast

import pytest

from studio.server.code.census import classify
from studio.server.code.inserts import COMPOSITES, ON_OBJECT, plan_composite
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

API = {"Scene", "Axes", "VGroup", "Create", "Write", "NumberLine", "ValueTracker", "always_redraw", "Dot",
       "Arrow", "MathTex", "GrowArrow", "TransformMatchingTex", "Text", "FadeIn", "Brace", "GrowFromCenter",
       "SurroundingRectangle", "FadeOut", "Square", "ORIGIN", "UP", "DOWN", "RIGHT", "LEFT", "UR",
       "BLUE", "WHITE", "YELLOW", "GREY", "GREEN", "ThreeDScene", "ThreeDAxes", "Surface", "np", "DEGREES", "place", "FG", "MUTED", "ACCENT", "ACCENT_2", "TITLE_SIZE", "BODY_SIZE"}

BLANK = "from manim import *\n\n\nclass S(Scene):\n    def construct(self):\n        sq = Square()\n        self.add(sq)\n"
SQ = {"site": [6, 13, 6, 21], "class": "Square"}


@pytest.mark.parametrize("which", COMPOSITES)
def test_each_preset_parses_and_is_editable(which):
    code = BLANK.replace("S(Scene)", "S(ThreeDScene)") if which == "surface" else BLANK
    src = Source(code.encode())
    plan = plan_composite(src, "S", [], 15, False, which, 1.0, -0.5, 0.0, SQ if which in ON_OBJECT else None)
    out = apply(code.encode(), plan.edits).decode()
    tree = ast.parse(out)
    census = classify(tree, API)
    new = [ln for ln in range(8, len(out.splitlines()) + 1) if ln in census.lines]
    assert new, out
    worst = max(census.lines[ln] for ln in new)
    # the number line's always_redraw is the one fixed template the studio writes at tier 3
    assert worst <= (3 if which == "number_line" else 2), (which, out)
    assert plan.checks["name"] in out


def test_names_never_clash():
    code = BLANK.replace("sq = Square()", "axes = Square()").replace("self.add(sq)", "self.add(axes)")
    src = Source(code.encode())
    out = apply(code.encode(), plan_composite(src, "S", [], 15, False, "graph", 0, 0, 0.0).edits).decode()
    assert "axes_2 = Axes(" in out and "axes_2.plot(" in out


def test_object_presets_need_an_object():
    with pytest.raises(EditError, match="on an object"):
        plan_composite(Source(BLANK.encode()), "S", [], 15, False, "brace", 0, 0, 0.0)


def test_tex_is_written_raw():
    src = Source(BLANK.encode())
    out = apply(BLANK.encode(), plan_composite(src, "S", [], 15, False, "graph", 0, 0, 0.0).edits).decode()
    assert r'r"\frac{x^2}{2}"' in out


def test_surface_needs_3d_and_tilts_only_an_untilted_camera():
    with pytest.raises(EditError, match="ThreeDScene"):
        plan_composite(Source(BLANK.encode()), "S", [], 15, False, "surface", 0, 0, 0.0)
    code = BLANK.replace("S(Scene)", "S(ThreeDScene)")
    out = apply(code.encode(), plan_composite(Source(code.encode()), "S", [], 15, False, "surface", 0, 0, 0.0).edits).decode()
    assert "set_camera_orientation(phi=65 * DEGREES" in out
    code = code.replace("sq = Square()", "self.set_camera_orientation(phi=70 * DEGREES)\n        sq = Square()")
    out = apply(code.encode(), plan_composite(Source(code.encode()), "S", [], 15, False, "surface", 0, 0, 0.0).edits).decode()
    assert out.count("set_camera_orientation") == 1
