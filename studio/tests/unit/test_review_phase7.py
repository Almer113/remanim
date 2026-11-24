"""Review after Phase 7 (studio/docs/review_phase7.md): regression tests for
what the review found in the code layer, the server and the deployment."""

import pytest

from studio.server.app import shadows_module
from studio.server.code import scenes
from studio.server.code.source import Source
from studio.server.code.splice import apply
from studio.server.project import ending_waits

TWO = '''from manim import *


class A(Scene):
    def construct(self):
        self.wait(1)
        # self.play(Write(x))  an old idea, kept


class B(Scene):
    def construct(self):
        pass
'''


def _apply(text, plan_fn, *args):
    src = Source(text.encode())
    plan = plan_fn(src, *args)
    out = apply(src.data, plan.edits).decode()
    compile(out, "scene.py", "exec")
    return out, plan.note


def test_docstring_prose_naming_a_scene_is_not_a_render_order():
    one = '"""Intro scene for the Euler video."""\nfrom manim import *\n\n\nclass Intro(Scene):\n    def construct(self):\n        pass\n'
    out, note = _apply(one, scenes.plan_scene_add, "Intro", "Outro", "after", ["Intro"], set())
    assert out.startswith('"""Intro scene for the Euler video."""') and "docstring" not in note
    out, _ = _apply(one, scenes.plan_scene_rename, "Intro", "Opening", ["Intro"], set())
    assert out.startswith('"""Intro scene for')


def test_a_labelled_render_order_still_follows():
    doc = '"""Shows A, B in a row.\n\nRender order: A, B.\n"""\n' + TWO
    out, note = _apply(doc, scenes.plan_scene_add, "A", "N", "after", ["A", "B"], set())
    assert "Shows A, B in a row" in out and "Render order: A, N, B." in out and "docstring" in note
    beats = '"""Beats: A, B (render in that order)."""\n' + TWO
    out, _ = _apply(beats, scenes.plan_scene_rename, "B", "Proof", ["A", "B"], set())
    assert "Beats: A, Proof (render" in out


PER_LINE = TWO + '\n\nSCENES = [\n    "A",  # the intro, 12 s\n    "B",  # the proof\n]\n'


def test_one_name_per_line_keeps_each_comment_with_its_name():
    out, _ = _apply(PER_LINE, scenes.plan_scene_delete, "B", ["A", "B"])
    assert 'SCENES = [\n    "A",  # the intro, 12 s\n]\n' in out
    out, _ = _apply(PER_LINE, scenes.plan_scene_add, "A", "C", "after", ["A", "B"], set())
    assert '    "A",  # the intro, 12 s\n    "C",\n    "B",  # the proof\n' in out
    no_comma = TWO + '\n\nSCENES = [\n    "A",  # one\n    "B"  # two\n]\n'
    out, _ = _apply(no_comma, scenes.plan_scene_add, "B", "C", "after", ["A", "B"], set())
    assert '    "B",  # two\n    "C"\n]' in out
    # the bracket on the last name's line is not "one per line": the bracket stays
    tight = TWO + '\n\nSCENES = [\n    "A",\n    "B"]\n'
    out, _ = _apply(tight, scenes.plan_scene_delete, "B", ["A", "B"])
    assert out.rstrip().endswith('"A"]')


@pytest.mark.parametrize("before,op,after", [
    ('SCENES = ()', ("add", "A", "C"), 'SCENES = ("C",)'),
    ('SCENES = ("B",)', ("delete", "B"), 'SCENES = ()'),
    ('SCENES = ["B"]', ("delete", "B"), 'SCENES = []'),
    ('SCENES = ("A", "B",)', ("delete", "B"), 'SCENES = ("A",)'),
])
def test_scenes_tuples_stay_tuples(before, op, after):
    text = TWO + "\n\n" + before + "\n"
    if op[0] == "add":
        out, _ = _apply(text, scenes.plan_scene_add, op[1], op[2], "after", ["A", "B"], set())
    else:
        out, _ = _apply(text, scenes.plan_scene_delete, op[1], ["A", "B"])
    assert out.rstrip().endswith(after)


def test_a_class_keeps_its_trailing_comments():
    out, _ = _apply(TWO, scenes.plan_scene_add, "A", "N", "after", ["A", "B"], set())
    assert "# self.play(Write(x))  an old idea, kept\n\n\nclass N(Scene):" in out
    out, _ = _apply(TWO, scenes.plan_scene_delete, "A", ["A", "B"])
    assert "old idea" not in out and "class B" in out


def test_a_reserved_word_says_so():
    from studio.server.code.splice import EditError
    with pytest.raises(EditError, match="reserves"):
        scenes.plan_scene_add(Source(TWO.encode()), "A", "None", "after", ["A", "B"], set())


def _ev(start, dur, call=None, kind="wait"):
    return {"start": start, "duration": dur, "call": call, "kind": kind}


def test_the_narration_tail_is_not_called_padding():
    play = _ev(0, 4, call=[1, 0, 1, 9], kind="play")
    voiced = {"audio": {"lines": [{"start": 2, "duration": 5}]}}
    # narration to 7 s, then padding to TARGET 9
    assert ending_waits({"events": [play, _ev(4, 3), _ev(7, 2)], "target": 9, **voiced}, 15) == \
        {1: "narration", 2: "padding"}
    # the narration runs past TARGET: no padding at all, only the tail
    assert ending_waits({"events": [play, _ev(4, 5)], "target": 8, **voiced}, 15) == {1: "narration"}
    # no narration, no TARGET: nothing to name
    assert ending_waits({"events": [play, _ev(4, 1)]}, 15) == {}
    # a wait the scene's code made is never one of these
    assert ending_waits({"events": [_ev(0, 9, call=[3, 0, 3, 9])], "target": 9}, 15) == {}


@pytest.mark.parametrize("stem,bad", [("manim", True), ("numpy", True), ("math", True), ("style", True),
                                      ("manim_kit", True), ("my_scene", False), ("euler_video", False)])
def test_a_new_file_may_not_shadow_a_module(stem, bad):
    assert shadows_module(stem) is bad


def test_setting_the_voice_fixes_the_template_comment():
    # friction 7 of the odd_squares run: "# set a voice to narrate" stayed after the voice was set
    from studio.server.code.inserts import new_file_text
    from studio.server.code.timeline import plan_set_voice
    t = new_file_text("Walk", 5.0, False)
    out, _ = _apply(t, plan_set_voice, "Walk", "class")
    assert 'VOICE = "en-US-AndrewNeural"  # the house voice; None for a silent scene' in out
    assert "set a voice" not in out
    base = 'from manim import *\nfrom manim_kit import *\n\n\nclass Beat(TimedScene):\n    VOICE = None  # set a voice to narrate\n\n\nclass A(Beat):\n    def construct(self):\n        pass\n'
    out, _ = _apply(base, plan_set_voice, "A", "base")
    assert "VOICE = \"en-US-AndrewNeural\"  # the house voice" in out
    own = base.replace("# set a voice to narrate", "# quiet for now")
    out, _ = _apply(own, plan_set_voice, "A", "base")
    assert "# quiet for now" in out  # a comment of your own is left alone


def test_export_drafts_answers_from_disk():
    # friction 10: the "low quality first" check forgot renders made before a server restart
    import asyncio
    from studio.server import app
    r = asyncio.run(app.handle({"type": "export.drafts", "file": "odd_squares.py"}))
    assert r["type"] == "export.drafts" and isinstance(r["scenes"], list)
    bad = asyncio.run(app.handle({"type": "export.drafts", "file": "../outside.py"}))
    assert bad["type"] == "error"
