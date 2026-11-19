"""Narration edits in the code layer (Phase 4 step 3), no Manim."""

import ast

import pytest

from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply
from studio.server.code.timeline import (caption_warnings, plan_voice_add, plan_voice_caption,
                                         plan_voice_delete, plan_voice_move, plan_voice_text)

HEAD = "from manim_kit import *\n\nclass S(TimedScene):\n    def construct(self):\n"


def scene(*lines):
    return HEAD + "".join("        " + ln + "\n" for ln in lines)


def span(code, needle, nth=0):
    tree = ast.parse(code)
    hits = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and ast.get_source_segment(code, n) == needle), key=lambda n: (n.lineno, n.col_offset))
    n = hits[nth]
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def line(code, needle, index=0, start=0.0, kind="say", requested=None):
    s = span(code, needle)
    return {"index": index, "kind": kind, "text": "", "call": s, "chain": [s], "start": start,
            "requested": start if requested is None else requested}


def ev(code, needle, start, dur, kind="play"):
    s = span(code, needle)
    return {"kind": kind, "start": start, "duration": dur, "call": s, "chain": [s]}


def run(code, plan):
    out = apply(code.encode(), plan.edits).decode()
    ast.parse(out)
    return out


# -- text -------------------------------------------------------------------------
def test_text_keeps_quote_style_and_escapes():
    code = scene("with self.say('Old words.'):", "    self.wait(1)")
    ln = line(code, "self.say('Old words.')")
    out = run(code, plan_voice_text(Source(code.encode()), "S", ln, "It's new"))
    assert "with self.say('It\\'s new'):" in out


def test_text_non_ascii_and_round_trip():
    code = scene('self.line("Привет, мир")  # hello', "self.wait(1)")
    ln = line(code, 'self.line("Привет, мир")')
    src = Source(code.encode())
    out = run(code, plan_voice_text(src, "S", ln, "Grüße"))
    assert 'self.line("Grüße")  # hello' in out
    back = run(out, plan_voice_text(Source(out.encode()), "S", line(out, 'self.line("Grüße")'), "Привет, мир"))
    assert back == code


def test_text_refuses_computed_and_unchanged():
    code = scene('words = "x"', "self.line(words)")
    with pytest.raises(EditError, match="computed"):
        plan_voice_text(Source(code.encode()), "S", line(code, "self.line(words)"), "y")
    code = scene('self.line("same")')
    with pytest.raises(EditError, match="unchanged"):
        plan_voice_text(Source(code.encode()), "S", line(code, 'self.line("same")'), "same")


def test_text_in_a_helper_is_refused():
    code = (HEAD + "        self.talk()\n\n    def talk(self):\n        self.line(\"hi\")\n")
    s_inner, s_outer = span(code, 'self.line("hi")'), span(code, "self.talk()")
    ln = {"index": 0, "kind": "say", "call": s_inner, "chain": [s_outer, s_inner], "start": 0, "requested": 0}
    with pytest.raises(EditError, match="aren't written"):
        plan_voice_text(Source(code.encode()), "S", ln, "bye")
    ln["chain"] = [s_inner]  # only the helper's call: not from construct()
    with pytest.raises(EditError, match="construct"):
        plan_voice_text(Source(code.encode()), "S", ln, "bye")


# -- caption ------------------------------------------------------------------------
def test_caption_add_change_remove_round_trip():
    code = scene('with self.say("A squared"):', "    self.wait(1)")
    src = Source(code.encode())
    ln = line(code, 'self.say("A squared")')
    one = run(code, plan_voice_caption(src, "S", ln, "a²"))
    assert 'self.say("A squared", caption="a²")' in one
    two = run(one, plan_voice_caption(Source(one.encode()), "S", line(one, 'self.say("A squared", caption="a²")'), "a^2"))
    assert 'caption="a^2"' in two
    back = run(two, plan_voice_caption(Source(two.encode()), "S",
                                       line(two, 'self.say("A squared", caption="a^2")'), None))
    assert back == code


def test_caption_equal_to_text_removes_keyword():
    code = scene('self.line("Hi", caption="Hey")')
    out = run(code, plan_voice_caption(Source(code.encode()), "S", line(code, 'self.line("Hi", caption="Hey")'), "Hi"))
    assert 'self.line("Hi")' in out


def test_caption_on_voiceover_is_subcaption():
    code = scene('with self.voiceover(text="Ninety degrees"):', "    self.wait(1)")
    ln = line(code, 'self.voiceover(text="Ninety degrees")', kind="voiceover")
    out = run(code, plan_voice_caption(Source(code.encode()), "S", ln, "90°"))
    assert 'self.voiceover(text="Ninety degrees", subcaption="90°")' in out


