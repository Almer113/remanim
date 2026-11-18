# Editable-code specification

What the studio may write into a `.py` file, for each GUI edit, and what the
code it generates looks like. This is one of the two documents the user
approves to finish Phase 1 (the other is the wireframes).

Evidence for every rule here is in `docs/phase0/` (S2 for moves, S4 for
timing, S5 for tiers).

## 1. Ground rules

1. **Edits are byte splices** at exact AST spans. Nothing outside the span
   changes: not formatting, comments, blank lines, quotes or line endings.
2. **Every edit is verified by replay** before it is written. The edit must
   produce the requested result (within 0.01 units, or one frame for timing)
   and must not crash. Otherwise it is refused, with the reason.
3. **The file stays human code.** No markers, no IDs, no `# studio` comments,
   no generated helper classes. Someone reading the diff sees what they'd
   have typed.
4. **Smallest edit wins.** Candidates are ranked: change an existing literal
   > extend an existing call > chain a new call > insert a new statement >
   edit inside a helper (moves every use; needs confirmation).
5. **Round trips close.** Undoing a change, or dragging back by the same
   amount, restores the file byte for byte. A term that returns to zero is
   removed with its operator; a `.shift()` that becomes zero is removed; an
   inserted statement that becomes a no-op is deleted.
6. **Never write a file that doesn't parse**, and never edit a file whose
   current text doesn't parse.

## 2. Tiers, as the GUI shows them

| Tier | Meaning | Badge | GUI can |
|---|---|---|---|
| 1 | Literal arguments and known API (S5: 65% of statements) | none | everything below |
| 2 | Computed but traceable: reads other objects, indexes groups, loops over literal lists, helper calls (S5: 29.5%) | `≈` | edit the literals inside; move/style via overrides (section 5) |
| 3 | Lambdas, updaters, `always_redraw`, `while`, computed conditions (S5: 5.4%) | lock | select, see, jump to code; timing edits only on its `play()` |

A tier is a property of a statement. An object's tier for an edit is the
tier of the statement the edit would touch.

## 3. Number and vector formatting

- Numbers keep the style of the literal they replace: `0.5` → `0.25`, `2` →
  `3` when whole, `2` → `2.5` otherwise. Shortest form that round-trips,
  rounded to 4 decimals (0.0001 units is far below one pixel at 4K).
- Directions are written with Manim constants: `0.4 * RIGHT + 0.25 * DOWN`,
  not `np.array([0.4, -0.25, 0])`. Zero components are left out. One unit is
  `RIGHT`, not `1 * RIGHT`.
- An existing vector expression is edited in place, term by term:
  `UP * 0.5` → `UP * 0.25 + 0.4 * RIGHT` (the original term keeps its
  written order `UP * 0.5`; new terms are appended in `k * DIR` form).
- Colours: a palette name from `style.py` if the value matches one
  (`ACCENT`), else a Manim colour constant (`BLUE_C`), else a hex string
  `"#58c4dd"`.

## 4. Edits and their code

### 4.1 Move (drag on the canvas)

Candidates, in rank order. The first that verifies is written.

