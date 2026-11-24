"""Timeline edits beyond one clip's length (Phase 4, code_spec.md §4.4):
narration lines, moving clips and groups, overlaps, ripple, reorder,
sections and scene order. Pure code layer: no Manim.

Every plan carries `checks`: what the replayed trace must show
(`check()` below), so verification stays the same as for other edits.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .moves import block_of, function_of, remove_statement, statement_of
from .planner import _string_like
from .source import Source, Span
from .splice import Edit, EditError, fmt, number_of, set_keyword
from .splice import set_number as _set_number_styled


def _kind_of(src: Source, node) -> str:
    p = src.parent(node)
    if isinstance(p, (ast.Assign, ast.AnnAssign)):
        return "target"
    if isinstance(p, ast.keyword):
        return "length"
    return "time"


def _point_style(src: Source, kind: str) -> bool:
    """Does this file write whole values of this kind (at()/wait() times,
    run_time=/start=/length=, TARGET) as `4.0` (True) or `4` (False)?"""
    cache = src.__dict__.setdefault("_studio_point_style", {})
    if kind not in cache:
        dot = plain = 0
        for n in ast.walk(src.tree):
            vals = []
            if kind == "time" and isinstance(n, ast.Call) and Source.call_name(n) in ("at", "wait") and n.args:
                vals.append(n.args[0])
            if kind == "length" and isinstance(n, ast.keyword) and n.arg in ("run_time", "start", "length"):
                vals.append(n.value)
            if kind == "target" and isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None and                     any(isinstance(t, ast.Name) and t.id == "TARGET"
                        for t in (n.targets if isinstance(n, ast.Assign) else [n.target])):
                vals.append(n.value)
            for v in vals:
                if isinstance(v, ast.Constant) and isinstance(v.value, (int, float)) and float(v.value).is_integer():
                    if "." in src.text(v):
                        dot += 1
                    else:
                        plain += 1
        cache[kind] = dot > plain
    return cache[kind]


def set_number(src: Source, node, value: float) -> Edit:
    """A time literal. A whole literal keeps its own style (`5.0` stays
    `6.0`); a fractional one that becomes whole follows the file's habit for
    that kind of number (`4.0` or `4`), so a move there and back restores the
    bytes either way."""
    if float(value).is_integer():
        v = fmt(value)
        old = src.text(node).lstrip("+-")
        old_v = number_of(node)
        if old_v is not None and float(old_v).is_integer():
            dotted = "." in old
        else:
            dotted = _point_style(src, _kind_of(src, node))
        return Edit(*src.span(node), v + ".0" if dotted else v)
    return _set_number_styled(src, node, value)


FRAME_TOL = 1.5  # in frames: the trace snaps times to whole frames (S4)
MAX_CAPTION, READ_CPS, READ_PAD = 70, 15, 0.3


@dataclass
class Plan:
    edits: list
    note: str
    confirm: str | None = None
    checks: dict = field(default_factory=dict)


# -- shared helpers -------------------------------------------------------------
def _construct(src: Source, scene: str) -> ast.FunctionDef:
    for node in src.tree.body:
        if isinstance(node, ast.ClassDef) and node.name == scene:
            for b in node.body:
                if isinstance(b, ast.FunctionDef) and b.name == "construct":
                    return b
            raise EditError(f"{scene} has no construct() of its own")
    raise EditError(f"no class {scene} in the file")


def _is_self(call, *methods) -> bool:
    f = call.func if isinstance(call, ast.Call) else None
    return isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self" \
        and (not methods or f.attr in methods)


def _self_stmt(st, *methods) -> ast.Call | None:
    """`self.m(...)` as an expression statement -> the call."""
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and _is_self(st.value, *methods):
        return st.value
    return None


def _alone(src: Source, st) -> bool:
    """On its own lines (a trailing comment allowed)."""
    if src.before(st.lineno, st.col_offset).strip():
        return False
    rest = src.after(st.end_lineno, st.end_col_offset).strip()
    return rest == "" or rest.startswith("#")


# -- narration -------------------------------------------------------------------
def _line_call(src: Source, scene: str, line: dict) -> tuple[ast.Call, ast.stmt]:
    """The construct()-level call behind a narration line, and its statement."""
    spans = list(line.get("chain") or []) or ([line["call"]] if line.get("call") else [])
    fn = _construct(src, scene)
    for sp in spans:
        c = src.find_call(Span(*sp))
        if c is not None and function_of(src, c) is fn:
            return c, statement_of(src, c)
    raise EditError("this line isn't spoken from construct() itself; edit it in the code")


def _text_node(call: ast.Call):
    for k in call.keywords:
        if k.arg in ("text", "spoken"):
            return k.value
    return call.args[0] if call.args else None


def _caption_kw(call: ast.Call, kind: str) -> str:
    name = Source.call_name(call)
    if name == "voiceover":
        return "subcaption"
    return "caption"


def _plain_string(src: Source, node, what: str) -> str:
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        shown = src.text(node) if node is not None else "nothing"
        raise EditError(f"the {what} is computed ({shown[:60]}); change it in the code")
    return node.value


def _clean_text(text, what: str) -> str:
    if not isinstance(text, str):
        raise EditError(f"the {what} must be text")
    if "\x00" in text or any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        raise EditError(f"the {what} has characters that can't be written to the file")
    t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        raise EditError(f"the {what} is empty")
    if len(t) > 2000:
        raise EditError(f"the {what} is too long")
    return t


def caption_warnings(text: str, shown_for: float | None = None) -> list[str]:
    out = []
    if len(text) > MAX_CAPTION:
        out.append(f"the caption is {len(text)} characters (at most {MAX_CAPTION} reads well)")
    need = len(text) / READ_CPS + READ_PAD
    if shown_for is not None and shown_for + 1e-6 < need:
        out.append(f"the caption is up {shown_for:.1f} s; reading it takes {need:.1f} s")
    return out


def plan_voice_text(src: Source, scene: str, line: dict, text) -> Plan:
    text = _clean_text(text, "line")
    call, _ = _line_call(src, scene, line)
    node = _text_node(call)
    if node is None:
        raise EditError(f"the words aren't written at line {call.lineno} ({Source.call_name(call)}() makes them "
                        "inside); edit them in the code")
    old = _plain_string(src, node, "spoken text")
    if old == text:
        raise EditError("the text is unchanged")
    edits = [Edit(*src.span(node), _string_like(src, node, text))]
    note = f"line {call.lineno}: narration text changed"
    # a caption equal to the new text is now redundant: leave it (it is the user's)
    return Plan(edits, note, checks={"voice": "text", "index": line["index"], "text": text})


def plan_voice_caption(src: Source, scene: str, line: dict, caption) -> Plan:
    call, _ = _line_call(src, scene, line)
    kw = _caption_kw(call, line.get("kind", "say"))
    spoken_node = _text_node(call)
    spoken = spoken_node.value if isinstance(spoken_node, ast.Constant) and isinstance(spoken_node.value, str) else None
    cap = None if caption in (None, "") else _clean_text(caption, "caption")
    existing = Source.keyword(call, kw)
    if existing is None and kw == "caption" and len(call.args) > 1:
        # say("words", "caption"): the caption is the second argument
        pos = call.args[1]
        if cap is None or cap == spoken:
            raise EditError(f"the caption is the second argument at line {call.lineno}; remove it in the code")
        _plain_string(src, pos, "caption")
        return Plan([Edit(*src.span(pos), _string_like(src, pos, cap))], f"line {call.lineno}: caption set",
                    checks={"voice": "caption", "index": line["index"], "caption": cap})
    if cap is None or cap == spoken:
        if existing is None:
            raise EditError("the caption already shows the spoken text")
        return Plan([set_keyword(src, call, kw, None)], f"line {call.lineno}: {kw}= removed (shows the spoken text)",
                    checks={"voice": "caption", "index": line["index"], "caption": spoken})
    if existing is not None:
        _plain_string(src, existing.value, "caption")
        e = Edit(*src.span(existing.value), _string_like(src, existing.value, cap))
    else:
        like = spoken_node if isinstance(spoken_node, ast.Constant) and isinstance(spoken_node.value, str) else None
        e = set_keyword(src, call, kw, _string_like(src, like, cap) if like is not None else _string_like(src, None, cap))
    return Plan([e], f"line {call.lineno}: caption set", checks={"voice": "caption", "index": line["index"],
                                                                  "caption": cap})


def _prev_stmt(src: Source, st):
    blk = block_of(src, st)
    if blk is None:
        return None, None
    i = next(j for j, s in enumerate(blk) if s is st)
    return (blk[i - 1] if i > 0 else None), blk


def stmt_spans(src: Source, fn, events: list, lines: list | None = None) -> dict[int, tuple[float, float]]:
    """id(statement at any depth of fn) -> (start, end) of what it runs.
    Narration lines count with their start only (say() doesn't block)."""
    out: dict[int, list] = {}

    def credit(spans, a, b):
        for sp in spans:
            c = src.find_call(Span(*sp))
            if c is None or function_of(src, c) is not fn:
                continue
            st = statement_of(src, c)
            while st is not None and st is not fn:
                out.setdefault(id(st), []).append((a, b))
                st = statement_of(src, src.parent(st))
            return
    for ev in events:
        credit(list(ev.get("chain") or []) or ([ev["call"]] if ev.get("call") else []),
               ev["start"], ev["start"] + ev["duration"])
    for ln in lines or []:
        credit(list(ln.get("chain") or []) or ([ln["call"]] if ln.get("call") else []),
               ln["requested"], ln["requested"])
    return {k: (min(a for a, _ in v), max(b for _, b in v)) for k, v in out.items()}


def _ends_before(src: Source, blk: list, i: int, spans: dict, block_start: float) -> float:
    """When everything before blk[i] has finished (its at()/wait() included)."""
    return max([block_start] + [spans[id(s)][1] for s in blk[:i] if id(s) in spans])


def plan_voice_move(src: Source, scene: str, line: dict, events: list, lines: list, t: float, fps: float,
                    timed: bool) -> Plan:
    """Start a narration line at t: the at() right before its statement
    (code_spec §4.4). Only in a TimedScene: voiceover() blocks."""
    if not timed or line.get("kind") != "say":
        raise EditError("only say()/line() narration in a TimedScene can be moved; "
                        "voiceover() waits for its audio, so moving it would shift everything after it")
    t = round(float(t), 2)
    if t < 0:
        raise EditError("a line can't start before 0")
    call, st = _line_call(src, scene, line)
    fn = _construct(src, scene)
    spans = stmt_spans(src, fn, events, lines)
    prev, blk = _prev_stmt(src, st)
    i = next(j for j, s in enumerate(blk) if s is st)
    parent = src.parent(st)
    block_start = spans.get(id(parent), (0.0, 0.0))[0] if parent is not fn else 0.0
    frame = 1 / fps
    prev_at = _self_stmt(prev, "at") if prev is not None else None
    if prev_at is not None and prev_at.args and number_of(prev_at.args[0]) is not None:
        before_at = _ends_before(src, blk, i - 1, spans, block_start)
        if t < before_at - frame / 2:
            raise EditError(f"the line can't start before {before_at:.2f} s: what comes before it runs until then "
                            "(move or shorten that first)")
        old = number_of(prev_at.args[0])
        if t <= before_at + frame / 2 and _alone(src, prev) and remove_statement(src, prev) is not None:
            # the at() would do nothing: remove it (round trip of an inserted one)
            e = remove_statement(src, prev)
            return Plan([e], f"self.at({fmt(old)}) removed: the line starts at {before_at:.2f} s",
                        checks={"voice": "start", "index": line["index"], "start": before_at})
        return Plan([set_number(src, prev_at.args[0], t)], f"self.at({fmt(old)}) → self.at({fmt(t)})",
                    checks={"voice": "start", "index": line["index"], "start": t})
    before = _ends_before(src, blk, i, spans, block_start)
    if t < before - frame / 2:
        raise EditError(f"the line can't start before {before:.2f} s: the code before it runs until then "
                        "(move or shorten that first, or move the line to an earlier spot in the code)")
    if t <= before + frame / 2:
        raise EditError("the line already starts there")
    if src.before(st.lineno, st.col_offset).strip():
        raise EditError(f"line {st.lineno} holds more than one statement; split it first")
    a = src.line_starts[st.lineno - 1]
    indent = src.indent_of(st.lineno)
    return Plan([Edit(a, a, f"{indent}self.at({fmt(t)}){src.newline}")], f"self.at({fmt(t)}) added before line {st.lineno}",
                checks={"voice": "start", "index": line["index"], "start": t})


def plan_voice_add(src: Source, scene: str, events: list, fps: float, timed: bool, t: float, text) -> Plan:
    """A new line at t: `self.line("...")` where a statement starting at t
    would go (the same slot a library drop uses)."""
    from .inserts import slot, _emit
    if not timed:
        raise EditError("new narration lines need a TimedScene (absolute timing); this scene isn't one")
    text = _clean_text(text, "line")
    fn = _construct(src, scene)
    t = round(float(t), 2)
    sl = slot(src, fn, events, t, fps, True, 0.0)
    lines = []
    if sl.at_needed and t > 1 / fps:
        lines.append(f"self.at({fmt(t)})")
    lines.append(f"self.line({_string_like(src, None, text)})")
    start = t if sl.at_needed else max(sl.start, t)
    note = f"narration line added at {start:.2f} s" + (sl.note or "")
    return Plan(_emit(src, sl, lines), note, checks={"voice": "add", "text": text, "start": start})


def plan_voice_delete(src: Source, scene: str, line: dict) -> Plan:
    call, st = _line_call(src, scene, line)
    if isinstance(st, ast.Expr):  # self.line("...") / self.say(...) used bare
        e = remove_statement(src, st)
        if e is None:
            s0, s1 = src.span(st)
            e = Edit(s0, s1, "pass")
        return Plan([e], f"narration line {st.lineno} removed",
                    checks={"voice": "delete", "index": line["index"], "text": line.get("text")})
    if isinstance(st, ast.Assign):  # a, b = self.line(...): the names are used later
        raise EditError(f"line {st.lineno} keeps the line's times ({src.text(st.targets[0])}) for later code; "
                        "delete it in the code")
    if not isinstance(st, (ast.With, ast.AsyncWith)) or len(st.items) != 1:
        raise EditError(f"line {st.lineno} isn't a plain `with self.say(...)`; delete it in the code")
    body = st.body
    if body[0].lineno == st.lineno:
        raise EditError(f"the with block at line {st.lineno} is on one line; put its body on its own lines first")
    # unwrap: drop the header line(s), dedent the body by one level
    head_end = max(st.items[0].context_expr.end_lineno, (st.items[0].optional_vars or st.items[0].context_expr).end_lineno)
    if body[0].lineno <= head_end:
        raise EditError(f"the with block at line {st.lineno} is on one line; put its body on its own lines first")
    if st.items[0].optional_vars is not None:
        name = src.text(st.items[0].optional_vars)
        for n in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(n, ast.Name) and n.id == name:
                raise EditError(f"the block uses `{name}` (the line's length); delete it in the code")
    outer = src.indent_of(st.lineno)
    inner = src.indent_of(body[0].lineno)
    if not inner.startswith(outer) or inner == outer:
        raise EditError("unusual indentation in the with block")
    # lines inside a multi-line string must not be touched
    strings = [(n.lineno, n.end_lineno) for n in ast.walk(st) if isinstance(n, ast.Constant)
               and isinstance(n.value, str) and n.end_lineno > n.lineno]
    edits = [Edit(src.line_starts[st.lineno - 1], src.line_end(head_end), "")]
    cut = len(inner) - len(outer)
    for ln in range(head_end + 1, st.end_lineno + 1):
        if any(a < ln <= b for a, b in strings):
            continue
        text = src.line_text(ln)
        if not text.strip():
            continue
        if not text.startswith(outer) or text[len(outer):len(outer) + cut].strip(" 	"):
            if text.lstrip().startswith("#"):
                continue
            raise EditError(f"line {ln} is indented less than the with block's body")
        a = src.line_starts[ln - 1] + len(outer.encode())
        edits.append(Edit(a, a + cut, ""))
    return Plan(edits, f"narration at line {st.lineno} removed; its {len(body)} statement(s) stay",
                checks={"voice": "delete", "index": line["index"], "text": line.get("text")})


# -- verification -----------------------------------------------------------------
def knock_on(before: dict, after: dict, fps: float, skip=frozenset()) -> str:
    """What else moved: '; 3 later clips start 0.8 s later'. Shown with the
    edit's summary, so a move that pushes other clips never does it silently."""
    tol = FRAME_TOL / fps
    lines = ""
    v0 = [ln.get("start") for ln in ((before.get("audio") or {}).get("lines") or []) if ln.get("start") is not None]
    v1 = [ln.get("start") for ln in ((after.get("audio") or {}).get("lines") or []) if ln.get("start") is not None]
    if len(v0) == len(v1):
        nv = sum(1 for x, y in zip(v0, v1) if abs(y - x) > tol)
        if nv:
            lines = f"; {nv} narration line{'s' if nv > 1 else ''} moved"
    a = [e for e in before["events"] if e["kind"] == "play"]
    b = [e for e in after["events"] if e["kind"] == "play"]
    if len(a) != len(b):
        return ""
    moved = [y["start"] - x["start"] for i, (x, y) in enumerate(zip(a, b))
             if i not in skip and abs(y["start"] - x["start"]) > tol]
    out = lines
    if moved:
        lo, hi = min(moved), max(moved)
        amount = f"{abs(lo):.2f} s" if abs(hi - lo) <= tol else f"{min(abs(lo), abs(hi)):.2f}–{max(abs(lo), abs(hi)):.2f} s"
        out += f"; {len(moved)} clip{'s' if len(moved) > 1 else ''} now start{'' if len(moved) > 1 else 's'} " \
               f"{amount} {'later' if hi > 0 else 'earlier'}"
    d0, d1 = before.get("duration", 0), after.get("duration", 0)
    if abs(d1 - d0) > tol:
        out += f"; the scene is now {d1:.2f} s (was {d0:.2f} s)"
    return out


def check(checks: dict, before: dict, after: dict, fps: float) -> str | None:
    """What the replayed trace must show for a timeline plan. None when it does."""
    tol = FRAME_TOL / fps
    plays0 = [e for e in before["events"] if e["kind"] == "play"]
    plays1 = [e for e in after["events"] if e["kind"] == "play"]
    if "order" in checks:
        got = [list(a.get("class") for a in e["anims"]) for e in plays1]
        if got != checks["order"]:
            return "the clips play in a different order than planned after the edit"
        return None
    if "scenes" in checks:
        return None
    if "section" in checks:
        c = checks["section"]
        secs = (after.get("audio") or {}).get("sections", [])
        if not any(x["name"] == c["name"] and abs(x["start"] - c["start"]) <= tol for x in secs):
            return f"no section {c['name']!r} at {c['start']:.2f} s after the edit"
        return None
    if "section_gone" in checks:
        n0 = sum(1 for x in (before.get("audio") or {}).get("sections", []) if x["name"] == checks["section_gone"])
        n1 = sum(1 for x in (after.get("audio") or {}).get("sections", []) if x["name"] == checks["section_gone"])
        return None if n1 == n0 - 1 else "the section is still there after the edit"
    if "merged" in checks:
        c = checks["merged"]
        if len(plays1) != len(plays0) + c["plays"] or c["play"] >= len(plays1):
            return "the groups weren't joined as planned"
        anims = plays1[c["play"]]["anims"]
        if len(anims) != c["first"] + len(c["offsets"]):
            return "the joined group doesn't hold the moved clip"
        for k, o in enumerate(c["offsets"]):
            if abs(anims[c["first"] + k].get("offset", 0.0) - o) > tol:
                return f"the moved clip starts {anims[c['first'] + k].get('offset', 0):.2f} s into the group, not {o:.2f} s"
        return None
    if "split" in checks:
        c = checks["split"]
        if len(plays1) != len(plays0) + 1 or c["play"] >= len(plays1):
            return "the clip didn't get its own play()"
        if abs(plays1[c["play"]]["start"] - c["start"]) > tol:
            return f"the clip starts at {plays1[c['play']]['start']:.2f} s after the edit, not {c['start']:.2f} s"
        return None
    if "anim_start" in checks:
        c = checks["anim_start"]
        plays = [e for e in after["events"] if e["kind"] == "play"]
        if c["play"] >= len(plays) or c["anim"] >= len(plays[c["play"]]["anims"]):
            return "the clip isn't in the same play() after the edit"
        got = plays[c["play"]]["anims"][c["anim"]].get("offset", 0.0)
        if abs(got - c["start"]) > tol:
            return f"the clip starts {got:.2f} s into its group after the edit, not {c['start']:.2f} s"
        return None
    if "starts" in checks:
        plays = [e for e in after["events"] if e["kind"] == "play"]
        for p, want in checks["starts"]["plays"].items():
            p = int(p)
            if p >= len(plays):
                return "the edited scene has fewer clips than before"
            if abs(plays[p]["start"] - want) > tol:
                return f"the clip starts at {plays[p]['start']:.2f} s after the edit, not {want:.2f} s"
        new = (after.get("audio") or {}).get("lines", [])
        for v, want in checks["starts"]["lines"].items():
            v = int(v)
            if v >= len(new):
                return "the edited scene has fewer narration lines than before"
            if abs(new[v]["start"] - want) > tol:
                return (f"the line starts at {new[v]['start']:.2f} s after the edit, not {want:.2f} s "
                        "(a line never starts before the one ahead of it has finished)")
        return None
    if "voice" in checks:
        old = (before.get("audio") or {}).get("lines", [])
        new = (after.get("audio") or {}).get("lines", [])
        v = checks["voice"]
        if v == "add":
            hit = [ln for ln in new if ln["text"] == checks["text"]]
            if not hit:
                return "the new line isn't spoken after the edit"
            if abs(hit[-1]["start"] - checks["start"]) > tol:
                return f"the new line starts at {hit[-1]['start']:.2f} s, not {checks['start']:.2f} s"
            return None
        if v == "delete":
            if len(new) != len(old) - 1:
                return "the line is still spoken after the edit"
            return None
        i = checks["index"]
        if len(new) != len(old) or i >= len(new):
            return "the edited scene has a different number of narration lines"
        ln = new[i]
        if v == "text" and ln["text"] != checks["text"]:
            return "the line speaks something else after the edit"
        if v == "caption":
            shown = ln.get("caption") or ln["text"]
            want = checks["caption"] if checks["caption"] is not None else ln["text"]
            if shown != want:
                return "the caption shows something else after the edit"
        if v == "start" and abs(ln["start"] - checks["start"]) > tol:
            return (f"the line starts at {ln['start']:.2f} s after the edit, not {checks['start']:.2f} s "
                    "(a line never starts before the one ahead of it has finished)")
        return None
    return None


# -- clips inside one play(): clip(anim, start=, length=) -----------------------------
def clip_parts(expr):
    """`clip(x, start=s, length=l)` -> (x, s node, l node, the clip call);
    anything else -> (expr, None, None, None)."""
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "clip":
        inner = expr.args[0] if expr.args else next((k.value for k in expr.keywords if k.arg == "anim"), None)
        start = Source.keyword(expr, "start")
        length = Source.keyword(expr, "length")
        s = start.value if start is not None else (expr.args[1] if len(expr.args) > 1 else None)
        ln = length.value if length is not None else (expr.args[2] if len(expr.args) > 2 else None)
        return inner, s, ln, expr
    return expr, None, None, None


def _play_args(src: Source, call: ast.Call, n_anims: int) -> list:
    if any(isinstance(a, ast.Starred) for a in call.args) or len(call.args) != n_anims:
        raise EditError(f"the play() at line {call.lineno} builds its animations in a way the timeline "
                        "can't match one to one (a *list); edit it in the code")
    return list(call.args)


def _refuse_computed(cc):
    raise EditError(f"the clip() at line {cc.lineno} has a computed length; change it in the code")


def _runtime_edits(src: Source, expr, value: float) -> list:
    """Edits that give one play() argument its own run_time (used when a
    play()'s run_time= is spread onto its animations)."""
    from .planner import _anim_call, _animate_attr, _animate_call
    v = fmt(value)
    inner, sn, ln, cc = clip_parts(expr)
    if cc is not None:
        # under play(run_time=R) Manim stretches the whole clip() to R, start
        # included: there is no faithful length= to write for it
        if sn is not None and not (number_of(sn) == 0.0):
            raise EditError(f"the clip() at line {cc.lineno} is stretched by the play()'s run_time; "
                            "give it its own length in the code first")
        if ln is not None:
            return [] if number_of(ln) is not None and abs(number_of(ln) - value) < 1e-9                 else [set_number(src, ln, value)] if number_of(ln) is not None else _refuse_computed(cc)
        return [set_keyword(src, cc, "length", v)]
    c = _anim_call(expr)
    if c is not None:
        k = Source.keyword(c, "run_time")
        if k is None:
            return [set_keyword(src, c, "run_time", v)]
        if number_of(k.value) is not None and abs(number_of(k.value) - value) > 1e-9:
            return [set_number(src, k.value, value)]
        return []
    ac = _animate_call(expr)
    if ac is not None:
        k = Source.keyword(ac, "run_time")
        if k is None:
            return [set_keyword(src, ac, "run_time", v)]
        if number_of(k.value) is not None and abs(number_of(k.value) - value) > 1e-9:
            return [set_number(src, k.value, value)]
        return []
    b = _animate_attr(expr)
    if b is not None:
        _, end = src.span(b)
        return [Edit(end, end, f"(run_time={v})")]
    raise EditError(f"can't give {src.text(expr)[:40]} its own run_time")


def _kit_import(src: Source) -> list:
    from .inserts import import_edit, star_imports
    if "manim_kit" in star_imports(src) or any(
            isinstance(n, ast.ImportFrom) and n.module == "manim_kit" and any(a.name == "clip" for a in n.names)
            for n in src.tree.body):
        return []
    e = import_edit(src, "manim_kit")
    return [e] if e is not None else []


def plan_anim_offset(src: Source, clip: dict, anim: int, start: float, fps: float) -> Plan:
    """Move one animation inside its play(): `clip(x, start=s)` (S4)."""
    if clip.get("lock"):
        raise EditError(clip["lock"])
    call = src.find_call(Span(*clip["call"]))
    if call is None or Source.call_name(call) != "play":
        raise EditError("can't find this clip's play() call")
    args = _play_args(src, call, len(clip["anims"]))
    if not 0 <= anim < len(args):
        raise EditError("that animation no longer exists")
    start = round(float(start), 2)
    if start < -1e-9:
        raise EditError("a clip can't start before its group; move the whole group earlier instead")
    if start < 0.5 / fps:
        start = 0.0
    expr = args[anim]
    inner, s_node, l_node, cc = clip_parts(expr)
    old = number_of(s_node) if s_node is not None else 0.0
    if s_node is not None and old is None:
        raise EditError(f"the clip's start is computed ({src.text(s_node)}); change it in the code")
    if abs((old or 0.0) - start) < 0.5 / fps:
        raise EditError("the clip already starts there")
    for k in call.keywords:
        if k.arg not in ("run_time", None):
            # play(rate_func=...) is set on the clip()'s Succession too, and
            # warps its wait: the start would not be where you put it
            raise EditError(f"the play() at line {call.lineno} sets {k.arg}= for all its animations; "
                            "give each animation its own in the code first")
    edits = []
    play_rt = Source.keyword(call, "run_time")
    rt = None
    if play_rt is not None:
        rt = number_of(play_rt.value)
        if rt is None:
            raise EditError(f"play() sets a computed run_time for all its animations (line {call.lineno})")
    if cc is None:
        extra = f", length={fmt(rt)}" if rt is not None else ""
        edits.append(Edit(*src.span(expr), f"clip({src.text(expr)}, start={fmt(start)}{extra})"))
        note = f"line {expr.lineno}: clip(..., start={fmt(start)})"
    elif start == 0.0 and l_node is None and rt is None and len(cc.args) + len(cc.keywords) <= 2:
        edits.append(Edit(*src.span(cc), src.text(inner)))  # back to the plain animation
        note = f"line {cc.lineno}: clip() removed (starts with its group)"
    elif start == 0.0:
        kw = Source.keyword(cc, "start")
        edits.append(set_keyword(src, cc, "start", None) if kw is not None else set_number(src, s_node, 0))
        note = f"line {cc.lineno}: start removed"
    else:
        edits.append(set_number(src, s_node, start) if s_node is not None
                     else set_keyword(src, cc, "start", fmt(start)))
        note = f"line {cc.lineno}: start={fmt(start)}"
    if rt is not None:
        # play(run_time=) would stretch every clip: give each its own instead (S4)
        edits.append(set_keyword(src, call, "run_time", None))
        for j, a in enumerate(args):
            if j != anim or cc is not None:
                edits += _runtime_edits(src, a, rt)
        note += f"; run_time={fmt(rt)} moved from play() onto each animation"
    if cc is None:
        edits += _kit_import(src)
    return Plan(edits, note, checks={"anim_start": {"play": clip["play_index"], "anim": anim, "start": start}})


# -- moving groups (whole statements) in time -------------------------------------------
def _construct_stmt(src: Source, fn, spans_: list):
    for sp in spans_:
        c = src.find_call(Span(*sp))
        if c is not None and function_of(src, c) is fn:
            return statement_of(src, c)
    return None


def _all_stmts(body):
    for st in body:
        yield st
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for name in ("body", "orelse", "finalbody"):
            sub = getattr(st, name, None)
            if isinstance(sub, list):
                yield from _all_stmts(sub)


def _target_node(src: Source, scene: str):
    for node in src.tree.body:
        if isinstance(node, ast.ClassDef) and node.name == scene:
            for b in node.body:
                if isinstance(b, (ast.Assign, ast.AnnAssign)):
                    tgt = b.targets[0] if isinstance(b, ast.Assign) and len(b.targets) == 1 else getattr(b, "target", None)
                    if isinstance(tgt, ast.Name) and tgt.id == "TARGET" and b.value is not None \
                            and number_of(b.value) is not None:
                        return b.value
    return None


def plan_shift(src: Source, scene: str, events: list, lines: list, plays: list, voices: list,
               dt: float, fps: float, timed: bool, ripple: bool) -> Plan:
    """Move whole groups (play() statements, narration lines, helper calls)
    by dt seconds: the at() / wait() before each (code_spec §4.4). With
    ripple, every later at() moves too (and a literal TARGET)."""
    dt = round(float(dt), 2)
    frame = 1 / fps
    if abs(dt) < frame / 2:
        raise EditError("that's less than a frame")
    fn = _construct(src, scene)
    play_events = [e for e in events if e["kind"] == "play"]
    chosen = []  # (statement, start, what)
    for p in plays:
        if not isinstance(p, int) or not 0 <= p < len(play_events):
            raise EditError("that clip no longer exists")
        ev = play_events[p]
        st = _construct_stmt(src, fn, list(ev.get("chain") or []) or [ev["call"]])
        if st is None:
            raise EditError(f"the play() at line {ev.get('call_line')} isn't run from construct()")
        chosen.append((st, ev["start"], f"line {st.lineno}"))
    for v in voices:
        if not isinstance(v, int) or not 0 <= v < len(lines):
            raise EditError("that narration line no longer exists")
        ln = lines[v]
        if ln.get("kind") != "say":
            raise EditError("voiceover() lines wait for their audio; they can't be moved on the timeline")
        _, st = _line_call(src, scene, ln)
        chosen.append((st, ln["requested"], f"line {st.lineno}"))
    if not chosen:
        raise EditError("nothing selected to move")
    seen, items = set(), []
    for st, t0, what in sorted(chosen, key=lambda c: (c[0].lineno, c[0].col_offset, c[1])):
        if id(st) not in seen:  # one statement per group; the earliest start wins
            seen.add(id(st))
            items.append((st, t0, what))
    def inside_chosen(st):
        p = src.parent(st)
        while p is not None and p is not fn:
            if id(p) in seen:
                return True
            p = src.parent(p)
        return False
    items = [it for it in items if not inside_chosen(it[0])]  # moves with the block around it
    spans = stmt_spans(src, fn, events, lines)
    edits, notes, edited = [], [], set()
    if not timed:
        items = items[:1]  # a sequential scene: everything after the first moves with it
    for st, t0, what in items:
        prev, blk = _prev_stmt(src, st)
        i = next(j for j, s in enumerate(blk) if s is st)
        parent = src.parent(st)
        block_start = spans.get(id(parent), (0.0, 0.0))[0] if parent is not fn else 0.0
        if prev is not None and id(prev) in seen:
            continue  # follows a moved group directly: it moves with it
        at = _self_stmt(prev, "at") if (timed and prev is not None) else None
        wait = _self_stmt(prev, "wait") if prev is not None else None
        if at is not None and at.args and number_of(at.args[0]) is not None:
            old = number_of(at.args[0])
            before = _ends_before(src, blk, i - 1, spans, block_start)
            # an at() already in the past waits for nothing: the group really
            # starts when the code before it ends, so move from there
            new = round(max(old, before) + dt, 2)
            if new < before - frame / 2:
                raise EditError(f"{what} can't start before {before:.2f} s: the code before it runs until then")
            if new <= before + frame / 2 and _alone(src, prev) and remove_statement(src, prev) is not None:
                edits.append(remove_statement(src, prev))
                notes.append(f"self.at({fmt(old)}) removed")
            else:
                edits.append(set_number(src, at.args[0], new))
                notes.append(f"self.at({fmt(old)}) → self.at({fmt(new)})")
            edited.add(id(prev))
            continue
        if wait is not None and len(wait.args) == 1 and not wait.keywords and number_of(wait.args[0]) is not None:
            old = number_of(wait.args[0])
            new = round(old + dt, 2)
            if new < -frame / 2:
                raise EditError(f"{what} can't move {abs(dt):.2f} s earlier: the pause before it is only {fmt(old)} s")
            if new < frame / 2:
                e = remove_statement(src, prev)
                if e is None:
                    raise EditError(f"the wait at line {prev.lineno} would become 0; remove it in the code")
                edits.append(e)
                notes.append(f"self.wait({fmt(old)}) removed")
            else:
                edits.append(set_number(src, wait.args[0], new))
                notes.append(f"self.wait({fmt(old)}) → self.wait({fmt(new)})")
            edited.add(id(prev))
            continue
        if dt < 0:
            raise EditError(f"{what} starts as soon as the code before it ends; move or shorten that first")
        if src.before(st.lineno, st.col_offset).strip():
            raise EditError(f"line {st.lineno} holds more than one statement; split it first")
        a = src.line_starts[st.lineno - 1]
        ind = src.indent_of(st.lineno)
        stmt = f"self.at({fmt(round(t0 + dt, 2))})" if timed else f"self.wait({fmt(dt)})"
        edits.append(Edit(a, a, f"{ind}{stmt}{src.newline}"))
        notes.append(f"{stmt} added before line {st.lineno}")
    if timed and ripple:
        last = max(items, key=lambda c: (c[0].end_lineno, c[0].end_col_offset))[0]
        moved = {id(it[0]) for it in items}

        def in_moved(st):   # inside a moved `with self.say(...):` block
            q = src.parent(st)
            while q is not None and q is not fn:
                if id(q) in moved:
                    return True
                q = src.parent(q)
            return False
        n = 0
        for st in _all_stmts(fn.body):
            after = (st.lineno, st.col_offset) > (last.end_lineno, last.end_col_offset)
            if not (after or in_moved(st)) or id(st) in edited:
                continue
            c = _self_stmt(st, "at")
            if c is not None and c.args and number_of(c.args[0]) is not None:
                v = number_of(c.args[0])
                if v + dt < 0:
                    raise EditError(f"the at({fmt(v)}) at line {st.lineno} would go below 0")
                edits.append(set_number(src, c.args[0], round(v + dt, 2)))
                n += 1
        tgt = _target_node(src, scene)
        if tgt is not None:
            v = number_of(tgt)
            edits.append(set_number(src, tgt, round(v + dt, 2)))
            notes.append(f"TARGET {fmt(v)} → {fmt(round(v + dt, 2))}")
        if n:
            notes.append(f"ripple: {n} later at() moved by {fmt(dt)} s")
    elif not timed and not ripple:
        last = items[-1][0]
        blk = block_of(src, last)
        j = next(k for k, s in enumerate(blk) if s is last)
        nxt = blk[j + 1] if j + 1 < len(blk) else None
        w = _self_stmt(nxt, "wait") if nxt is not None else None
        if w is not None and len(w.args) == 1 and not w.keywords and number_of(w.args[0]) is not None:
            old = number_of(w.args[0])
            if old - dt >= frame / 2:
                edits.append(set_number(src, w.args[0], round(old - dt, 2)))
                notes.append(f"self.wait({fmt(old)}) after it → {fmt(round(old - dt, 2))}")
    starts = {"plays": {p: round(play_events[p]["start"] + dt, 4) for p in plays},
              "lines": {v: round(lines[v]["requested"] + dt, 4) for v in voices}}
    return Plan(edits, "; ".join(notes) or "moved", checks={"starts": starts, "dt": dt})


# -- overlapping groups: merge two play()s, or split a clip out ------------------------
def _play_stmt(src: Source, fn, clip: dict) -> tuple[ast.Call, ast.stmt]:
    if clip.get("lock"):
        raise EditError(clip["lock"])
    call = src.find_call(Span(*clip["call"])) if clip.get("call") else None
    if call is None or Source.call_name(call) != "play" or not _is_self(call):
        raise EditError("can't find this clip's self.play() call")
    st = statement_of(src, call)
    if not (isinstance(st, ast.Expr) and st.value is call) or function_of(src, call) is not fn:
        raise EditError(f"the play() at line {call.lineno} isn't a plain statement in construct()")
    return call, st


def _timing_only(st) -> bool:
    return _self_stmt(st, "at", "wait") is not None or isinstance(st, ast.Pass)


def _arg_text(src: Source, expr, start: float, length: str | None) -> str:
    inner = src.text(expr)
    if start < 1e-9 and length is None:
        return inner
    parts = [inner]
    if start >= 1e-9:
        parts.append(f"start={fmt(start)}")
    if length is not None:
        parts.append(f"length={length}")
    return f"clip({', '.join(parts)})"


def _append_args(src: Source, call: ast.Call, texts: list[str]) -> Edit:
    """New positional arguments after the last one, in the call's own layout."""
    if not call.args:
        raise EditError("the play() has no animations to join")
    last = call.args[-1]
    _, at = src.span(last)
    args = list(call.args) + list(call.keywords)
    one_per_line = len({a.lineno for a in args}) == len(args) and all(a.lineno > call.lineno for a in args)
    if one_per_line:
        ind = src.indent_of(last.lineno)
        return Edit(at, at, "".join(f",{src.newline}{ind}{t}" for t in texts))
    return Edit(at, at, "".join(f", {t}" for t in texts))


def plan_merge(src: Source, scene: str, moving: dict, anim, into: dict, start: float, fps: float) -> Plan:
    """Overlap clips from two groups (code_spec §4.4): the later play()'s
    animation(s) join the earlier one as `clip(x, start=s)`."""
    fn = _construct(src, scene)
    p2, st2 = _play_stmt(src, fn, moving)
    p1, st1 = _play_stmt(src, fn, into)
    blk = block_of(src, st1)
    if blk is None or not any(s is st2 for s in blk):
        raise EditError("the two groups are in different blocks of code; join them in the code")
    i1 = next(j for j, s in enumerate(blk) if s is st1)
    i2 = next(j for j, s in enumerate(blk) if s is st2)
    if i2 <= i1:
        raise EditError("drag a clip onto an earlier group to overlap them")
    if not all(_timing_only(s) for s in blk[i1 + 1:i2]):
        raise EditError(f"there is other code between line {st1.lineno} and line {st2.lineno}; "
                        "move the clip in the code, or move the groups together first")
    start = round(float(start), 2)
    if start < -1e-9:
        raise EditError("a clip can't start before its group; move the group earlier first")
    args2 = _play_args(src, p2, len(moving["anims"]))
    for p_, verb in ((p2, "it can't be split up from the timeline"),
                     (p1, "the clip would take that on")):
        for k in p_.keywords:
            if k.arg != "run_time":
                raise EditError(f"the play() at line {p_.lineno} sets {k.arg}= for all its animations; {verb}")
    rt2 = Source.keyword(p2, "run_time")
    if rt2 is not None and number_of(rt2.value) is None:
        raise EditError(f"the play() at line {p2.lineno} has a computed run_time")
    picked = list(range(len(args2))) if anim is None else [anim]
    if any(not 0 <= j < len(args2) for j in picked):
        raise EditError("that animation no longer exists")
    texts, offsets = [], []
    for j in picked:
        inner, s_node, l_node, cc = clip_parts(args2[j])
        base = number_of(s_node) if s_node is not None else 0.0
        if base is None:
            raise EditError(f"the clip's start is computed ({src.text(s_node)})")
        length = src.text(l_node) if l_node is not None else (src.text(rt2.value) if rt2 is not None else None)
        o = round(start + base, 2)
        texts.append(_arg_text(src, inner, o, length))
        offsets.append(o)
    args1 = _play_args(src, p1, len(into["anims"]))
    edits = [_append_args(src, p1, texts)]
    rt1 = Source.keyword(p1, "run_time")
    if rt1 is not None:
        r = number_of(rt1.value)
        if r is None:
            raise EditError(f"the play() at line {p1.lineno} has a computed run_time")
        edits.append(set_keyword(src, p1, "run_time", None))
        for a in args1:
            edits += _runtime_edits(src, a, r)
    if len(picked) == len(args2):
        e = remove_statement(src, st2)
        if e is None:
            raise EditError(f"line {st2.lineno} shares its line with other code; split it first")
        edits.append(e)
        gone = True
    else:
        from .splice import _remove_argument
        edits.append(_remove_argument(src, p2, args2[picked[0]]))
        gone = False
    if any("clip(" in t for t in texts):
        edits += _kit_import(src)
    n1 = len(args1)
    note = (f"line {st2.lineno} joined the play() at line {st1.lineno}" if gone else
            f"{src.text(args2[picked[0]])[:40]} moved into the play() at line {st1.lineno}")
    return Plan(edits, note + f", starting {fmt(start)} s into it",
                checks={"merged": {"play": into["play_index"], "first": n1, "offsets": offsets,
                                   "plays": -1 if gone else 0}})


def plan_split(src: Source, scene: str, clip: dict, anim: int, t: float, events: list, fps: float,
               timed: bool) -> Plan:
    """Pull one animation out of its group: its own play() right after it
    (code_spec §4.4), with an at() in a TimedScene when it starts later."""
    fn = _construct(src, scene)
    p1, st1 = _play_stmt(src, fn, clip)
    args = _play_args(src, p1, len(clip["anims"]))
    if len(args) < 2:
        raise EditError("this group has only one clip; move the group instead")
    if not 0 <= anim < len(args):
        raise EditError("that animation no longer exists")
    for k in p1.keywords:
        if k.arg not in ("run_time",):
            raise EditError(f"the play() at line {p1.lineno} sets {k.arg}= for all its animations")
    rt = Source.keyword(p1, "run_time")
    inner, s_node, l_node, cc = clip_parts(args[anim])
    length = src.text(l_node) if l_node is not None else (src.text(rt.value) if rt is not None else None)
    t = round(float(t), 2)
    frame = 1 / fps
    # the group ends earlier without it (but at least as late as its other clips)
    a0 = clip["start"]
    ends = []
    for j, a in enumerate(args):
        if j == anim:
            continue
        info = clip["anims"][j] if j < len(clip["anims"]) else {}
        ends.append(a0 + float(info.get("offset", 0) or 0) + float(info.get("run_time", 0) or 0))
    group_end = max(ends) if ends else a0
    if t < group_end - frame / 2:
        raise EditError(f"the group runs until {group_end:.2f} s; drop the clip after that, "
                        "or move it inside the group instead")
    from .splice import _remove_argument
    edits = [_remove_argument(src, p1, args[anim])]
    ind = src.indent_of(st1.lineno)
    nl = src.newline
    lines = []
    if t > group_end + frame / 2:
        lines.append(f"self.at({fmt(t)})" if timed else f"self.wait({fmt(round(t - group_end, 2))})")
    play = f"self.play({src.text(inner)}" + (f", run_time={length}" if length is not None else "") + ")"
    lines.append(play)
    end = src.line_end(st1.end_lineno)
    edits.append(Edit(end, end, (nl if src.data[end - 1:end] != b"\n" else "") +
                      "".join(f"{ind}{ln}{nl}" for ln in lines)))
    if not timed:
        note_more = "; later clips start later by its length"
    else:
        note_more = ""
    return Plan(edits, f"{src.text(inner)[:40]} has its own play() after line {st1.lineno}" + note_more,
                checks={"split": {"play": clip["play_index"] + 1, "start": max(t, group_end)}})


# -- reorder (code_spec §4.4): whole statements, one block -----------------------------
def _names(node) -> tuple[set, set]:
    """(names assigned, names read) anywhere in a statement."""
    out_w, out_r = set(), set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            (out_w if isinstance(n.ctx, (ast.Store, ast.Del)) else out_r).add(n.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self":
            # scene state: self.grid = ... then self.play(self.grid...) depend
            (out_w if isinstance(n.ctx, (ast.Store, ast.Del)) else out_r).add("self." + n.attr)
    return out_w, out_r


# self.X reads that are the scene's own methods, not state
_SCENE_METHODS = {"self." + m for m in ("play", "wait", "add", "remove", "at", "say", "line", "voiceover",
                                        "bring_to_front", "bring_to_back", "add_sound", "next_section",
                                        "add_subcaption", "wait_until_bookmark", "camera", "renderer",
                                        "mobjects", "time", "add_fixed_in_frame_mobjects", "fade_all",
                                        "set_camera_orientation", "move_camera", "begin_ambient_camera_rotation",
                                        "stop_ambient_camera_rotation")}


def _file_names(src: Source) -> set:
    """Names the file binds itself (variables, helpers, classes), at any level."""
    out = set()
    for n in ast.walk(src.tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
    return out


def _whole_lines(src: Source, st) -> tuple[int, int]:
    return src.line_starts[st.lineno - 1], src.line_end(st.end_lineno)


def _stmt_for_play(src: Source, fn, events: list, p: int):
    plays = [e for e in events if e["kind"] == "play"]
    if not isinstance(p, int) or not 0 <= p < len(plays):
        raise EditError("that clip no longer exists")
    st = _construct_stmt(src, fn, list(plays[p].get("chain") or []) or [plays[p]["call"]])
    if st is None:
        raise EditError("this clip isn't run from construct()")
    return st


def plan_reorder(src: Source, scene: str, events: list, play: int, target: int, after: bool, timed: bool) -> Plan:
    """Put the group behind `play` before (or after) the group behind
    `target`. In a TimedScene the at() anchors stay put and the two groups
    trade places (and times); in a sequential scene the statement moves."""
    fn = _construct(src, scene)
    s = _stmt_for_play(src, fn, events, play)
    t = _stmt_for_play(src, fn, events, target)
    if s is t:
        raise EditError("that's the same group")
    blk = block_of(src, s)
    if blk is None or not any(x is t for x in blk):
        # a play inside a with block: try the with statement itself
        raise EditError("the two clips are in different blocks of code (one is inside a with/for block); "
                        "reorder them in the code")
    i, j = (next(k for k, x in enumerate(blk) if x is s), next(k for k, x in enumerate(blk) if x is t))
    for st in (s, t):
        if not _alone(src, st):
            raise EditError(f"line {st.lineno} shares its line with other code; split it first")
    own = _file_names(src) - {"self"}
    if timed:
        lo, hi = sorted((i, j))
        between = blk[lo:hi + 1]
        moved = [s, t]
    else:
        lo, hi = (i, j) if i < j else (j, i)
        between = blk[lo:hi + 1]
        moved = [s]
    # dependency check: the moved statement(s) and everything they pass
    for m in moved:
        mw, mr = _names(m)
        for x in between:
            if x is m:
                continue
            xw, xr = _names(x)
            shared = {n for n in (mw & (xr | xw)) | (xw & mr) | (mr & xr)
                      if n in own or (n.startswith("self.") and n not in _SCENE_METHODS)}
            if shared:
                raise EditError(f"line {m.lineno} and line {x.lineno} both use {', '.join(sorted(shared))}; "
                                "reordering them would change what the scene does")
    plays = [e for e in events if e["kind"] == "play"]
    sig = [tuple(a.get("class") for a in e["anims"]) for e in plays]
    spans = {id(st): [k for k, e in enumerate(plays)
                      if _construct_stmt(src, fn, list(e.get("chain") or []) or [e["call"]]) is st] for st in blk}
    order = [st for st in blk]
    if timed:
        order[i], order[j] = order[j], order[i]
        a0, a1 = _whole_lines(src, s)
        b0, b1 = _whole_lines(src, t)
        ts, tt = src.data[a0:a1].decode("utf-8"), src.data[b0:b1].decode("utf-8")
        edits = [Edit(a0, a1, tt), Edit(b0, b1, ts)]
        note = f"line {s.lineno} and line {t.lineno} traded places (the at() times stay)"
    else:
        order.pop(i)
        k = order.index(t) + (1 if after else 0)
        order.insert(k, s)
        a0, a1 = _whole_lines(src, s)
        text = src.data[a0:a1].decode("utf-8")
        if not text.endswith("\n"):
            text += src.newline
        b0, b1 = _whole_lines(src, t)
        at = b1 if after else b0
        if at == a0 or at == a1:
            raise EditError("the clip is already there")
        edits = [Edit(a0, a1, ""), Edit(at, at, text)]
        note = f"line {s.lineno} moved {'after' if after else 'before'} line {t.lineno}"
    in_blk = sorted(k for st in blk for k in spans.get(id(st), []))
    new_seq = [k for st in order for k in spans.get(id(st), [])]
    expect_idx = list(range(len(plays)))
    for pos, k in zip(in_blk, new_seq):
        expect_idx[pos] = k
    return Plan(edits, note, checks={"order": [list(sig[k]) for k in expect_idx]})


# -- scene order: the module's SCENES list ----------------------------------------------
def _scenes_list(src: Source):
    for node in src.tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "SCENES" and isinstance(node.value, (ast.List, ast.Tuple)):
            return node
    return None


def plan_scene_order(src: Source, order: list, defined: list) -> Plan:
    """Reorder the module's `SCENES = [...]` (the render / concat order) by
    swapping its strings in place, layout kept. Without one, a SCENES list is
    added at the end of the file. The docstring's "Render order: ..." line
    follows when it lists the same scenes."""
    if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
        raise EditError("not a list of scene names")
    node = _scenes_list(src)
    nl = src.newline
    if node is None:
        if sorted(order) != sorted(defined):
            raise EditError("the new order must name every scene once")
        if order == defined:
            raise EditError("the scenes are already in that order")
        text = "SCENES = [" + ", ".join(_string_like(src, None, n) for n in order) + "]" + nl
        end = len(src.data)
        # two blank lines after the last class (PEP 8), counting the ones already there
        trailing = len(src.data) - len(src.data.rstrip(b"\r\n"))
        newlines = src.data[end - trailing:].count(b"\n")
        lead = nl * max(0, 3 - newlines)
        return Plan([Edit(end, end, lead + text)], "SCENES list added at the end of the file",
                    checks={"scenes": order})
    elts = node.value.elts
    if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts):
        raise EditError(f"SCENES (line {node.lineno}) isn't a plain list of names; reorder it in the code")
    cur = [e.value for e in elts]
    if sorted(cur) != sorted(order):
        raise EditError("the new order must name the same scenes as SCENES")
    if cur == order:
        raise EditError("the scenes are already in that order")
    texts = {e.value: src.text(e) for e in elts}
    edits = [Edit(*src.span(e), texts[name]) for e, name in zip(elts, order) if e.value != name]
    note = "SCENES reordered: " + ", ".join(order)
    doc = ast.get_docstring(src.tree, clean=False)
    if doc and isinstance(src.tree.body[0], ast.Expr):
        # the same names in the docstring, perhaps wrapped over lines: each
        # name is swapped in place, the commas and line breaks stay
        d0, d1 = src.span(src.tree.body[0])
        text = src.data[d0:d1].decode("utf-8")
        pat = re.compile(r",\s+".join(r"\b(" + re.escape(n) + r")\b" for n in cur))
        found = list(pat.finditer(text))
        if len(found) == 1:
            m = found[0]
            for g, name in enumerate(order, 1):
                if cur[g - 1] != name:
                    a = d0 + len(text[:m.start(g)].encode("utf-8"))
                    edits.append(Edit(a, a + len(cur[g - 1].encode("utf-8")), name))
            note += " (and the docstring's render order)"
    return Plan(edits, note, checks={"scenes": order})


# -- sections: Manim's own self.next_section("name") ------------------------------------
SECTION_NAME = re.compile(r"[\w .,:;!?()'-]{1,60}")


def _section_name(name) -> str:
    n = str(name or "").strip()
    if not SECTION_NAME.fullmatch(n):
        raise EditError("a section name is 1-60 letters, digits, spaces or simple punctuation")
    return n


def _section_call(src: Source, scene: str, sec: dict) -> tuple[ast.Call, ast.stmt]:
    fn = _construct(src, scene)
    for sp in list(sec.get("chain") or []) or ([sec["call"]] if sec.get("call") else []):
        c = src.find_call(Span(*sp))
        if c is not None and function_of(src, c) is fn:
            return c, statement_of(src, c)
    raise EditError("this section starts inside a helper; edit it in the code")


def plan_section_add(src: Source, scene: str, events: list, fps: float, timed: bool, t: float, name) -> Plan:
    from .inserts import _emit, slot
    name = _section_name(name)
    fn = _construct(src, scene)
    t = round(float(t), 2)
    sl = slot(src, fn, events, t, fps, timed, 0.0)
    lines = []
    if timed and sl.at_needed and t > 1 / fps:
        lines.append(f"self.at({fmt(t)})")
    elif not timed and t - sl.start > 1 / fps:
        raise EditError(f"in a sequential scene a section can start only where a clip starts or ends "
                        f"(nearest: {sl.start:.2f} s)")
    lines.append(f"self.next_section({_string_like(src, None, name)})")
    start = t if (timed and sl.at_needed) else max(sl.start, t if timed else sl.start)
    return Plan(_emit(src, sl, lines), f"section {name!r} starts at {start:.2f} s" + (sl.note or ""),
                checks={"section": {"name": name, "start": start}})


def plan_section_rename(src: Source, scene: str, sec: dict, name) -> Plan:
    name = _section_name(name)
    call, _ = _section_call(src, scene, sec)
    node = call.args[0] if call.args else (Source.keyword(call, "name").value if Source.keyword(call, "name") else None)
    if node is None:
        return Plan([set_keyword(src, call, "name", _string_like(src, None, name))] if call.keywords else
                    [Edit(src.offset(call.end_lineno, call.end_col_offset) - 1,
                          src.offset(call.end_lineno, call.end_col_offset) - 1, _string_like(src, None, name))],
                    f"section named {name!r}", checks={"section": {"name": name, "start": sec["start"]}})
    _plain_string(src, node, "section name")
    return Plan([Edit(*src.span(node), _string_like(src, node, name))], f"section renamed {name!r}",
                checks={"section": {"name": name, "start": sec["start"]}})


def plan_section_delete(src: Source, scene: str, sec: dict) -> Plan:
    call, st = _section_call(src, scene, sec)
    if not (isinstance(st, ast.Expr) and st.value is call):
        raise EditError(f"line {st.lineno} does more than start a section")
    e = remove_statement(src, st)
    if e is None:
        s0, s1 = src.span(st)
        e = Edit(s0, s1, "pass")
    return Plan([e], f"section {sec.get('name')!r} removed (line {st.lineno})",
                checks={"section_gone": sec.get("name")})


# -- dead anchors (Phase 4 exit §3.2, Phase 5 step 3) ------------------------------
def _anchor_calls(src: Source, scene: str) -> list:
    """`self.at(...)` statements in the scene's own construct(), in order
    (nested functions excluded)."""
    from .inserts import scene_construct
    try:
        fn = scene_construct(src, scene)
    except EditError:
        return []
    out = []

    def walk(body):
        for s in body:
            if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and _is_self(s.value, "at"):
                out.append(s)
            for name in ("body", "orelse", "finalbody"):
                inner = getattr(s, name, None)
                if isinstance(inner, list) and not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                                    ast.ClassDef)):
                    walk(inner)
    walk(fn.body)
    return out


