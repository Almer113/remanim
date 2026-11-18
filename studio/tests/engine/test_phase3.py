"""Phase 3 through a real worker: build a scene from a blank file with canvas
and library edits only, check the code reads like hand-written Manim, then
undo everything back to the template bytes. Also drags on awkward files.

Never run while the studio server or a corpus run is busy (shared
media/Tex_studio).
"""

import ast
import asyncio
import shutil

from studio.server.code.inserts import new_file_text
from studio.server.code.census import classify
from studio.server.project import Document
from studio.tests.engine.test_engine import CORPUS, TMP, _quiet, run


async def _objects(doc, scene, f):
    r = await doc.frame(scene, f, ids=True)
    assert "error" not in r, r.get("error")
    return r["objects"]


async def _edit(doc, msg):
    r = await doc.edit({"rev": doc.rev, **msg})
    if r["type"] == "edit.preview":
        r = await doc.confirm(r["token"])
    assert r["type"] == "edit.done", r
    return r


def _find(objs, cls, name=None):
    return next(o for o in objs if o["class"] == cls and (name is None or o.get("name") == name)
                and not o.get("virtual"))


def test_build_a_scene_from_a_blank_file():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "blank_build.py"
        template = new_file_text("Build").encode()
        path.write_bytes(template)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            S = "Build"
            assert doc.traces[S]["duration"] == 5.0
            fps = doc.meta["fps"]
            # drop a square at 0.5 s, a title at 1.5 s
            await _edit(doc, {"type": "edit.insert", "scene": S, "class": "Square", "x": -2, "y": 0,
                              "f": int(1 * fps)})
            await _edit(doc, {"type": "edit.insert", "scene": S, "class": "Text", "x": 0, "y": 3,
                              "region": "title", "f": int(2 * fps)})
            f = int(3 * fps)
            sq = _find(await _objects(doc, S, f), "Square")
            # drag it, scale it, turn it
            await _edit(doc, {"type": "edit.move", "scene": S, "object": sq, "f": f, "dx": 1.5, "dy": -0.5})
            sq = _find(await _objects(doc, S, f), "Square")
            assert abs(sq["center"][0] + 0.5) < 0.01 and abs(sq["center"][1] + 0.5) < 0.01
            await _edit(doc, {"type": "edit.scale", "scene": S, "object": sq, "f": f, "k": 1.5})
            sq = _find(await _objects(doc, S, f), "Square")
            await _edit(doc, {"type": "edit.rotate", "scene": S, "object": sq, "f": f, "deg": 30})
            sq = _find(await _objects(doc, S, f), "Square")
            # an animation preset on it, then a copy, then group both
            await _edit(doc, {"type": "edit.preset", "scene": S, "object": sq, "preset": "Indicate", "f": f})
            await _edit(doc, {"type": "edit.duplicate", "scene": S, "object": sq, "f": int(4 * fps)})
            objs = await _objects(doc, S, int(4.9 * fps))
            pair = [o for o in objs if o["class"] == "Square" and not o.get("virtual")]
            assert len(pair) == 2
            await _edit(doc, {"type": "edit.group", "scene": S, "objects": pair, "f": int(4.9 * fps)})
            code = path.read_text(encoding="utf-8")
            print(code)
            ast.parse(code)
            # reads like hand-written Manim: every statement the studio wrote is tier 1
            tiers = classify(ast.parse(code), set(doc.api) | {"Square", "Text", "VGroup", "place", "ACCENT", "FG",
                                                              "BODY_SIZE", "Create", "Write", "Indicate", "FadeIn",
                                                              "LEFT", "RIGHT", "UP", "DOWN", "DEGREES",
                                                              "apply_background", "TimedScene"})
            assert all(t == 1 for t in tiers.lines.values()), tiers.lines
            # the drag edited the literal move_to(); scale and rotate chained after it
            assert "square = Square(side_length=2, color=ACCENT).move_to(0.5 * LEFT + 0.5 * DOWN)" \
                   ".rotate(30 * DEGREES).scale(1.5)" in code
            assert "        self.at(1)\n        self.play(Create(square), run_time=0.8)\n" in code
            assert 'text = place(Text("Text", font_size=BODY_SIZE, color=FG), "title")' in code
            assert "square_2 = square.copy().shift(0.5 * RIGHT + 0.5 * DOWN)" in code
            assert "group = VGroup(square, square_2)" in code
            assert "self.play(Indicate(square), run_time=1)" in code
            # delete the copy (its group refers to it: refused), undo to the start
            sq2 = next(o for o in pair if o.get("name") == "square_2")
            r = await doc.edit({"type": "edit.delete", "rev": doc.rev, "scene": S, "object": sq2,
                                "f": int(4.9 * fps)})
            assert r["type"] == "edit.refused" and "line" in r["reason"]
            while doc.undo:
                r = await doc.undo_redo("undo")
                assert r["type"] == "edit.done", r
            assert path.read_bytes() == template
        finally:
            doc.close()
    run(go())