| Situation | Edit | Example |
|---|---|---|
| Last placed by a literal `shift(v)` / `move_to(v)` | change the numbers in `v` | `.shift(UP * 0.5)` → `.shift(UP * 0.25 + 0.4 * RIGHT)` |
| Last placed by a chained `.shift()` on the same expression | merge into it | `.next_to(a, UP).shift(0.2 * UP)` → `.shift(0.2 * UP + 0.4 * RIGHT)` |
| Last placed by anything else (`next_to`, `to_edge`, `place()`, a constructor) | chain `.shift(d)` on that call | `get_title().shift(0.4 * RIGHT + 0.25 * DOWN)` |
| Placed by a group's `arrange()` | new statement after the layout: `name.shift(d)`, or `group[i][j].shift(d)` | `row[0][1].shift(0.4 * RIGHT)` |
| Made in a helper, used here | chain `.shift(d)` on **this** call of the helper | `fog = get_fog().shift(0.3 * LEFT)` |
| Helper returns a tuple | new statement after the unpacking: `name.shift(d)` | `dots.shift(0.3 * LEFT)` (Phase 3 gap 2) |
| Library object placed by its own arguments | edit that argument (pattern rule per class) | `ClippedGrid(("ellipse", c + 0.4 * RIGHT, a, b), ...)` (Phase 3 gap 1) |
| Moved by `.animate.shift()`/`.move_to()` in a play, and the drag is at or after that play | change the animate call's vector | `blob.animate.shift(2 * RIGHT)` → `(2.4 * RIGHT + 0.25 * DOWN)` |
| Placed inside the helper body only | edit inside the helper, **after confirmation** listing the other uses | `r.move_to(side * (...) + 0.4 * RIGHT)` |
| One axis set every frame by an updater | drag locked to the free axis; the locked axis is refused | fog: y only |
| During a morph or other non-still moment | not offered; drag at a still moment or a play's end | |

The drag's moment matters: dragging at time *t* changes where the object is
at *t*. If the object later moves with `.animate`, the later move is relative
(`shift`) or absolute (`move_to`); the planner says which in the preview
("moves from here on" vs "moves only until 0:04.2").

### 4.2 Scale and rotate (Phase 3)

Same ranking as moves, with `scale(k)` / `rotate(angle)`:
- existing literal `.scale(k)` → multiply: `.scale(0.8)` → `.scale(0.96)`;
- else chain `.scale(k)`; keep the object's centre (Manim's default) unless
  the user drags a corner handle with "scale about the opposite corner",
  which writes `about_edge=DL`;
- rotations are written in degrees: `.rotate(15 * DEGREES)`. An existing
  `PI / 2` literal is edited as `PI / 2 + 15 * DEGREES` only if the result
  isn't a round multiple of `PI / 12`, else rewritten as `PI / 3` etc.

### 4.3 Properties (inspector)

