"""Phase 7 unit tests (plan: docs/phase7/plan.md)."""

import ast

import pytest

from studio.server.code.inserts import HOUSE_VOICE, new_file_text
from studio.server.code.splice import EditError


# -- step 2: the New file dialog's options --------------------------------------------------
@pytest.mark.parametrize("voice", [False, True])
@pytest.mark.parametrize("target", [None, 5.0, 12.5])
def test_template_options_parse(voice, target):
    text = new_file_text("Opt", target=target, voice=voice)
    cls = ast.parse(text).body[-1]
    assert isinstance(cls, ast.ClassDef) and cls.name == "Opt"
    names = {t.id: st.value for st in cls.body if isinstance(st, ast.Assign) for t in st.targets}
    assert ast.literal_eval(names["VOICE"]) == (HOUSE_VOICE if voice else None)
    if target is None:
        assert "TARGET" not in names
    else:
        assert ast.literal_eval(names["TARGET"]) == target


def test_template_default_is_unchanged():
    # files made before Phase 7 (and the engine tests' blank file) keep their bytes
    assert new_file_text("Demo") == new_file_text("Demo", target=5.0, voice=False)
    assert "VOICE = None  # set a voice to narrate\n    TARGET = 5.0" in new_file_text("Demo")


@pytest.mark.parametrize("bad", [0, -1, 1e9, "5"])
def test_template_refuses_bad_lengths(bad):
    with pytest.raises(EditError):
        new_file_text("Opt", target=bad)


# -- step 3: add, delete, rename a scene ----------------------------------------------------
from studio.server.code.scenes import plan_scene_add, plan_scene_delete, plan_scene_rename  # noqa: E402
from studio.server.code.source import Source  # noqa: E402
from studio.server.code.splice import apply  # noqa: E402

BEATS = '''"""A video.

Render order: Hook, Walk.
"""

from manim import *
from manim_kit import *


class Beat(TimedScene):
    CAPTIONS = True


class Hook(Beat):
    TARGET = 7.6

    def construct(self):
        self.at(0.2)
        self.wait(1)


class Walk(Beat):
    TARGET = 11.8

    def construct(self):
        self.wait(2)
'''


def _run(text, plan):
    out = apply(text.encode(), plan.edits).decode()
    ast.parse(out)
    return out


def test_add_after_copies_base_and_target():
    out = _run(BEATS, plan_scene_add(Source(BEATS.encode()), "Hook", "Middle", "after", ["Hook", "Walk"], set()))
    assert "class Hook(Beat):\n    TARGET = 7.6\n\n    def construct(self):\n        self.at(0.2)\n        self.wait(1)\n" \
           "\n\nclass Middle(Beat):\n    TARGET = 7.6\n\n    def construct(self):\n        pass\n\n\nclass Walk(Beat):" in out
    assert "Render order: Hook, Middle, Walk." in out


def test_add_at_end_and_template_scene():
    src = new_file_text("Only", voice=True)
    out = _run(src, plan_scene_add(Source(src.encode()), "Only", "Second", "end", ["Only"], set()))
    assert out.endswith('class Second(TimedScene):\n    VOICE = "en-US-AndrewNeural"\n    TARGET = 5.0\n\n'
                        "    def construct(self):\n        apply_background()\n")
    assert "\n\n\nclass Second" in out


def test_add_with_scenes_list_and_crlf():
    text = (BEATS + '\nSCENES = ["Hook", "Walk"]\n').replace("\n", "\r\n")
    out = apply(text.encode(), plan_scene_add(Source(text.encode()), "Hook", "Mid", "after",
                                              ["Hook", "Walk"], set()).edits).decode()
    assert 'SCENES = ["Hook", "Mid", "Walk"]' in out and "Render order: Hook, Mid, Walk." in out
    assert "\n" not in out.replace("\r\n", "")  # line endings kept
    end = plan_scene_add(Source(text.encode()), "Hook", "Last", "end", ["Hook", "Walk"], set())
    out = apply(text.encode(), end.edits).decode()
    assert 'SCENES = ["Hook", "Walk", "Last"]' in out
    assert out.index("class Last") < out.index("SCENES =")  # after the last class, not after SCENES