def _waiting(stmts: list, trace: dict) -> list[bool]:
    """Which of these at() statements made the scene wait in `trace`."""
    calls = {tuple(ev["call"]) for ev in trace.get("events", []) if ev.get("call") and ev["kind"] == "wait"}
    return [(s.value.lineno, s.value.col_offset, s.value.end_lineno, s.value.end_col_offset) in calls
            for s in stmts]


def dead_anchors(old: Source, old_trace: dict, new: Source, new_trace: dict, scene: str) -> tuple[list[Edit], str]:
    """Edits on `new` removing the `self.at(t)` calls this edit left with
    nothing to wait for (they waited before, and now the scene is already
    past t). Nothing is removed when the edit added or removed at() calls,
    because matching them up would be a guess. Removing one changes no
    timing: it no longer waits."""
    a, b = _anchor_calls(old, scene), _anchor_calls(new, scene)
    if not a or len(a) != len(b):
        return [], ""
    before, after = _waiting(a, old_trace), _waiting(b, new_trace)
    dead = [s for s, w0, w1 in zip(b, before, after) if w0 and not w1]
    if not dead:
        return [], ""
    from .inserts import _remove_stmts
    try:
        edits = _remove_stmts(new, dead)
    except EditError:
        return [], ""
    what = ", ".join(f"{new.text(s.value)} (line {s.lineno})" for s in dead)
    return edits, f"; removed {what}: it no longer waits for anything"


