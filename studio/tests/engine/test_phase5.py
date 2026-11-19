"""Phase 5 through a real worker: in-place text edits with a TeX error,
the glyph map, and part colour, on small scenes in tests/tmp. Undone back
to the original bytes.

LaTeX runs here (shared media/Tex_studio): never run while the studio
server or a corpus run is busy.
"""

from studio.server.project import Document
from studio.tests.engine.test_engine import TMP, _quiet, run

SCENE = '''from manim import *


class Parts(Scene):
    def construct(self):
        eq = MathTex("a^2 + b^2 = c^2")
        eq.shift(UP)
        word = Text("to be or not to be", font_size=36)
        word.next_to(eq, DOWN)
        self.add(eq, word)
        self.wait(1)
'''


def _obj(doc, r, cls):
    o = next(o for o in r["objects"] if o["class"] == cls and not o.get("virtual"))
    return o


async def _objects(doc, f=5):
    r = await doc.frame("Parts", f, ids=True)
    assert "error" not in r, r
    return r


def test_glyph_map_and_part_colour_then_undo():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_parts.py"
        path.write_text(SCENE, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await _objects(doc)
            eq = _obj(doc, r, "MathTex")
            assert eq["texts"][0]["editable"] and eq["texts"][0]["value"] == "a^2 + b^2 = c^2"

            g = (await doc.glyphs("Parts", 5, eq["id"]))["glyphs"]
            assert g and g["kind"] == "tex" and len(g["map"]) == 8 == len(g["boxes"])
            own = [g["parts"][p][a:b] for p, a, b in g["map"]]
            assert sorted(own) == sorted(["a", "2", "+", "b", "2", "=", "c", "2"])

            # "+" occurs once and nothing indexes eq: isolated by its TeX
            plus = own.index("+")
            r = await doc.edit({"rev": doc.rev, "type": "edit.part_colour", "scene": "Parts", "object": eq,
                                "f": 5, "glyphs": [plus], "value": {"name": "YELLOW"}})
            assert r["type"] == "edit.done", r
            assert 'tex_to_color_map={"+": YELLOW}' in path.read_text(encoding="utf-8")

            # the "2" of b^2 repeats: an index override, checked glyph by glyph
            r = await _objects(doc)
            eq = _obj(doc, r, "MathTex")
            g = (await doc.glyphs("Parts", 5, eq["id"]))["glyphs"]
            own = [g["parts"][p][a:b] for p, a, b in g["map"]]
            two = next(i for i, (p, a, b) in enumerate(g["map"]) if own[i] == "2" and "b" in g["parts"][p])
            r = await doc.edit({"rev": doc.rev, "type": "edit.part_colour", "scene": "Parts", "object": eq,
                                "f": 5, "glyphs": [two], "value": {"name": "RED"}})
            assert r["type"] == "edit.done", r
            assert ".set_color(RED)" in path.read_text(encoding="utf-8")

            # a Text word that occurs once
            r = await _objects(doc)
            word = _obj(doc, r, "Text")
            g = (await doc.glyphs("Parts", 5, word["id"]))["glyphs"]
            assert g and g["kind"] == "text"
            orr = [i for i, (_, a, _) in enumerate(g["map"]) if a in (6, 7)]
            r = await doc.edit({"rev": doc.rev, "type": "edit.part_colour", "scene": "Parts", "object": word,
                                "f": 5, "glyphs": orr, "value": {"name": "GREEN"}})
            assert r["type"] == "edit.done", r
            assert 't2c={"or": GREEN}' in path.read_text(encoding="utf-8")

            for _ in range(3):
                assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_tex_error_is_refused_with_latex_message():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_texerr.py"
        path.write_text(SCENE, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await _objects(doc)
            eq = _obj(doc, r, "MathTex")
            span = eq["texts"][0]["span"]
            r = await doc.edit({"rev": doc.rev, "type": "edit.literal", "scene": "Parts",
                                "changes": [{"span": span, "value": {"string": r"a^2 + \badcommand"}}]})
            assert r["type"] == "edit.refused", r
            assert "LaTeX" in r["reason"] and "badcommand" in r["reason"], r["reason"]
            assert path.read_bytes() == original

            r = await doc.edit({"rev": doc.rev, "type": "edit.literal", "scene": "Parts",
                                "changes": [{"span": span, "value": {"string": r"x^2 + \pi"}}]})
            assert r["type"] == "edit.done", r
            assert 'MathTex(r"x^2 + \\pi")' in path.read_text(encoding="utf-8") or \
                'MathTex("x^2 + \\\\pi")' in path.read_text(encoding="utf-8")
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


CURVE = '''from manim import *
import numpy as np


class Curve(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3, 1], y_range=[-2, 5, 1])
        graph = axes.plot(lambda x: 0.5 * x**2, x_range=[-2, 2])
        self.add(axes, graph)
        self.wait(1)
'''


def test_curve_formula_edit_and_a_formula_that_fails():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_curve.py"
        path.write_text(CURVE, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.frame("Curve", 5, ids=True)
            g = next(o for o in r["objects"] if o.get("curve"))
            assert g["curve"] == {**g["curve"], "params": ["x"], "expr": "0.5 * x**2"}
            r = await doc.edit({"rev": doc.rev, "type": "edit.curve", "scene": "Curve", "object": g,
                                "expr": "np.sin(2 * x) + 1"})
            assert r["type"] == "edit.done", r
            assert "lambda x: np.sin(2 * x) + 1" in path.read_text(encoding="utf-8")
            # parses and names are known, but fails when Manim runs it: refused, file unchanged
            before = path.read_bytes()
            r = await doc.frame("Curve", 5, ids=True)
            g = next(o for o in r["objects"] if o.get("curve"))
            r = await doc.edit({"rev": doc.rev, "type": "edit.curve", "scene": "Curve", "object": g,
                                "expr": "np.log(x - 10) + int('a')"})
            assert r["type"] == "edit.refused", r
            assert path.read_bytes() == before
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_axes_range_and_transform_kind():
    code = '''from manim import *


class Pair(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3, 1], y_range=[-2, 5, 1], x_length=6)
        a, b = Square(), Circle()
        self.add(axes, a)
        self.play(Transform(a, b), run_time=1)
        self.play(FadeOut(a))
'''
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_pair.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.frame("Pair", 0, ids=True)
            ax = next(o for o in r["objects"] if o["class"] == "Axes")
            xr = next(x for x in ax["ranges"] if x["kw"] == "x_range")
            assert [p["label"] for p in xr["parts"]] == ["min", "max", "step"]
            r = await doc.edit({"rev": doc.rev, "type": "edit.literal", "scene": "Pair",
                                "span": xr["parts"][1]["span"], "value": {"number": 4}})
            assert r["type"] == "edit.done", r
            assert "x_range=[-3, 4, 1]" in path.read_text(encoding="utf-8")

            clip = next(c for c in doc.model()["scenes"][0]["clips"] if c.get("transforms"))
            assert clip["transforms"][0]["kind"] == "Transform"
            # FadeOut(a) afterwards: a must stay on screen
            r = await doc.edit({"rev": doc.rev, "type": "edit.transform_kind", "scene": "Pair",
                                "clip": clip["index"], "arg": 0, "kind": "ReplacementTransform"})
            assert r["type"] == "edit.refused" and "line 10 uses it" in r["reason"], r
            r = await doc.edit({"rev": doc.rev, "type": "edit.transform_kind", "scene": "Pair",
                                "clip": clip["index"], "arg": 0, "kind": "TransformFromCopy"})
            # a keeps its own shape now, so FadeOut(a) on line 10 fades something else: ask first
            assert r["type"] == "edit.preview" and "line 10 uses it" in r["why"], r
            r = await doc.confirm(r["token"])
            assert r["type"] == "edit.done", r
            assert "TransformFromCopy(a, b)" in path.read_text(encoding="utf-8")
            for _ in range(2):
                assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_every_composite_preset_builds_and_undoes():
    from studio.server.code.inserts import COMPOSITES, ON_OBJECT
    code = '''from manim import *


class Blank(Scene):
    def construct(self):
        sq = Square().shift(3 * LEFT)
        self.add(sq)
        self.wait(1)
'''
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_presets.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            for which in COMPOSITES:
                msg = {"rev": doc.rev, "type": "edit.composite", "scene": "Blank", "preset": which,
                       "x": 1.5, "y": 0.0, "f": 0}
                if which in ON_OBJECT:
                    r = await doc.frame("Blank", 0, ids=True)
                    msg["object"] = next(o for o in r["objects"] if o["class"] == "Square")
                r = await doc.edit(msg)
                if which == "surface":  # a 2D scene: refused, nothing written
                    assert r["type"] == "edit.refused" and "ThreeDScene" in r["reason"], r
                    assert path.read_bytes() == original
                    continue
                assert r["type"] == "edit.done", (which, r)
                assert (await doc.undo_redo("undo"))["type"] == "edit.done"
                assert path.read_bytes() == original, which
        finally:
            doc.close()
    run(go())


def test_surface_preset_in_a_3d_scene():
    code = '''from manim import *


class Land(ThreeDScene):
    def construct(self):
        self.wait(1)
'''
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_surface.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.edit({"rev": doc.rev, "type": "edit.composite", "scene": "Land", "preset": "surface",
                                "x": 0, "y": 0, "f": 0})
            assert r["type"] == "edit.done", r
            text = path.read_text(encoding="utf-8")
            assert "Surface(lambda u, v: axes.c2p(u, v, np.sin(u) * np.cos(v))," in text
            assert "self.set_camera_orientation(phi=65 * DEGREES, theta=-45 * DEGREES)" in text
            cam = (await doc.frame("Land", 30, "half", "jpeg"))["camera"]
            assert abs(cam["phi"] - 65) < 0.1
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_camera_2d_and_3d():
    import shutil
    from studio.tests.engine.test_engine import ROOT
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_camera.py"
        shutil.copy(ROOT / "studio" / "tests" / "corpus" / "awkward" / "camera.py", path)
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            fps = doc.meta.get("fps", 15)
            f = int(1.2 * fps)  # after the zoom
            cam = (await doc.frame("Zoom", f, "half", "jpeg"))["camera"]
            assert cam["kind"] == "2d" and abs(cam["center"][0] - 2) < 0.01
            r = await doc.edit({"rev": doc.rev, "type": "edit.camera", "scene": "Zoom", "f": f,
                                "center": [1.0, 0.5], "width": cam["width"] * 1.5})
            assert r["type"] == "edit.done", r
            assert "move_to(RIGHT + 0.5 * UP)" in path.read_text(encoding="utf-8")
            # during the move: refused
            r = await doc.edit({"rev": doc.rev, "type": "edit.camera", "scene": "Zoom", "f": int(0.5 * fps),
                                "center": [0.0, 0.0]})
            assert r["type"] == "edit.refused" and "moving here" in r["reason"], r

            cam = (await doc.frame("Orbit", 0, "half", "jpeg"))["camera"]
            assert cam["kind"] == "3d" and abs(cam["phi"] - 70) < 0.1
            r = await doc.edit({"rev": doc.rev, "type": "edit.camera", "scene": "Orbit", "f": 0, "phi": 60})
            assert r["type"] == "edit.done", r
            assert "set_camera_orientation(phi=60 * DEGREES" in path.read_text(encoding="utf-8")
            for _ in range(2):
                assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_dot_on_axes_drags_in_graph_units():
    code = '''from manim import *


class OnAxes(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3, 1], y_range=[-2, 4, 1], x_length=6, y_length=6)
        dot = Dot(axes.c2p(1, 2), color=YELLOW)
        self.add(axes, dot)
        self.wait(1)
'''
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_axes_dot.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.frame("OnAxes", 5, ids=True)
            ax = next(o for o in r["objects"] if o["class"] == "Axes")
            assert ax["coords"]["ex"] == [1.0, 0.0] and ax["coords"]["ey"] == [0.0, 1.0]
            dot = next(o for o in r["objects"] if o["class"] == "Dot")
            r = await doc.edit({"rev": doc.rev, "type": "edit.move", "scene": "OnAxes", "object": dot,
                                "f": 5, "dx": 0.5, "dy": -1.0})
            assert r["type"] == "edit.done", r
            assert "Dot(axes.c2p(1.5, 1), color=YELLOW)" in path.read_text(encoding="utf-8")
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_transform_ghost_and_match_these():
    code = '''from manim import *


class Match(Scene):
    def construct(self):
        a = MathTex("x", "+", "y")
        b = MathTex("y", "+", "z").shift(DOWN * 2)
        sq = Square().shift(LEFT * 4)
        self.add(a, sq)
        self.play(TransformMatchingTex(a, b), sq.animate.shift(RIGHT), run_time=1)
        self.wait(1)
'''
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_match.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.frame("Match", 2, ids=True)
            gh = {g["index"]: g for g in r["ghosts"]}
            m = gh[0]
            assert m["keys"] and sorted(p["key"] for p in m["pairs"]) == ["+", "y"]
            assert [u["key"] for u in m["unmatched_source"]] == ["x"]
            assert [u["key"] for u in m["unmatched_target"]] == ["z"]
            # the .animate move: its target is one unit right of the square
            assert abs(gh[1]["target"][0] - (-4 - 1 + 1)) < 0.05
            assert "ghosts" not in await doc.frame("Match", 20, ids=True)  # in the wait: none

            clip = next(c for c in doc.model()["scenes"][0]["clips"] if c["kind"] == "play")
            r = await doc.edit({"rev": doc.rev, "type": "edit.match_parts", "scene": "Match",
                                "clip": clip["index"], "arg": 0, "source_key": "x", "target_key": "z"})
            assert r["type"] == "edit.done", r
            assert 'key_map={"x": "z"}),' in path.read_text(encoding="utf-8")
            r = await doc.frame("Match", 2, ids=True)
            m = next(g for g in r["ghosts"] if g["index"] == 0)
            assert any(p.get("mapped") and p["key"] == "x" and p["to"] == "z" for p in m["pairs"])
            assert not m["unmatched_source"] and not m["unmatched_target"]
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_3d_objects_report_projection_and_move_in_world():
    code = '''from manim import *


class Floor(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=60 * DEGREES, theta=-45 * DEGREES)
        cube = Cube(side_length=1).shift(RIGHT)
        label = Text("pinned", font_size=30).to_corner(UL)
        self.add_fixed_in_frame_mobjects(label)
        self.add(cube)
        self.wait(1)
'''
    async def go():
        import math
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_floor.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.frame("Floor", 5, ids=True)
            cube = next(o for o in r["objects"] if o["class"] == "Cube")
            label = next(o for o in r["objects"] if o["class"] == "Text")
            assert "proj" in cube and "proj" not in label
            # theta -45: world x points down-right on screen, world y up-right
            ex, ey = cube["proj"]["ex"], cube["proj"]["ey"]
            assert ex[0] > 0 and ex[1] < 0 and ey[0] > 0 and ey[1] > 0
            assert abs(math.hypot(*cube["proj"]["ez"]) - math.sin(math.radians(60))) < 0.15
            r = await doc.edit({"rev": doc.rev, "type": "edit.move", "scene": "Floor", "object": cube,
                                "f": 5, "dx": 0.0, "dy": 1.5})
            assert r["type"] == "edit.done", r
            assert "Cube(side_length=1).shift(RIGHT + 1.5 * UP)" in path.read_text(encoding="utf-8")
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())


def test_area_and_riemann_fields():
    code = '''from manim import *


class Area(Scene):
    def construct(self):
        axes = Axes(x_range=[0, 4, 1], y_range=[0, 4, 1], x_length=6, y_length=4)
        curve = axes.plot(lambda x: 0.25 * x**2)
        area = axes.get_area(curve, x_range=[1, 3], opacity=0.4)
        rects = axes.get_riemann_rectangles(curve, x_range=[0, 2], dx=0.5)
        self.add(axes, curve, area, rects)
        self.wait(1)
'''
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p5_area.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            r = await doc.frame("Area", 5, ids=True)
            area = next(o for o in r["objects"] if o.get("name") == "area")
            rects = next(o for o in r["objects"] if o.get("name") == "rects")
            assert [x["kw"] for x in area["ranges"]] == ["x_range", "opacity"]
            dx = next(x for x in rects["ranges"] if x["kw"] == "dx")["parts"][0]
            r = await doc.edit({"rev": doc.rev, "type": "edit.literal", "scene": "Area",
                                "span": dx["span"], "value": {"number": 0.25}})
            assert r["type"] == "edit.done", r
            assert "dx=0.25" in path.read_text(encoding="utf-8")
            assert (await doc.undo_redo("undo"))["type"] == "edit.done"
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())