def test_add_with_decorator_and_keywords():
    text = "from manim import *\n\n\n@dataclass\nclass A(Scene, metaclass=M):\n    def construct(self):\n        pass\n"
    out = _run(text, plan_scene_add(Source(text.encode()), "A", "B", "after", ["A"], set()))
    assert "class B(Scene, metaclass=M):\n    def construct(self):\n        pass\n" in out
    assert "@" not in out.split("class B")[1]


@pytest.mark.parametrize("bad,why", [("Hook", "already"), ("Beat", "already"), ("2x", "not a class"),
                                     ("class", "reserves"), ("None", "reserves"), ("Circle", "Manim")])
def test_add_refuses_bad_names(bad, why):
    with pytest.raises(EditError, match=why):
        plan_scene_add(Source(BEATS.encode()), "Hook", bad, "after", ["Hook", "Walk"], {"Circle"})


def test_delete_scene_and_its_listing():
    text = BEATS + '\nSCENES = ["Hook", "Walk"]\n'
    out = _run(text, plan_scene_delete(Source(text.encode()), "Hook", ["Hook", "Walk"]))
    assert "class Hook" not in out and 'SCENES = ["Walk"]' in out and "Render order: Walk." in out
    assert "    CAPTIONS = True\n\n\nclass Walk(Beat):" in out  # spacing kept
    out = _run(BEATS, plan_scene_delete(Source(BEATS.encode()), "Walk", ["Hook", "Walk"]))
    assert out.endswith("        self.wait(1)\n") and "Render order: Hook." in out


def test_delete_refusals():
    with pytest.raises(EditError, match="only scene"):
        plan_scene_delete(Source(BEATS.encode()), "Hook", ["Hook"])
    text = BEATS + "\n\nclass Later(Hook):\n    pass\n"
    with pytest.raises(EditError, match="other code names Hook"):
        plan_scene_delete(Source(text.encode()), "Hook", ["Hook", "Walk", "Later"])


def test_rename_scene_everywhere_it_is_listed():
    text = BEATS + "\nSCENES = ['Hook', 'Walk']\n"
    out = _run(text, plan_scene_rename(Source(text.encode()), "Walk", "Stroll", ["Hook", "Walk"], set()))
    assert "class Stroll(Beat):" in out and "SCENES = ['Hook', 'Stroll']" in out
    assert "Render order: Hook, Stroll." in out and "Walk" not in out


def test_rename_refused_when_code_names_the_class():
    text = BEATS.replace("        self.wait(2)\n", "        self.wait(2)\n        super(Walk, self)\n")
    with pytest.raises(EditError, match="rename it in the code"):
        plan_scene_rename(Source(text.encode()), "Walk", "Stroll", ["Hook", "Walk"], set())


# -- step 4: TARGET ---------------------------------------------------------------------------
from studio.server.code.timeline import plan_target  # noqa: E402


def test_target_changes_own_literal_in_style():
    t = "class A(TimedScene):\n    TARGET = 5.0\n\n    def construct(self):\n        pass\n"
    assert "TARGET = 7.0\n" in _run(t, plan_target(Source(t.encode()), "A", 7))
    assert "TARGET = 7.25\n" in _run(t, plan_target(Source(t.encode()), "A", 7.25))


@pytest.mark.parametrize("body,want", [
    ("    VOICE = None\n\n    def construct(self):\n        pass\n",
     "    VOICE = None\n    TARGET = 4\n\n    def construct(self):"),
    ("    def construct(self):\n        pass\n", "class A(TimedScene):\n    TARGET = 4\n\n    def construct(self):"),
    ('    """Doc."""\n\n    def construct(self):\n        pass\n', '    """Doc."""\n    TARGET = 4\n\n    def construct'),
])
def test_target_added_when_the_class_has_none(body, want):
    t = "class A(TimedScene):\n" + body
    assert want in _run(t, plan_target(Source(t.encode()), "A", 4))