# -- TARGET: the scene's length (Phase 7 step 4) -------------------------------------------
def target_stmt(src: Source, scene: str):
    """The scene class's own `TARGET = ...` statement, or None (inherited or unset)."""
    for node in src.tree.body:
        if isinstance(node, ast.ClassDef) and node.name == scene:
            for b in node.body:
                tgt = (b.targets[0] if isinstance(b, ast.Assign) and len(b.targets) == 1
                       else getattr(b, "target", None) if isinstance(b, ast.AnnAssign) else None)
                if isinstance(tgt, ast.Name) and tgt.id == "TARGET" and b.value is not None:
                    return b
            return None
    raise EditError(f"no class {scene} in the file")


def plan_target(src: Source, scene: str, value: float) -> Plan:
    """Set the scene's TARGET: its own literal is changed; a computed one is
    refused; without one of its own, a `TARGET = value` line is added to the
    class (it overrides an inherited one)."""
    value = round(float(value), 2)
    if not 0 < value <= 3600:
        raise EditError("a length in seconds, more than 0")
    st = target_stmt(src, scene)
    if st is not None:
        old = number_of(st.value)
        if old is None:
            raise EditError(f"TARGET is computed ({src.text(st.value)}, line {st.lineno}); change it in the code")
        if abs(old - value) < 1e-9:
            raise EditError(f"TARGET is already {fmt(old)}")
        return Plan([set_number(src, st.value, value)], f"TARGET {fmt(old)} → {fmt(value)}",
                    checks={"target": value})
    cls = next(n for n in src.tree.body if isinstance(n, ast.ClassDef) and n.name == scene)
    v = fmt(value) + (".0" if float(value).is_integer() and _point_style(src, "target") else "")
    text = f"TARGET = {v}"
    return Plan([_class_setting(src, cls, text)], f"{text} added", checks={"target": value})


