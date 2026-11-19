"""Spike S6: which glyphs of a formula come from which characters of its TeX?

Manim CE 0.22 splits MathTex into parts with dvisvgm `\\special` groups
(one compile; the SVG keeps a <g id=...> per part). The studio can do the
same in a *probe* compile, never in the user's file: wrap small pieces of
the TeX (a letter, a digit, an operator, a command like \\alpha, a fraction,
a matrix, a base with its scripts) in groups, nested where TeX nests, and
read off which glyphs each piece made. A glyph belongs to the innermost
piece that holds it: the bar of \\frac{a}{b} to the \\frac, the `a` to `a`.

For every fixed TeX string in the corpus this checks:
  compiles   the probed string still compiles
  faithful   same glyph count as the plain compile, every glyph within
             0.001 units of where it was and the same width
  mapped     share of glyphs that fall in some piece
and times both compiles.

Run:  .venv/Scripts/python -u studio/spikes/s6_tex_parts.py [--show N]
Uses its own LaTeX folder (media/Tex_spike), so it is safe beside the studio.
Report: media/studio_spikes/s6/report.json
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from manim import SingleStringMathTex, config  # noqa: E402

config.tex_dir = str(ROOT / "media" / "Tex_spike")
OUT = ROOT / "media" / "studio_spikes" / "s6"

TEX_CALLS = {"MathTex": "math", "Tex": "text", "SingleStringMathTex": "math"}
FILES = ["test_scene.py", "pythagoras.py", "order_matters.py", "gradient_descent.py", "eola_preview.py"]


def corpus_tex() -> list[dict]:
    files = list(FILES)
    for d in ("studio/tests/corpus/awkward", "studio/tests/corpus/gallery", "tools/fixtures"):
        files += [f"{d}/{p.name}" for p in sorted((ROOT / d).glob("*.py"))]
    out, seen = [], set()
    for rel in files:
        try:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in TEX_CALLS):
                continue
            parts = [a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if not parts or len(parts) != len(n.args):
                continue  # computed TeX (f-strings, names): not a fixed formula
            key = (TEX_CALLS[n.func.id], tuple(parts))
            if key in seen:
                continue
            seen.add(key)
            out.append({"file": rel, "line": n.lineno, "mode": TEX_CALLS[n.func.id], "parts": parts})
    return out


# -- the probe ----------------------------------------------------------------------
CLOSE = r"\special{dvisvgm:raw </g>}"
SPACING = {"quad", "qquad", ",", ";", ":", "!", " ", "\\", "displaystyle", "textstyle", "scriptstyle",
           "scriptscriptstyle", "limits", "nolimits", "hfill", "newline", "noindent", "centering", "par",
           "small", "large", "Large", "LARGE", "huge", "Huge", "normalsize", "footnotesize", "tiny"}
ACCENTS = {"vec", "hat", "bar", "tilde", "dot", "ddot", "widehat", "widetilde", "overrightarrow",
           "overleftarrow", "acute", "grave", "check", "breve", "mathring"}
TEXT_ACCENTS = set("'`^\"~=.") | {"c", "v", "u", "H", "r", "d", "b", "t", "k"}
UNDRAWN_ARGS = {"textcolor": 1, "colorbox": 1}       # leading arguments that are not drawn
NOT_DRAWN = {"color", "hspace", "vspace", "label"}   # the whole command draws nothing
CMD = re.compile(r"\\([A-Za-z]+|.)")
LIGATURE = re.compile("``|''|---|--|!`|\\?`")


def _open(k: int) -> str:
    return r"\special{dvisvgm:raw <g id='q%04d'>}" % k


class Probe:
    """pieces[k] = (start, end, own_start, own_end): the span group k covers,
    and the part whose glyphs are its own (not in a nested group)."""

    def __init__(self, tex: str, text_mode: bool):
        self.t, self.text_mode = tex, text_mode
        self.pieces: list[tuple[int, int, int, int]] = []

    def wrap(self, body: str, span: tuple[int, int], own: tuple[int, int]) -> str:
        self.pieces.append((*span, *own))
        return _open(len(self.pieces) - 1) + body + CLOSE

    # -- scanning ---------------------------------------------------------------------
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
        """Start of the close that matches the open at j."""
        depth = 0
        for m in re.finditer(f"(?P<o>{open_re})|(?P<c>{close_re})", self.t[j:]):
            depth += 1 if m.group("o") else -1
            if depth == 0:
                return j + m.start()
        return len(self.t)

    def token_end(self, k: int) -> int:
        """End of one token at k: a command, a {group} or a character."""
        t = self.t
        if k >= len(t):
            return k
        if t[k] == "\\":
            return CMD.match(t, k).end()
        if t[k] == "{":
            return self.group_end(k) + 1
        return k + 1

    # -- one atom: (output, end, how) where how is False (keep as is), "leaf"
    #    (one piece) or "outer" (a piece around probed insides) -----------------------
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
                k = self.group_end(j) + 1                                   # past {env}
                k2 = self.matching(i, r"\\begin\{", r"\\end\{")             # \end{...}
                e = self.group_end(k2 + 4) + 1
                return t[i:k] + self.seq(k, k2) + t[k2:e], e, "outer"
            if name == "left":
                k = self.token_end(self.skip_space(j))                     # past the delimiter
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

    def own_of(self, start: int, end: int, how: str) -> tuple[int, int]:
        if how == "outer" and self.t[start] == "\\":
            return start, CMD.match(self.t, start).end()   # the command draws its own glyphs (a bar, a radical)
        return start, end

    # -- a sequence of atoms, each with its scripts --------------------------------------
    def seq(self, a: int, b: int) -> str:
        t, out, i = self.t, [], a
        while i < b:
            if t[i] in "^_":                      # scripts with no base
                out.append(t[i])
                i = self.script(i + 1, b, out)
                continue
            start = i
            text, i, how = self.atom(i, b)
            k = self.skip_space(i)
            if how and not self.text_mode and k < b and t[k] in "^_":
                # the base and its scripts in one group: limits and kerning stay as they were
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


def probe(tex: str, text_mode: bool) -> tuple[str, list]:
    p = Probe(tex, text_mode)
    return p.seq(0, len(tex)), p.pieces


# -- measuring ------------------------------------------------------------------------
def glyphs(m) -> list:
    return list(m.family_members_with_points())


def run_one(item: dict) -> dict:
    mode = item["mode"]
    tex = " ".join(item["parts"]) if mode == "math" else "".join(item["parts"])
    res = {"file": item["file"], "line": item["line"], "tex": tex[:120], "mode": mode}

    def single(x):  # Tex is MathTex in a "center" environment (text mode)
        return SingleStringMathTex(x) if mode == "math" else SingleStringMathTex(x, tex_environment="center")

    t = time.monotonic()
    try:
        plain = single(tex)
    except Exception as e:  # noqa: BLE001
        res["plain_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return res
    res["plain_s"] = round(time.monotonic() - t, 2)
    probed, pieces = probe(tex, mode == "text")
    res["pieces"] = len(pieces)
    t = time.monotonic()
    try:
        m = single(probed)
    except Exception as e:  # noqa: BLE001
        res["compiles"] = False
        res["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        res["probed"] = probed[:600]
        return res
    res["probe_s"] = round(time.monotonic() - t, 2)
    res["compiles"] = True
    a, b = glyphs(plain), glyphs(m)
    res["glyphs"] = len(a)
    res["faithful"] = bool(len(a) == len(b) and all(
        np.allclose(x.get_center(), y.get_center(), atol=1e-3) and abs(x.width - y.width) < 1e-3
        for x, y in zip(a, b)))
    d = getattr(m, "id_to_vgroup_dict", {})
    # innermost piece per glyph: the one with the shortest span
    owner: dict[int, int] = {}
    for k, (s0, s1, _, _) in enumerate(pieces):
        g = d.get("q%04d" % k)
        if g is None:
            continue
        for x in glyphs(g):
            cur = owner.get(id(x))
            if cur is None or (s1 - s0) < (pieces[cur][1] - pieces[cur][0]):
                owner[id(x)] = k
    mapped = sum(1 for x in b if id(x) in owner)
    res["mapped"] = round(mapped / len(b), 3) if b else 1.0
    res["unmapped_glyphs"] = len(b) - mapped
    if res["unmapped_glyphs"] or not res["faithful"]:
        res["probed"] = probed[:600]
    # what each piece's own glyphs are, for a look at the map
    res["map"] = [tex[p[2]:p[3]] for k, p in enumerate(pieces)
                  if any(owner.get(id(x)) == k for x in glyphs(d.get("q%04d" % k, m)))][:40]
    return res


def main():
    show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 0
    items = corpus_tex()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for it in items:
        r = run_one(it)
        rows.append(r)
        flag = ("PLAIN-ERR" if "plain_error" in r else "OK" if r.get("faithful") and r.get("mapped") == 1
                else "NO-COMPILE" if not r.get("compiles")
                else f"faithful={r.get('faithful')} mapped={r.get('mapped')}")
        print(f"{flag:30} {Path(r['file']).name}:{r['line']} {r['tex'][:60]!r}", flush=True)
    ok = [r for r in rows if "plain_error" not in r]
    summary = {
        "formulas": len(rows),
        "plain_compile_errors": len(rows) - len(ok),
        "probe_compiles": sum(1 for r in ok if r.get("compiles")),
        "faithful": sum(1 for r in ok if r.get("faithful")),
        "fully_mapped_and_faithful": sum(1 for r in ok if r.get("faithful") and r.get("mapped") == 1),
        "glyphs": sum(r.get("glyphs", 0) for r in ok),
        "unmapped_glyphs": sum(r.get("unmapped_glyphs", 0) for r in ok if r.get("compiles")),
        "median_plain_s": float(np.median([r["plain_s"] for r in ok])) if ok else None,
        "median_probe_s": float(np.median([r["probe_s"] for r in ok if "probe_s" in r])) if ok else None,
    }
    (OUT / "report.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for r in [r for r in ok if not (r.get("faithful") and r.get("mapped") == 1)][:show]:
        print(json.dumps({k: v for k, v in r.items() if k != "map"}, indent=1))


if __name__ == "__main__":
    main()
