"""Part-level colour for Text / MathTex / Tex (Phase 5, step 6).

The user picks glyphs on the canvas; the engine's probe map
(`engine/texmap.py`) says which source characters made them. This module
turns that into code, preferring forms that leave the formula's structure
alone:

- Text: `t2c={"word": C}` on the call (the word when it occurs once in the
  text, else Manim's slice key `"[a:b]"`).
- MathTex / Tex, a whole part (an argument, a `{{ }}` group): `eq[i].set_color(C)`
  on a new line after the formula is made.
- MathTex / Tex, a piece inside a part:
  1. `tex_to_color_map={"x": C}` on the call, when the piece's TeX occurs
     once in the whole formula and no code indexes the formula (isolating
     the piece renumbers the parts);
  2. otherwise `eq[i][a:b].set_color(C)`, an index override on a new line.

Every candidate is checked by replay (project.py): the coloured glyphs
must be exactly the selected ones, and no other glyph changes colour. The
first candidate that passes is written.
"""

from __future__ import annotations

import ast

from .source import Source
from .splice import Edit, EditError, set_keyword

TEXT = {"Text"}
TEX = {"MathTex", "Tex", "SingleStringMathTex"}
MATCHERS = {"TransformMatchingTex", "TransformMatchingShapes"}


def selection(glyphs: dict, picked: list) -> list[int]:
    """The picked glyphs, grown to whole pieces (an `a` and its `^2` are
    separate pieces; the two glyphs of `\\vec{v}` are one)."""
    mp = glyphs.get("map") or []
    try:
        picked = sorted({int(i) for i in picked})
    except (TypeError, ValueError):
        raise EditError("bad glyph selection") from None
    if not picked or any(not 0 <= i < len(mp) for i in picked):
        raise EditError("pick glyphs of the formula first")
    pieces = {tuple(mp[i]) for i in picked}
    return [i for i, m in enumerate(mp) if tuple(m) in pieces]


def candidates(src: Source, obj: dict, glyphs: dict, sel: list[int], colour: str) -> list:
    """Plans to try, best first. `colour` is code (`YELLOW`, `"#FF0000"`)."""
    from .planner import Plan, _call
    if not src.ok:
        raise EditError("the file doesn't parse")
    cls = obj.get("class")
    if obj.get("site") is None:
        raise EditError("this text isn't made by a call in the scene file")
    call = _call(src, obj["site"], cls or "constructor")
    texts = obj.get("texts") or []
    mp = glyphs["map"]
    parts = glyphs["parts"]
    name = _name(src, obj)
    out = []
    confirm = None
    if obj.get("in_helper"):
        confirm = f"{cls} is made inside {obj.get('func')}(): this changes every text that helper makes"

    if glyphs.get("kind") == "text":
        if cls not in TEXT:
            raise EditError(f"part colour on a {cls} isn't supported yet")
        chars = sorted({c for i in sel for c in range(mp[i][1], mp[i][2])})
        a, b = chars[0], chars[-1] + 1
        inside = [i for i, m in enumerate(mp) if a <= m[1] < b]
        if inside != sel:
            raise EditError("pick letters next to each other")
        text = parts[0]
        word = text[a:b]
        key = word if text.count(word) == 1 and word.strip() == word else f"[{a}:{b}]"
        e = _add_to_map(src, call, "t2c", key, colour)
        if e is not None:
            out.append(Plan([e], f"t2c: {key!r} → {colour}", confirm, checks={"part_colour": True}))
        if name:
            k = sel
            idx = f"[{k[0]}]" if len(k) == 1 else f"[{k[0]}:{k[-1] + 1}]"
            out += _override(src, name, idx, colour, confirm, k == list(range(k[0], k[-1] + 1)))
        if not out:
            raise EditError("t2c is set in a way the studio can't extend, and the text has no name")
        return out

    if cls not in TEX:
        raise EditError(f"part colour on a {cls} isn't supported yet")
    p = {mp[i][0] for i in sel}
    if len(p) != 1:
        raise EditError("pick glyphs from one part of the formula (one string)")
    p = p.pop()
    in_part = [i for i, m in enumerate(mp) if m[0] == p]
    pos = [in_part.index(i) for i in sel]
    contiguous = pos == list(range(pos[0], pos[-1] + 1))
    whole = len(pos) == len(in_part)
    if not whole:
        # 1. isolate the piece by its TeX, when that is safe
        lo = min(mp[i][1] for i in sel)
        hi = max(mp[i][2] for i in sel)
        piece = parts[p][lo:hi]
        exact = [i for i in in_part if lo <= mp[i][1] and mp[i][2] <= hi] == sel
        literal = p < len(texts) and texts[p].get("editable")
        tex_all = " ".join(parts)
        if exact and literal and piece.strip() and tex_all.count(piece) == 1 and _balanced(piece) \
                and not (name and _indexed(src, call, name[0])):
            e = _add_to_map(src, call, "tex_to_color_map", piece, colour)
            if e is not None:
                out.append(Plan([e], f"tex_to_color_map: {piece!r} → {colour}", confirm,
                                checks={"part_colour": True}))
    if name:
        head = f"[{p}]"  # a MathTex's submobjects are its parts, even with one part
        if whole:
            idx = head
        else:
            idx = head + (f"[{pos[0]}]" if len(pos) == 1 else f"[{pos[0]}:{pos[-1] + 1}]")
        out += _override(src, name, idx, colour, confirm, contiguous)
    if not out:
        if not contiguous:
            raise EditError("pick glyphs next to each other")
        raise EditError("the formula has no name in construct(); name it in the code first "
                        "(eq = MathTex(...)), or pick a piece that appears once")
    return out