def _class_setting(src: Source, cls: ast.ClassDef, text: str) -> Edit:
    """A new `NAME = value` line in a class: after its docstring and its other
    settings, before its first method."""
    nl = src.newline
    ind = src.indent_of(cls.body[0].lineno)
    body = list(cls.body)
    k = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        k = 1  # after the docstring
    while k < len(body) and isinstance(body[k], (ast.Assign, ast.AnnAssign)):
        k += 1  # after the class's other settings (VOICE, CAPTIONS, ...)
    if k > 0:
        at = src.line_end(body[k - 1].end_lineno)
        return Edit(at, at, f"{ind}{text}{nl}")
    first = body[0]
    line = min([first.lineno] + [d.lineno for d in getattr(first, "decorator_list", [])])
    at = src.line_starts[line - 1]
    return Edit(at, at, f"{ind}{text}{nl}{nl}")


# -- VOICE: narrating a silent scene (Phase 7 step 5) ---------------------------------------
HOUSE_VOICE = "en-US-AndrewNeural"


def class_chain(src: Source, scene: str) -> list[ast.ClassDef]:
    """The scene class and its base classes defined in this file, nearest first."""
    classes = {n.name: n for n in src.tree.body if isinstance(n, ast.ClassDef)}
    out, todo = [], [scene]
    while todo:
        name = todo.pop(0)
        c = classes.get(name)
        if c is None or c in out:
            continue
        out.append(c)
        todo.extend(b.id for b in c.bases if isinstance(b, ast.Name))
    return out


