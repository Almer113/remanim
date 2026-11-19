"""Which glyphs of a Text / MathTex / Tex come from which characters of its
source (Phase 5, step 6; spike S6, `docs/phase0/S6_tex_parts.md`).

MathTex / Tex: a *probe compile* of the same TeX (same environment and
template), with every small piece wrapped in a dvisvgm `\\special` group,
nested where TeX nests. A glyph belongs to the innermost piece holding it.
The user's file is never touched. The map is used only when the probe draws
exactly what the object draws: same glyph count, and the glyph centres match
the object's up to a similarity (the object may since have been moved,
scaled or turned).

Text (Pango): glyph i is the i-th character that isn't white space, when
the counts agree.

Result, per glyph in the object's *drawing order* (SVG order):
    {"kind": "tex"|"text", "parts": [...], "glyphs": [[part, start, end], ...]}
`start:end` index into `parts[part]`: the piece's own characters.
"""

from __future__ import annotations

import re

import numpy as np

CLOSE = r"\special{dvisvgm:raw </g>}"
SPACING = {"quad", "qquad", ",", ";", ":", "!", " ", "\\", "displaystyle", "textstyle", "scriptstyle",
           "scriptscriptstyle", "limits", "nolimits", "hfill", "newline", "noindent", "centering", "par",
           "small", "large", "Large", "LARGE", "huge", "Huge", "normalsize", "footnotesize", "tiny"}
ACCENTS = {"vec", "hat", "bar", "tilde", "dot", "ddot", "widehat", "widetilde", "overrightarrow",
           "overleftarrow", "acute", "grave", "check", "breve", "mathring"}
TEXT_ACCENTS = set("'`^\"~=.") | {"c", "v", "u", "H", "r", "d", "b", "t", "k"}
UNDRAWN_ARGS = {"textcolor": 1, "colorbox": 1}
NOT_DRAWN = {"color", "hspace", "vspace", "label"}
CMD = re.compile(r"\\([A-Za-z]+|.)")
LIGATURE = re.compile("``|''|---|--|!`|\\?`")