def _override(src, name_stmt, idx: str, colour: str, confirm, contiguous: bool) -> list:
    from .moves import insert_after
    from .planner import Plan
    if not contiguous:
        return []
    name, stmt = name_stmt
    line = f"{name}{idx}.set_color({colour})"
    try:
        e = insert_after(src, stmt, line)
    except EditError:
        return []
    return [Plan([e], f"new line {line} after line {stmt.end_lineno}", confirm, checks={"part_colour": True})]


def _name(src: Source, obj: dict):
    from .moves import assigned_name, function_of
    named = assigned_name(src, obj.get("site"))
    if named and function_of(src, named[1]) is not None:
        return named
    return None


def _indexed(src: Source, call, name: str) -> bool:
    """Does code in the same function index the formula, or hand it to a
    matching transform (which pairs parts)?"""
    from .moves import function_of
    fn = function_of(src, call) or src.tree
    for n in ast.walk(fn):
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == name:
            return True
        if isinstance(n, ast.Call):
            f = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
            if f in MATCHERS and any(isinstance(a, ast.Name) and a.id == name for a in n.args):
                return True
            if f in ("get_part_by_tex", "get_parts_by_tex", "index_of_part", "index_of_part_by_tex"):
                return True
    return False


def _balanced(t: str) -> bool:
    depth, i = 0, 0
    while i < len(t):
        if t[i] == "\\":
            i += 2
            continue
        depth += {"{": 1, "}": -1}.get(t[i], 0)
        if depth < 0:
            return False
        i += 1
    return depth == 0 and not t.rstrip().endswith(("^", "_")) and not t.lstrip().startswith(("^", "_"))


def _str_code(src: Source, s: str) -> str:
    """A Python literal for TeX: raw when it has backslashes and can be raw."""
    if "\\" in s and '"' not in s and not s.endswith("\\") and "\n" not in s:
        return f'r"{s}"'
    from .planner import _string_like
    return _string_like(src, None, s)


def _add_to_map(src: Source, call, kw: str, key: str, colour: str) -> Edit | None:
    """`kw={key: colour}` on the call, or one more entry in its dict literal."""
    k = Source.keyword(call, kw)
    entry = f"{_str_code(src, key)}: {colour}"
    if k is None:
        return set_keyword(src, call, kw, "{" + entry + "}")
    d = k.value
    if not isinstance(d, ast.Dict) or any(x is None for x in d.keys):
        return None
    for x in d.keys:
        if isinstance(x, ast.Constant) and x.value == key:
            a, b = src.span(d.values[d.keys.index(x)])
            return Edit(a, b, colour)
    a, b = src.span(d)
    return Edit(b - 1, b - 1, (", " if d.keys else "") + entry)


def check(before: list, after_glyphs: dict | None, sel: list[int], want: str | None, same) -> str | None:
    """None when exactly the selected glyphs took the colour."""
    if not after_glyphs:
        return "after the edit the studio can't match the text's glyphs to its source"
    after = after_glyphs.get("colors") or []
    if len(after) != len(before):
        return "the edit changed how many glyphs the text has"
    s = set(sel)
    for i, (b, a) in enumerate(zip(before, after)):
        if i in s:
            if want is not None and not same(a, want):
                return f"glyph {i + 1} came out {a}, not {want}"
        elif not same(a, b):
            return f"glyph {i + 1} changed colour too ({b} → {a})"
    return None