def test_drag_and_back_on_helpers():
    """S2 as a test: every object on screen moves exactly, and back restores bytes."""
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        dst = TMP / "helpers.py"
        shutil.copyfile(CORPUS / "helpers.py", dst)
        orig = dst.read_bytes()
        doc = Document(dst, [], _quiet)
        try:
            await doc.load()
            S = "Helpers"
            f = doc.frame_count(S) - 1
            objs = [o for o in await _objects(doc, S, f) if not o.get("virtual")]
            assert len(objs) >= 15
            for o in objs:
                await _edit(doc, {"type": "edit.move", "scene": S, "object": o, "f": f, "dx": 0.4, "dy": -0.25})
                o2 = next(x for x in await _objects(doc, S, f) if x["id"] == o["id"])
                await _edit(doc, {"type": "edit.move", "scene": S, "object": o2, "f": f, "dx": -0.4, "dy": 0.25})
                assert dst.read_bytes() == orig, o["id"]
        finally:
            doc.close()
    run(go())


def test_mid_animation_drag_is_refused():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        dst = TMP / "helpers.py"
        shutil.copyfile(CORPUS / "helpers.py", dst)
        doc = Document(dst, [], _quiet)
        try:
            await doc.load()
            S = "Helpers"
            f = int(0.5 * doc.meta["fps"])  # inside top[2].animate.shift
            o = next(x for x in await _objects(doc, S, f) if x["id"] == "Square@7:20#2")
            r = await doc.edit({"type": "edit.move", "rev": doc.rev, "scene": S, "object": o, "f": f,
                                "dx": 1, "dy": 0})
            assert r["type"] == "edit.refused" and "animating" in r["reason"]
        finally:
            doc.close()
    run(go())


def test_only_this_one_property_override():
    """A colour edit on one dot of a comprehension offers `dots[1].set_color(...)`
    next to the edit that changes every dot; the override is verified and written."""
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "override_one.py"
        path.write_text("from manim import *\n\n\nclass Dots(Scene):\n    def construct(self):\n"
                        "        dots = [Dot(RIGHT * x, color=BLUE) for x in (-2, 0, 2)]\n"
                        "        self.add(*dots)\n        self.wait(1)\n", encoding="utf-8")
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            objs = await _objects(doc, "Dots", 5)
            mid = next(o for o in objs if o["class"] == "Dot" and abs((o.get("center") or [9])[0]) < 0.1)
            r = await doc.edit({"type": "edit.prop", "rev": doc.rev, "scene": "Dots", "object": mid,
                                "prop": "color", "value": {"name": "RED"}, "f": 5})
            assert r["type"] == "edit.preview", r
            alts = r.get("alternatives") or []
            assert len(alts) == 1 and "dots[1].set_color(RED)" in alts[0]["summary"]
            done = await doc.confirm(alts[0]["token"])
            assert done["type"] == "edit.done", done
            code = path.read_text(encoding="utf-8")
            assert "for x in (-2, 0, 2)]\n        dots[1].set_color(RED)\n        self.add(*dots)" in code
            assert "color=BLUE" in code  # the other dots keep theirs
        finally:
            doc.close()
    run(go())


def test_animate_in_a_multi_line_play_edits_the_animate_vector():
    """The house style splits self.play( over lines; _MethodAnimation.finish()
    must not hide the .animate record (review after Phase 3, engine #1)."""
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "animate_multiline.py"
        code = ("from manim import *\n\n\nclass A(Scene):\n    def construct(self):\n"
                "        c = Circle()\n        d = Dot()\n        self.add(c, d)\n"
                "        self.play(\n            c.animate.shift(RIGHT),\n            run_time=1,\n        )\n"
                "        move = d.animate.shift(UP)\n        self.play(move)\n        self.wait(1)\n")
        path.write_text(code, encoding="utf-8", newline="\n")
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            f = int(2.5 * doc.meta["fps"])
            objs = await _objects(doc, "A", f)
            for cls, before, after in [("Circle", "c.animate.shift(RIGHT)", "c.animate.shift(RIGHT + 0.5 * UP)"),
                                       ("Dot", "d.animate.shift(UP)", "d.animate.shift(0.5 * RIGHT + UP)")]:
                o = _find(objs, cls)
                assert o["placement"]["move"]["kind"] == "animate", o["placement"]["move"]
                dx, dy = (0, 0.5) if cls == "Circle" else (0.5, 0)
                r = await _edit(doc, {"type": "edit.move", "scene": "A", "object": o, "f": f, "dx": dx, "dy": dy})
                assert after in path.read_text(encoding="utf-8"), (r, path.read_text(encoding="utf-8"))
                objs = await _objects(doc, "A", f)
            while doc.undo:
                r = await doc.undo_redo("undo")
                assert r["type"] == "edit.done", r
            assert path.read_text(encoding="utf-8") == code
        finally:
            doc.close()
            path.unlink(missing_ok=True)
    run(go())