class Probe:
    """pieces[k] = (start, end, own_start, own_end) in this part's string;
    group ids are `<prefix><k>`."""

    def __init__(self, tex: str, text_mode: bool, prefix: str):
        self.t, self.text_mode, self.prefix = tex, text_mode, prefix
        self.pieces: list[tuple[int, int, int, int]] = []

    def gid(self, k: int) -> str:
        return f"{self.prefix}{k:04d}"

    def wrap(self, body: str, span, own) -> str:
        self.pieces.append((*span, *own))
        return r"\special{dvisvgm:raw <g id='%s'>}" % self.gid(len(self.pieces) - 1) + body + CLOSE

    def group_end(self, j: int) -> int:
        t, depth = self.t, 0
        while j < len(t):
            c = t[j]
            if c == "\\":
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return len(t) - 1

    def skip_space(self, j: int) -> int:
        while j < len(self.t) and self.t[j] in " \t\n":
            j += 1
        return j

    def matching(self, j: int, open_re: str, close_re: str) -> int:
        depth = 0
        for m in re.finditer(f"(?P<o>{open_re})|(?P<c>{close_re})", self.t[j:]):
            depth += 1 if m.group("o") else -1
            if depth == 0:
                return j + m.start()
        return len(self.t)

    def token_end(self, k: int) -> int:
        t = self.t
        if k >= len(t):
            return k
        if t[k] == "\\":
            return CMD.match(t, k).end()
        if t[k] == "{":
            return self.group_end(k) + 1
        return k + 1

    def atom(self, i: int, end: int):
        t = self.t
        c = t[i]
        if c == "%":
            e = t.find("\n", i)
            e = end if e < 0 else e
            return t[i:e], e, False
        if c in " \t\n&~":
            return c, i + 1, False
        if c == "{":
            e = self.group_end(i)
            return "{" + self.seq(i + 1, e) + "}", e + 1, False
        if c == "\\":
            m = CMD.match(t, i)
            name, j = m.group(1), m.end()
            if name == "begin":
                k = self.group_end(j) + 1
                k2 = self.matching(i, r"\\begin\{", r"\\end\{")
                e = self.group_end(k2 + 4) + 1
                return t[i:k] + self.seq(k, k2) + t[k2:e], e, "outer"
            if name == "left":
                k = self.token_end(self.skip_space(j))
                k2 = self.matching(i, r"\\left(?![A-Za-z])", r"\\right(?![A-Za-z])")
                e = self.token_end(self.skip_space(k2 + 6))
                return t[i:k] + self.seq(k, k2) + t[k2:e], e, "outer"
            if name in ACCENTS or (self.text_mode and name in TEXT_ACCENTS):
                k = self.token_end(self.skip_space(j))
                return t[i:k], k, "leaf"
            if name in SPACING or not (name.isalpha() or name in "{}$%&#_|"):
                return t[i:j], j, False
            k, out, nargs = j, t[i:j], 0
            while k < end and t[k] in "{[":
                if t[k] == "[":
                    e = t.find("]", k)
                    e = end - 1 if e < 0 else e
                    out += t[k:e + 1]
                    k = e + 1
                    continue
                e = self.group_end(k)
                drawn = nargs >= UNDRAWN_ARGS.get(name, 0) and name not in NOT_DRAWN
                out += "{" + self.seq(k + 1, e) + "}" if drawn else t[k:e + 1]
                nargs += 1
                k = e + 1
            if name in NOT_DRAWN:
                return out, k, False
            return out, k, ("outer" if nargs else "leaf")
        if self.text_mode:
            m = LIGATURE.match(t, i)
            if m:
                return m.group(0), m.end(), "leaf"
            if c.isalpha():
                k = i
                while k < end and t[k].isalpha():
                    k += 1
                return t[i:k], k, "leaf"
        return c, i + 1, "leaf"

    def own_of(self, start: int, end: int, how) -> tuple[int, int]:
        if how == "outer" and self.t[start] == "\\":
            return start, CMD.match(self.t, start).end()
        return start, end

    def seq(self, a: int, b: int) -> str:
        t, out, i = self.t, [], a
        while i < b:
            if t[i] in "^_":
                out.append(t[i])
                i = self.script(i + 1, b, out)
                continue
            start = i
            text, i, how = self.atom(i, b)
            k = self.skip_space(i)
            if how and not self.text_mode and k < b and t[k] in "^_":
                parts = [text, t[i:k]]
                while k < b and t[k] in "^_":
                    parts.append(t[k])
                    k = self.script(k + 1, b, parts)
                    k2 = self.skip_space(k)
                    if k2 < b and t[k2] in "^_":
                        parts.append(t[k:k2])
                        k = k2
                    else:
                        break
                out.append(self.wrap("".join(parts), (start, k), self.own_of(start, i, how)))
                i = k
                continue
            out.append(self.wrap(text, (start, i), self.own_of(start, i, how)) if how else text)
        return "".join(out)

    def script(self, k: int, b: int, out: list) -> int:
        t = self.t
        k2 = self.skip_space(k)
        out.append(t[k:k2])
        k = k2
        if k >= b:
            return k
        if t[k] == "{":
            e = self.group_end(k)
            out.append("{" + self.seq(k + 1, e) + "}")
            return e + 1
        e = self.token_end(k)
        out.append("{" + self.seq(k, e) + "}")
        return e


def probe_parts(parts: list[str], text_mode: bool, sep: str) -> tuple[str, list[Probe]]:
    probes = [Probe(p, text_mode, f"sp{i:02d}x") for i, p in enumerate(parts)]
    return sep.join(pr.seq(0, len(pr.t)) for pr in probes), probes


# -- matching the probe to the object ------------------------------------------------
def _glyphs(m) -> list:
    return list(m.family_members_with_points())


