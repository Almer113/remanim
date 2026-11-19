# S6: which glyphs of a formula come from which part of its TeX?

**Question** (Phase 5 plan, step 4): when the user selects glyphs of a
`MathTex` / `Tex` on the canvas, can the studio tell exactly which
characters of the TeX source made them, reliably and fast enough to build
in-place editing and part colouring on?

**Verdict: go.** On every fixed formula in the corpus (80 distinct
strings, 1,021 glyphs, maths and text mode), a probe compile gives an
exact glyph → source map, and draws exactly what the plain compile draws.

Code: `studio/spikes/s6_tex_parts.py`. Report:
`media/studio_spikes/s6/report.json` (with the map of every formula).

## How it works

Manim CE 0.22 already splits a `MathTex` into parts with dvisvgm specials:
each part is wrapped in `\special{dvisvgm:raw <g id='...'>}` ...
`\special{dvisvgm:raw </g>}`, compiled once, and the SVG keeps one `<g>`
per part (`id_to_vgroup_dict`). The studio does the same in a **probe
compile**, which never touches the user's file. It wraps every small piece
of the TeX in its own group, nested where TeX nests:

| Piece | Example | Its own glyphs |
|---|---|---|
| a character, or a word in text mode | `a`, `+`, `Jean` | the glyph(s) |
| a command with no arguments | `\alpha`, `\cdot`, `\infty`, `\sum` | the symbol |
| a command with arguments, around its probed arguments | `\frac{1}{n^2}`, `\sqrt{x}` | the bar, the radical |
| an accent, whole | `\vec{v}`, `\'e` | letter and accent |
| an environment, around its probed body | `\begin{bmatrix}...\end{bmatrix}` | the brackets |
| `\left( ... \right)`, around its probed body | | the delimiters |
| a base with its scripts, around the probed scripts | `a^2`, `\sum_{n=1}^\infty` | the base (`a`, `Σ`) |
| text ligatures, whole | ``` `` ```, `''`, `---` | the ligature |

A glyph belongs to the innermost piece that holds it. Spacing commands,
`&`, `\\`, colour and environment names and comments are left as they are.

## Results

| Measure | Result |
|---|---|
| Formulas (distinct fixed strings in the corpus) | 80 (maths and text mode) |
| Probe compiles | **80 / 80** |
| Faithful (same glyph count; every glyph within 0.001 units and the same width) | **80 / 80** |
| Glyphs mapped to a piece | **1,021 / 1,021** |
| Compile time, fresh | 1.6–2.9 s (as a plain compile) |
| Compile time, cached | 0.1–0.2 s |

The first version of the probe wrapped pieces flat. That version failed
on 13 formulas, all through tokenising, not through the method itself:
- `\overset` was wrapped without its arguments, so it didn't compile;
- accents and `\'e` were split from their letters;
- ``` `` ``` and `---` ligatures were broken apart;
- `\sum` was separated from its limits, which moved them;
- matrix brackets and `\left(` delimiters ended up in no piece.

The nested version fixes all of these.

Examples of the map (each piece's own glyphs, in drawing order):
- `a^2 + b^2 = c^2` → `2, a, +, 2, b, =, 2, c` (each `a` and its `2` are
  told apart);
- `\sum_{n=1}^\infty \frac{1}{n^2}` → `n, =, 1, \infty, \sum, 1, 2, n, \frac`;
- a matrix's brackets → `\begin`.

## What this means for step 5 and 6

1. **Selecting part of a formula** (step 6): the engine runs the probe
   compile for the selected object's TeX (cached per string, like Manim's
   own cache) and sends a glyph → source-span map with the object. A drag
   across glyphs on the canvas becomes a span of the TeX string, extended
   to whole pieces.
2. **Colouring** the span: the rules in the plan (`{{ }}` / an index
   override / `t2c`) can then be checked exactly. After the replay, the
   coloured glyphs must be the selected ones.
3. **In-place editing** (step 5) doesn't need the map. Showing the cursor
   at the clicked glyph's place in the source does.
4. **Cost**: one extra compile per new formula, ~2 s fresh and ~0.1 s
   cached. It is run lazily, only when the user selects inside a formula,
   so opening a file doesn't get slower.

Limits:
- TeX built at run time (f-strings, names) is probed from the string
  Manim actually received, which the engine records. Only its literal
  pieces can be edited (code_spec tier 2).
- Custom macros from a user `TexTemplate` are treated as commands. A macro
  that takes arguments without braces would be split wrongly; the
  faithfulness check would catch it, and the studio then falls back to
  whole-part selection.