def test_caption_warnings():
    assert caption_warnings("x" * 71)
    assert not caption_warnings("short", 2.0)
    assert caption_warnings("a caption that takes a while to read", 0.5)


# -- move ---------------------------------------------------------------------------
def test_move_changes_the_at_before_the_line_and_removes_it_when_unneeded():
    code = scene("self.play(FadeIn(a), run_time=1)", "self.at(2)", 'self.line("Hi")')
    events = [ev(code, "self.play(FadeIn(a), run_time=1)", 0, 1), ev(code, "self.at(2)", 1, 1, "wait")]
    ln = line(code, 'self.line("Hi")', start=2.0)
    src = Source(code.encode())
    out = run(code, plan_voice_move(src, "S", ln, events, [ln], 3.5, 15, True))
    assert "self.at(3.5)" in out
    p = plan_voice_move(src, "S", ln, events, [ln], 1.0, 15, True)
    assert "self.at" not in run(code, p) and p.checks["start"] == 1.0
    with pytest.raises(EditError, match="before 1.00"):
        plan_voice_move(src, "S", ln, events, [ln], 0.5, 15, True)


def test_move_inserts_an_at_and_back_is_refused_as_no_op():
    code = scene("self.play(FadeIn(a), run_time=1)", 'with self.say("Hi"):', "    self.wait(1)")
    events = [ev(code, "self.play(FadeIn(a), run_time=1)", 0, 1), ev(code, "self.wait(1)", 1, 1, "wait")]
    ln = line(code, 'self.say("Hi")', start=1.0)
    out = run(code, plan_voice_move(Source(code.encode()), "S", ln, events, [ln], 2.25, 15, True))
    assert '        self.at(2.25)\n        with self.say("Hi"):' in out


def test_move_refused_outside_timed_scene_and_for_voiceover():
    code = scene('self.line("Hi")')
    ln = line(code, 'self.line("Hi")')
    with pytest.raises(EditError, match="TimedScene"):
        plan_voice_move(Source(code.encode()), "S", ln, [], [ln], 1, 15, False)
    with pytest.raises(EditError):
        plan_voice_move(Source(code.encode()), "S", {**ln, "kind": "voiceover"}, [], [ln], 1, 15, True)


# -- add ----------------------------------------------------------------------------
def test_add_in_a_gap_writes_at_and_line():
    code = scene("self.play(FadeIn(a), run_time=1)", "self.at(4)", "self.play(FadeOut(a), run_time=1)")
    events = [ev(code, "self.play(FadeIn(a), run_time=1)", 0, 1), ev(code, "self.at(4)", 1, 3, "wait"),
              ev(code, "self.play(FadeOut(a), run_time=1)", 4, 1)]
    p = plan_voice_add(Source(code.encode()), "S", events, 15, True, 2, "New line.")
    out = run(code, p)
    assert '        self.at(2)\n        self.line("New line.")\n        self.at(4)\n' in out
    assert p.checks == {"voice": "add", "text": "New line.", "start": 2.0}


def test_add_refused_in_sequential_scene_and_empty():
    code = scene("self.wait(1)")
    with pytest.raises(EditError, match="TimedScene"):
        plan_voice_add(Source(code.encode()), "S", [], 15, False, 0.5, "x")
    with pytest.raises(EditError, match="empty"):
        plan_voice_add(Source(code.encode()), "S", [], 15, True, 0.5, "  ")


# -- delete -------------------------------------------------------------------------
def test_delete_unwraps_the_with_block():
    code = scene("self.at(1)", 'with self.say("Hi"):  # intro', "    self.play(FadeIn(a), run_time=1)",
                 "    self.play(", "        FadeOut(a),", "    )", "self.wait(1)")
    out = run(code, plan_voice_delete(Source(code.encode()), "S", line(code, 'self.say("Hi")')))
    assert out == scene("self.at(1)", "self.play(FadeIn(a), run_time=1)", "self.play(", "    FadeOut(a),", ")",
                        "self.wait(1)")


def test_delete_bare_line_and_refuse_named_times():
    code = scene('self.line("Hi")', "self.wait(1)")
    assert run(code, plan_voice_delete(Source(code.encode()), "S", line(code, 'self.line("Hi")'))) == scene("self.wait(1)")
    code = scene('a, b = self.line("Hi")', "self.at(a + 1)")
    with pytest.raises(EditError, match="later code"):
        plan_voice_delete(Source(code.encode()), "S", line(code, 'self.line("Hi")'))