def _setting(cls: ast.ClassDef, attr: str):
    for st in cls.body:
        tgt = (st.targets[0] if isinstance(st, ast.Assign) and len(st.targets) == 1
               else getattr(st, "target", None) if isinstance(st, ast.AnnAssign) else None)
        if isinstance(tgt, ast.Name) and tgt.id == attr and st.value is not None:
            return st
    return None


def voice_state(src: Source, scene: str) -> dict:
    """Who sets the scene's VOICE in this file, and whether it is None (silent)."""
    for cls in class_chain(src, scene):
        st = _setting(cls, "VOICE")
        if st is not None:
            silent = isinstance(st.value, ast.Constant) and st.value.value is None
            return {"silent": silent, "owner": cls.name, "line": st.lineno}
    return {"silent": False, "owner": None, "line": None}


TEMPLATE_SILENT_NOTE = "set a voice to narrate"  # inserts.new_file_text's comments on VOICE
TEMPLATE_VOICED_NOTE = "the house voice; None for a silent scene"


def plan_set_voice(src: Source, scene: str, where: str) -> Plan:
    """Give a silent scene the house voice: on the scene class itself
    (where="class"), or on the base class that sets VOICE = None
    (where="base": every scene built on it gets the voice)."""
    vs = voice_state(src, scene)
    if not vs["silent"]:
        raise EditError("this scene already has a voice")
    owner = next(c for c in class_chain(src, scene) if c.name == vs["owner"])
    st = _setting(owner, "VOICE")
    lit = _string_like(src, None, HOUSE_VOICE)

    def set_value() -> list[Edit]:
        # the template's "# set a voice to narrate" would be wrong once it is set:
        # it becomes the voiced template's comment
        edits = [Edit(*src.span(st.value), lit)]
        rest = src.after(st.end_lineno, st.end_col_offset)
        i = rest.find(TEMPLATE_SILENT_NOTE)
        if i >= 0 and not rest[:i].strip().strip("#").strip():
            a = src.offset(st.end_lineno, st.end_col_offset) + len(rest[:i].encode("utf-8"))
            edits.append(Edit(a, a + len(TEMPLATE_SILENT_NOTE.encode("utf-8")), TEMPLATE_VOICED_NOTE))
        return edits
    if where == "base":
        if owner.name == scene:
            raise EditError("VOICE = None is on the scene itself, not on a base class")
        return Plan(set_value(), f"VOICE on {owner.name} → {lit}")
    if where != "class":
        raise EditError(f"where must be 'class' or 'base', not {where!r}")
    if owner.name == scene:
        return Plan(set_value(), f"VOICE → {lit}")
    cls = class_chain(src, scene)[0]
    return Plan([_class_setting(src, cls, f"VOICE = {lit}")], f"VOICE = {lit} added to {scene}")
