"""Fixes from the review after Phase 4 (code layer and server helpers), no Manim."""

import ast

import pytest

from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply
from studio.server.code.timeline import (knock_on, plan_reorder, plan_voice_caption, plan_voice_text,
                                         set_number)
from studio.server.project import _BOOKMARK, _tts_failed

HEAD = "from manim_kit import *\n\nclass S(TimedScene):\n    def construct(self):\n"
SEQ = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n"


def scene(*lines, head=HEAD):
    return head + "".join("        " + ln + "\n" for ln in lines)


def span(code, needle):
    tree = ast.parse(code)
    n = min((n for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.get_source_segment(code, n) == needle),
            key=lambda n: (n.lineno, n.col_offset))
    return [n.lineno, n.col_offset, n.end_lineno, n.end_col_offset]


def line(code, needle):
    s = span(code, needle)
    return {"index": 0, "kind": "say", "text": "", "call": s, "chain": [s], "start": 0.0, "requested": 0.0}


def ev(code, needle, start, dur, cls):
    s = span(code, needle)
    return {"kind": "play", "start": start, "duration": dur, "call": s, "chain": [s], "anims": [{"class": cls}]}


def run(code, plan):
    out = apply(code.encode(), plan.edits).decode()
    ast.parse(out)
    return out


def _num(code, text):
    src = Source(code.encode())
    node = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Constant) and src.text(n) == text)
    return src, node


# -- #5: a whole literal keeps its own style ---------------------------------------
def test_whole_literal_keeps_its_style_against_the_file_habit():
    # the file writes at() times as 1.5 / 2.0; this one is written 3
    code = scene("self.at(1.5)", "self.at(2.0)", "self.at(3)")
    src, node = _num(code, "3")
    assert apply(code.encode(), [set_number(src, node, 4.0)]).decode().count("self.at(4)") == 1
    code = scene("self.at(1)", "self.at(2)", "self.at(3.0)")
    src, node = _num(code, "3.0")
    assert "self.at(4.0)" in apply(code.encode(), [set_number(src, node, 4.0)]).decode()


def test_annotated_target_counts_for_the_style():
    code = "from manim_kit import *\n\nclass S(TimedScene):\n    TARGET: float = 6.0\n"
    src, node = _num(code, "6.0")
    assert "TARGET: float = 7.0" in apply(code.encode(), [set_number(src, node, 7.0)]).decode()


# -- #6: a caption written as the second argument ----------------------------------
def test_positional_caption_is_changed_in_place():
    code = scene('with self.say("A squared", "a²"):', "    self.wait(1)")
    out = run(code, plan_voice_caption(Source(code.encode()), "S", line(code, 'self.say("A squared", "a²")'), "a^2"))
    assert 'self.say("A squared", "a^2")' in out and "caption=" not in out


def test_positional_caption_removal_is_refused_not_duplicated():
    code = scene('with self.say("A squared", "a²"):', "    self.wait(1)")
    with pytest.raises(EditError, match="second argument"):
        plan_voice_caption(Source(code.encode()), "S", line(code, 'self.say("A squared", "a²")'), None)


# -- #9: text that can't be written ------------------------------------------------
def test_text_with_nul_or_surrogates_is_refused():
    code = scene('self.line("Hi")')
    for bad in ("a\x00b", "a\ud800b"):
        with pytest.raises(EditError, match="can't be written"):
            plan_voice_text(Source(code.encode()), "S", line(code, 'self.line("Hi")'), bad)


def test_text_line_breaks_are_normalised():
    code = scene('self.line("Hi")')
    out = run(code, plan_voice_text(Source(code.encode()), "S", line(code, 'self.line("Hi")'), "one\r\ntwo\rthree"))
    assert 'self.line("one\\ntwo\\nthree")' in out


def test_triple_quoted_text_keeps_crlf():
    code = scene('self.line("""Hi""")').replace("\n", "\r\n")
    src = Source(code.encode())
    out = apply(code.encode(), plan_voice_text(src, "S", line(code.replace("\r\n", "\n"), 'self.line("""Hi""")'),
                                                "one\ntwo").edits)
    assert b'"""one\r\ntwo"""' in out and b"\n" not in out.replace(b"\r\n", b"")


# -- #8: scene attributes are dependencies too -------------------------------------
def test_reorder_refuses_shared_self_attributes():
    pa, pb = "self.play(Write(self.t))", "self.play(self.t.animate.shift(UP))"
    code = scene("self.t = Text('x')", pa, pb, head=SEQ)
    events = [ev(code, pa, 0, 1, "Write"), ev(code, pb, 1, 1, "_MethodAnimation")]
    with pytest.raises(EditError, match="self.t"):
        plan_reorder(Source(code.encode()), "S", events, 1, 0, False, False)


def test_reorder_ignores_scene_methods():
    pa, pb = "self.play(FadeIn(a))", "self.play(FadeIn(b))"
    code = scene(pa, pb, head=SEQ)
    events = [ev(code, pa, 0, 1, "a"), ev(code, pb, 1, 1, "b")]
    assert run(code, plan_reorder(Source(code.encode()), "S", events, 1, 0, False, False)) == scene(pb, pa, head=SEQ)


# -- #7: narration lines that move are reported ------------------------------------
def test_knock_on_reports_moved_narration():
    before = {"events": [], "duration": 5, "audio": {"lines": [{"start": 1.0}, {"start": 3.0}]}}
    after = {"events": [], "duration": 5, "audio": {"lines": [{"start": 1.0}, {"start": 3.5}]}}
    assert "1 narration line moved" in knock_on(before, after, 15)
    assert knock_on(before, before, 15) == ""


# -- server helpers ----------------------------------------------------------------
def test_tts_failure_is_not_matched_by_to_edge():
    assert not _tts_failed({"message": "AttributeError: 'Text' object has no attribute 'to_edge_x'"})
    assert _tts_failed({"message": "RuntimeError: Edge TTS failed 3 times. Are you online?"})
    assert _tts_failed({"message": "TimeoutError", "traceback": 'File "edge_tts_service.py", line 90'})


def test_bookmarks_are_stripped_from_the_shown_caption():
    text = "The <bookmark mark='a'/>green arrow lands <bookmark mark=\"b\" />here."
    assert _BOOKMARK.sub("", text) == "The green arrow lands here."


# -- /audio answers byte ranges (seeking) ------------------------------------------
class _Req:
    def __init__(self, rng=None):
        self.headers = {"Range": rng} if rng else {}


def test_audio_ranges():
    from studio.server.app import _ranged
    body = bytes(range(100))
    full = _ranged(_Req(), body, "audio/wav", {})
    assert full.status == 200 and full.body == body and full.headers["Accept-Ranges"] == "bytes"
    part = _ranged(_Req("bytes=10-19"), body, "audio/wav", {})
    assert part.status == 206 and part.body == body[10:20] and part.headers["Content-Range"] == "bytes 10-19/100"
    assert _ranged(_Req("bytes=90-"), body, "audio/wav", {}).body == body[90:]
    assert _ranged(_Req("bytes=-5"), body, "audio/wav", {}).body == body[95:]
    assert _ranged(_Req("bytes=95-500"), body, "audio/wav", {}).headers["Content-Range"] == "bytes 95-99/100"
    assert _ranged(_Req("bytes=200-"), body, "audio/wav", {}).status == 416
    assert _ranged(_Req("bytes=5-1"), body, "audio/wav", {}).status == 416
    assert _ranged(_Req("items=0-1"), body, "audio/wav", {}).status == 200