def test_delete_refuses_when_block_uses_the_length():
    code = scene('with self.say("Hi") as d:', "    self.wait(d)")
    with pytest.raises(EditError, match="length"):
        plan_voice_delete(Source(code.encode()), "S", line(code, 'self.say("Hi")'))


# -- sections --------------------------------------------------------------------------
from studio.server.code.timeline import plan_section_add, plan_section_delete, plan_section_rename  # noqa: E402


def test_section_add_rename_delete_round_trip():
    code = scene("self.play(FadeIn(a), run_time=1)", "self.at(4)", "self.play(FadeOut(a), run_time=1)")
    events = [ev(code, "self.play(FadeIn(a), run_time=1)", 0, 1), ev(code, "self.at(4)", 1, 3, "wait"),
              ev(code, "self.play(FadeOut(a), run_time=1)", 4, 1)]
    out = run(code, plan_section_add(Source(code.encode()), "S", events, 15, True, 4, "Outro"))
    assert '        self.next_section("Outro")\n        self.at(4)\n' in out or \
        '        self.at(4)\n        self.next_section("Outro")\n' in out
    s = span(out, 'self.next_section("Outro")')
    sec = {"name": "Outro", "start": 4.0, "call": s, "chain": [s]}
    renamed = run(out, plan_section_rename(Source(out.encode()), "S", sec, "The end"))
    assert 'self.next_section("The end")' in renamed
    s2 = span(renamed, 'self.next_section("The end")')
    gone = run(renamed, plan_section_delete(Source(renamed.encode()), "S", {**sec, "call": s2, "chain": [s2]}))
    assert "next_section" not in gone


def test_section_name_is_checked():
    code = scene("self.wait(1)")
    with pytest.raises(EditError, match="section name"):
        plan_section_add(Source(code.encode()), "S", [], 15, True, 0, 'x"); import os; ("')


def test_a_long_caption_continues_under_the_paren_and_comes_back_off():
    words = "Rotate, then shear. Or shear, then rotate. Same result?"
    code = scene(f'with self.say("{words}"):', "    self.wait(1)")
    src = Source(code.encode())
    out = run(code, plan_voice_caption(src, "S", line(code, f'self.say("{words}")'), "Rotate then shear, or the other way?"))
    assert f'        with self.say("{words}",\n                      caption="Rotate then shear, or the other way?"):' in out
    needle = f'self.say("{words}",\n                      caption="Rotate then shear, or the other way?")'
    back = run(out, plan_voice_caption(Source(out.encode()), "S", line(out, needle), None))
    assert back == code


def test_section_at_an_existing_at_writes_no_second_at():
    code = scene("self.play(FadeIn(a), run_time=1)", "self.at(4)", "self.play(FadeOut(a), run_time=1)")
    events = [ev(code, "self.play(FadeIn(a), run_time=1)", 0, 1), ev(code, "self.at(4)", 1, 3, "wait"),
              ev(code, "self.play(FadeOut(a), run_time=1)", 4, 1)]
    out = run(code, plan_section_add(Source(code.encode()), "S", events, 15, True, 4, "Outro"))
    assert out.count("self.at(4)") == 1
    assert '        self.at(4)\n        self.next_section("Outro")\n        self.play(FadeOut' in out


def test_line_at_an_at_whose_end_rounds_past_t_writes_no_second_at():
    code = scene("self.play(FadeIn(a), run_time=1)", "self.at(1.8)", "self.play(FadeOut(a), run_time=1)")
    events = [ev(code, "self.play(FadeIn(a), run_time=1)", 0, 1),
              ev(code, "self.at(1.8)", 1, 0.8000001, "wait"),
              ev(code, "self.play(FadeOut(a), run_time=1)", 1.8000001, 1)]
    out = run(code, plan_section_add(Source(code.encode()), "S", events, 15, True, 1.8, "B"))
    assert out.count("self.at(1.8)") == 1
    assert '        self.at(1.8)\n        self.next_section("B")\n' in out


def test_a_families_zip_crash_is_explained():
    from studio.server.project import _stop_reason
    err = {"message": "zip() argument 2 is shorter than argument 1", "line": 37,
           "traceback": "...\n  families = list(self.get_all_families_zipped())\nValueError: zip()"}
    why = _stop_reason(err)
    assert why.startswith("the edited scene stops with zip()") and "(line 37)" in why
    assert "always_redraw" in why
    assert "always_redraw" not in _stop_reason({"message": "NameError: x", "line": 3})
