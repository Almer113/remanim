"""Phase 5 step 6: the part-colour planner (glyph maps given, no LaTeX run)."""

import ast

import pytest

from studio.server.code import tex
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply

HEAD = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n"


def scene(*lines):
    return HEAD + "".join("        " + ln + "\n" for ln in lines)


def obj_for(code, cls, texts=None):
    src = Source(code.encode())
    call = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == cls)
    return src, {"class": cls, "site": [call.lineno, call.col_offset, call.end_lineno, call.end_col_offset],
                 "texts": texts or [{"editable": True}] * len(call.args)}


def run(code, cls, glyphs, picked, colour="YELLOW"):
    src, obj = obj_for(code, cls)
    sel = tex.selection(glyphs, picked)
    return [apply(code.encode(), p.edits).decode() for p in tex.candidates(src, obj, glyphs, sel, colour)]


# "a^2 + b^2" drawn as: 2, a, +, 2, b   (each script before its base, as dvisvgm draws)
PYTH = {"kind": "tex", "parts": ["a^2 + b^2"],
        "map": [[0, 2, 3], [0, 0, 1], [0, 4, 5], [0, 8, 9], [0, 6, 7]]}


def test_a_unique_piece_is_isolated_by_its_tex():
    code = scene('eq = MathTex("a^2 + b^2")', "self.add(eq)")
    out = run(code, "MathTex", PYTH, [2])
    assert 'MathTex("a^2 + b^2", tex_to_color_map={"+": YELLOW})' in out[0]
    assert "eq[0][2].set_color(YELLOW)" in out[1]  # the fallback, if the replay disagrees


def test_a_piece_that_repeats_gets_an_index_override():
    code = scene('eq = MathTex("a^2 + b^2")', "self.add(eq)")
    out = run(code, "MathTex", PYTH, [0])  # the first "2" occurs twice in the TeX
    assert len(out) == 1 and "eq[0][0].set_color(YELLOW)" in out[0]


def test_no_isolation_when_code_indexes_the_formula():
    code = scene('eq = MathTex("a^2 + b^2")', "self.play(Indicate(eq[0][1]))")
    out = run(code, "MathTex", PYTH, [2])
    assert len(out) == 1 and "eq[0][2].set_color(YELLOW)" in out[0]
    code = scene('eq = MathTex("a^2 + b^2")', 'f = MathTex("c")', "self.play(TransformMatchingTex(eq, f))")
    assert len(run(code, "MathTex", PYTH, [2])) == 1


def test_a_whole_argument_is_coloured_by_index():
    g = {"kind": "tex", "parts": ["a^2", "+", "b^2"],
         "map": [[0, 2, 3], [0, 0, 1], [1, 0, 1], [2, 2, 3], [2, 0, 1]]}
    code = scene('eq = MathTex("a^2", "+", "b^2")')
    out = run(code, "MathTex", g, [3, 4])
    assert out == [code + "        eq[2].set_color(YELLOW)\n"]


def test_glyphs_from_two_parts_are_refused():
    g = {"kind": "tex", "parts": ["a", "b"], "map": [[0, 0, 1], [1, 0, 1]]}
    with pytest.raises(EditError, match="one part"):
        run(scene('eq = MathTex("a", "b")'), "MathTex", g, [0, 1])


def test_an_unnamed_formula_needs_a_unique_piece():
    code = scene('self.add(MathTex("a^2 + b^2"))')
    assert 'tex_to_color_map={"+": YELLOW}' in run(code, "MathTex", PYTH, [2])[0]
    with pytest.raises(EditError, match="no name"):
        run(code, "MathTex", PYTH, [0])


def test_existing_map_is_extended():
    code = scene('eq = MathTex("a^2 + b^2", tex_to_color_map={"a": RED})')
    out = run(code, "MathTex", PYTH, [2])
    assert 'tex_to_color_map={"a": RED, "+": YELLOW}' in out[0]


def test_backslash_tex_is_written_raw():
    g = {"kind": "tex", "parts": [r"x \cdot y"], "map": [[0, 0, 1], [0, 2, 7], [0, 8, 9]]}
    code = scene(r'eq = MathTex(r"x \cdot y")')
    assert r'tex_to_color_map={r"\cdot": YELLOW}' in run(code, "MathTex", g, [1])[0]


def test_text_word_and_repeated_word():
    t = "to be or not to be"
    chars = [i for i, c in enumerate(t) if not c.isspace()]
    g = {"kind": "text", "parts": [t], "map": [[0, i, i + 1] for i in chars]}
    code = scene(f'line = Text("{t}")')
    out = run(code, "Text", g, [4, 5])  # "or": once
    assert 'Text("to be or not to be", t2c={"or": YELLOW})' in out[0]
    assert "line[4:6].set_color(YELLOW)" in out[1]
    out = run(code, "Text", g, [0, 1])  # "to": twice -> Manim's slice key
    assert 't2c={"[0:2]": YELLOW}' in out[0]


def test_selection_grows_to_whole_pieces():
    g = {"kind": "tex", "parts": [r"\vec{v}"], "map": [[0, 0, 7], [0, 0, 7]]}
    assert tex.selection(g, [1]) == [0, 1]


def test_check():
    same = lambda a, b: a == b  # noqa: E731
    before = ["#ffffff"] * 3
    assert tex.check(before, {"colors": ["#ffffff", "#ffff00", "#ffffff"]}, [1], "#ffff00", same) is None
    assert "changed colour too" in tex.check(before, {"colors": ["#ff0000", "#ffff00", "#ffffff"]}, [1],
                                             "#ffff00", same)
    assert "how many glyphs" in tex.check(before, {"colors": ["#ffffff"]}, [0], None, same)