def _svg_order(mob) -> list:
    """The object's glyphs in drawing (SVG) order: MathTex regroups them by
    part, but its "root" group keeps the order they were drawn in."""
    d = getattr(mob, "id_to_vgroup_dict", None) or {}
    root = d.get("root")
    if root is not None:
        g = _glyphs(root)
        mine = {id(x) for x in _glyphs(mob)}
        if len(g) == len(mine) and all(id(x) in mine for x in g):
            return g
    return _glyphs(mob)


def similar(a: np.ndarray, b: np.ndarray, tol: float = 0.02) -> bool:
    """Do points b match points a after one move, scale and turn? (complex
    least squares: b ≈ s·a + c)."""
    if len(a) != len(b):
        return False
    if len(a) == 1:
        return True
    za = a[:, 0] + 1j * a[:, 1]
    zb = b[:, 0] + 1j * b[:, 1]
    za0, zb0 = za - za.mean(), zb - zb.mean()
    den = np.vdot(za0, za0)
    if abs(den) < 1e-12:
        return bool(np.allclose(zb0, 0, atol=tol))
    s = np.vdot(za0, zb0) / den
    resid = np.abs(zb0 - s * za0)
    size = max(np.abs(zb0).max(), 1e-6)
    return bool(resid.max() <= tol * size)


_CACHE: dict = {}


def tex_map(mob) -> dict | None:
    """The glyph → source map for a Text / MathTex / Tex, or None."""
    try:
        from manim import MathTex, Tex, Text
    except Exception:  # noqa: BLE001
        return None
    if isinstance(mob, MathTex):
        return _tex(mob, isinstance(mob, Tex))
    if isinstance(mob, Text):
        return _text(mob)
    return None


def _text(mob) -> dict | None:
    text = getattr(mob, "original_text", None) or getattr(mob, "text", None)
    if not isinstance(text, str):
        return None
    chars = [i for i, c in enumerate(text) if not c.isspace()]
    g = _glyphs(mob)
    if len(g) != len(chars):
        return None  # ligatures or markup: no exact map
    return {"kind": "text", "parts": [text], "glyphs": [[0, i, i + 1] for i in chars]}


def _tex(mob, text_mode: bool) -> dict | None:
    from manim import SingleStringMathTex
    parts = [str(p) for p in getattr(mob, "tex_strings", []) or []]
    if not parts:
        return None
    sep = getattr(mob, "arg_separator", " ")
    env = getattr(mob, "tex_environment", "align*")
    template = getattr(mob, "tex_template", None)
    key = (tuple(parts), sep, env, text_mode, getattr(template, "body", None) if template else None)
    if key not in _CACHE:
        _CACHE[key] = _probe_once(parts, sep, env, template, text_mode, SingleStringMathTex)
    probed = _CACHE[key]
    if probed is None:
        return None
    centres, owners = probed
    mine = _svg_order(mob)
    if len(mine) != len(centres):
        return None
    pts = np.array([[x.get_center()[0], x.get_center()[1]] for x in mine])
    if not similar(centres, pts):
        return None
    return {"kind": "tex", "parts": parts, "glyphs": owners}


def _probe_once(parts, sep, env, template, text_mode, Single):
    body, probes = probe_parts(parts, text_mode, sep)
    try:
        kw = {"tex_environment": env}
        if template is not None:
            kw["tex_template"] = template
        m = Single(body, **kw)
    except Exception:  # noqa: BLE001  (a probe that doesn't compile: no map)
        return None
    d = getattr(m, "id_to_vgroup_dict", {})
    owner: dict[int, tuple] = {}
    for pi, pr in enumerate(probes):
        for k, (s0, s1, o0, o1) in enumerate(pr.pieces):
            grp = d.get(pr.gid(k))
            if grp is None:
                continue
            for x in _glyphs(grp):
                cur = owner.get(id(x))
                if cur is None or (s1 - s0) < cur[3]:
                    owner[id(x)] = (pi, o0, o1, s1 - s0)
    gl = _glyphs(m)
    if any(id(x) not in owner for x in gl):
        return None
    centres = np.array([[x.get_center()[0], x.get_center()[1]] for x in gl])
    return centres, [[owner[id(x)][0], owner[id(x)][1], owner[id(x)][2]] for x in gl]