| Property | Where it's written |
|---|---|
| Constructor argument (`radius`, `font_size`, `color`, `stroke_width`, text content) | that keyword in the creating call; add the keyword if missing (after the last keyword argument, same line if it fits in 100 characters, else on its own line with the call's indentation) |
| Set later by a method (`set_color`, `set_fill`, `set_stroke`, `set_opacity`) | that call's argument |
| Neither | chain the setter on the creating call: `Circle(radius=1).set_fill(ACCENT, opacity=0.5)` |
| Constructor default being restored | remove the keyword (and its comma) |

Text content edits (`Text("...")`, `MathTex(r"...")`) keep the string's quote
style and raw prefix, and escape only what must be escaped.

### 4.4 Timing (timeline)

From S4. Assumes no `run_time=` on a `play()` that holds clips of different
lengths (the studio never writes one there).

| GUI edit | Code |
|---|---|
| Trim / stretch a clip | its `run_time=` keyword (on the animation if the play has several, else on `play()`); add it if missing |
| Move a group | its `self.at(t)` literal; in a sequential scene, the `self.wait(d)` before it (inserted if absent, removed when 0) |
| Move a clip within its group | `clip(anim, start=s)`; add `clip(...)` around it when it gets a delay; remove `clip()` when the delay returns to 0 and no `length` is set |
| Overlap clips from two groups | merge the two `play()` calls into one; the later clip gets `start=` |
| Separate overlapping clips | split the `play()`; the moved part gets its own `self.at(t)` (or `wait`) |
| Easing | `rate_func=` keyword (`smooth` is the default: removing the keyword restores it) |
| Ripple | edit every later `at()` literal by the same amount, one edit each, as one undo step |
| Reorder (Phase 4) | move whole statements; only within one block, and only when no statement in between reads a name the moved one assigns |
| Move a narration line | the `at()` before its `with self.say(...)` / `self.line(...)`; the GUI shows the real start (lines never overlap) |

`clip()` lives in `manim_kit.py`:

```python
def clip(anim, start=0.0, length=None):
    """An animation placed on its play()'s local timeline."""
    if length is not None:
        anim.run_time = length
    return Succession(Wait(start), anim) if start else anim
```

### 4.5 Adding from the library (Phase 3)

A drop on the canvas at time *t*:
1. A creation statement in the scene's `construct()`, inserted after the last
   statement that runs before *t* and at the same indentation, named after the
   class (`circle`, `circle_2`, ...):
   `circle = Circle(radius=1, color=ACCENT).move_to(1.6 * LEFT + 0.8 * UP)`.
   Positions snap to `place()` regions or `grid_point()` when dropped on a
   guide: `place(Text("..."), "title")`.
2. An entrance: `self.play(FadeIn(circle), run_time=0.8)` at *t*, using the
   preset chosen in the library (`Create`, `Write`, `FadeIn`, `GrowFromCenter`).
3. Imports: if the class is from `manim_kit` or `style` and the file doesn't
   import it, add `from manim_kit import *` after the last import.

### 4.6 Delete, duplicate, group (Phase 3)

- **Delete an object:** remove its creation statement and every statement
  that only uses it (adds, plays with it alone). If any other statement reads
  it (`next_to(circle, ...)`), refuse and list those lines.
- **Delete a clip:** remove the animation from its `play()`; remove the
  `play()` if it is empty.
- **Duplicate:** `circle_2 = circle.copy().shift(0.5 * RIGHT)` plus its own
  entrance.
- **Group:** `group = VGroup(a, b)` after the later of the two creations.

## 5. Tier-2 overrides

PLAN.md open question: how should an override read so it stays obvious? Answer:
**as an ordinary statement right after the code that made or placed the
object, using the shortest name that reaches it**. No comments or markers.

```python
dots = VGroup(*[Dot(p) for p in points])
dots[2].set_color(ACCENT)          # override from the inspector
dots[2].shift(0.3 * UP)            # override from a drag
```

- Two overrides of the same object and kind merge into one statement.
- An override that becomes a no-op is deleted (round-trip rule 5).
- Inside a loop, an override for one iteration would need a condition, which
  is tier 3. The studio doesn't write that; it offers "edit the loop for all
  items" (edit the literal inside the loop body) or "change only this one"
  (an override after the loop, by index).

## 6. Generated-code style

Code the studio writes from scratch (new scenes, library drops) follows the
repo's CLAUDE.md rules, so GUI-made and hand-made scenes look the same:

```python
from manim import *
from manim_kit import *
from style import *


class NewScene(TimedScene):
    VOICE = None          # set a voice to narrate

    def construct(self):
        title = place(Text("Order matters", font_size=TITLE_SIZE, color=FG), "title")
        square = Square(side_length=2, color=ACCENT).move_to(1.5 * LEFT)

        self.at(0.5)
        self.play(Write(title), run_time=1.0)
        self.at(2.0)
        self.play(
            Create(square, run_time=1.0),
            clip(square.animate.shift(3 * RIGHT), start=0.6, length=1.2),
        )
        self.at(5.0)
```

- New scenes subclass `TimedScene` (S4): absolute `at(t)` anchors.
- Objects first, then the timeline. One blank line between.
- Explicit `run_time=` on every animation the studio writes.
- Palette names and sizes from `style.py`; regions via `place()`.
- Names: lowercase class name, numbered on clashes.
- Line length up to 100 characters; longer calls break after `(` with one
  argument per line, indented 4 more.

## 7. What the studio never does

- Rewrite or reformat code it doesn't need to touch.
- Turn tier 2 or 3 code into tier 1 ("simplify") without being asked.
- Edit `style.py`, `manim_kit.py` or another imported module from a canvas
  drag. (Changing the palette is an explicit action in the inspector, with
  the file named.)
- Add `run_time=` to a `play()` holding clips of different lengths.
- Write while the file has a parse error, or write a result that doesn't
  parse.