def test_target_refusals():
    t = "class A(TimedScene):\n    TARGET = 2 * 3\n\n    def construct(self):\n        pass\n"
    with pytest.raises(EditError, match="computed"):
        plan_target(Source(t.encode()), "A", 4)
    t = "class A(TimedScene):\n    TARGET = 4\n\n    def construct(self):\n        pass\n"
    with pytest.raises(EditError, match="already"):
        plan_target(Source(t.encode()), "A", 4)
    with pytest.raises(EditError, match="more than 0"):
        plan_target(Source(t.encode()), "A", 0)


# -- step 5: narrating a silent scene ----------------------------------------------------------
from studio.server.code.timeline import plan_set_voice, voice_state  # noqa: E402

SILENT_BASE = '''class Beat(TimedScene):
    VOICE = None
    CAPTIONS = True


class One(Beat):
    TARGET = 4

    def construct(self):
        pass


class Two(Beat):
    def construct(self):
        pass
'''


def test_voice_state_finds_the_owner():
    assert voice_state(Source(SILENT_BASE.encode()), "One") == {"silent": True, "owner": "Beat", "line": 2}
    t = new_file_text("A")
    assert voice_state(Source(t.encode()), "A")["owner"] == "A"
    assert not voice_state(Source(new_file_text("A", voice=True).encode()), "A")["silent"]
    assert voice_state(Source(b"class A(TimedScene):\n    pass\n"), "A") == {"silent": False, "owner": None, "line": None}


def test_set_voice_on_the_scene_or_its_base():
    out = _run(SILENT_BASE, plan_set_voice(Source(SILENT_BASE.encode()), "One", "class"))
    assert 'class One(Beat):\n    TARGET = 4\n    VOICE = "en-US-AndrewNeural"\n\n    def construct' in out
    assert "    VOICE = None\n" in out  # Two stays silent
    out = _run(SILENT_BASE, plan_set_voice(Source(SILENT_BASE.encode()), "Two", "class"))
    assert 'class Two(Beat):\n    VOICE = "en-US-AndrewNeural"\n\n    def construct' in out
    out = _run(SILENT_BASE, plan_set_voice(Source(SILENT_BASE.encode()), "Two", "base"))
    assert 'class Beat(TimedScene):\n    VOICE = "en-US-AndrewNeural"\n    CAPTIONS' in out
    t = new_file_text("A")
    out = _run(t, plan_set_voice(Source(t.encode()), "A", "class"))
    assert 'VOICE = "en-US-AndrewNeural"  # the house voice; None for a silent scene' in out
    assert "set a voice to narrate" not in out
    with pytest.raises(EditError, match="not on a base"):
        plan_set_voice(Source(t.encode()), "A", "base")
    t = new_file_text("A", voice=True)
    with pytest.raises(EditError, match="already has a voice"):
        plan_set_voice(Source(t.encode()), "A", "class")


# -- step 9: scale and turn as the Inspector shows them -------------------------------------
from studio.server.code.moves import chained_transform  # noqa: E402


@pytest.mark.parametrize("code,want", [
    ("Square()", (1.0, 0.0)),
    ("Square().scale(1.3)", (1.3, 0.0)),
    ("get_plane(RIGHT).scale(1.3).rotate(30 * DEGREES).scale(2)", (2.6, 30.0)),
    ("Square().rotate(PI / 2).shift(UP)", (1.0, 90.0)),
    ("Square().scale(k)", None),
])
def test_chained_transform(code, want):
    src = Source(f"x = {code}\n".encode())
    call = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name))
    assert chained_transform(src, call) == want


# A scale edit can chain onto the object's last placement statement, not its
# constructor: the Inspector reads that statement too (found making odd_squares.py)
from studio.server.code.moves import transform_calls, transform_value  # noqa: E402


@pytest.mark.parametrize("code,want", [
    ("eq.shift(UP * 0.5).scale(0.9)", (0.9, 0.0)),   # the site is eq.shift(...)
    ("eq.scale(0.9)", (0.9, 0.0)),                   # a scale statement of its own
    ("eq.rotate(PI / 2).scale(2)", (2.0, 90.0)),
    ("eq.shift(UP).scale(k)", None),
])
def test_transform_of_a_later_statement(code, want):
    src = Source(f"{code}\n".encode())
    call = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call)
                and isinstance(n.func.value, ast.Name))  # the innermost eq.<method>(...)
    assert transform_value(transform_calls(src, call)) == want
