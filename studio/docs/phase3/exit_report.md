# Phase 3 exit report: direct manipulation

Date: 2026-11-18. Verdict: **Phase 3 is done.** Both exit criteria are
met: a scene built from a blank file without typing code, and 91.0% of
on-screen objects drag-editable and verified (corpus 91.7%, repo-video
sample 87.5%). The margin over 90% is small; every miss is listed in
section 2.

## 1. What was built

- **Move recording** (`server/engine/moves.py`): every positioning, scale
  and rotate call on a mobject records the scene-file call behind it and
  how (static, `.animate`, updater, laid out by `arrange`, moved by a
  running animation). `Transform(a, b)` remembers `b` on `a`; groups the
  scene makes but never adds (`pair = VGroup(a, b)`) are remembered on
  their members, so they can be selected and moved. Copies start with no
  history. Objects report `center`, `size`, a reference point `p0` and a
  `placement` record; the model reports the frame size in scene units.
- **Move / scale / rotate planner** (`server/code/moves.py`): ranked
  candidates per code_spec §4.1–4.2: edit a literal vector, merge into a
  chained `.shift()`, chain on the placing call, this use of a helper (a
  helper that returns a tuple gets `name.shift()` on a new line), override
  `group[i].shift()` after the group's last placement, edit the `.animate`
  vector, and last, edit inside the helper or loop with confirmation. A
  term or call that returns to zero is removed; a coefficient that returns
  to one is written as the bare name (`UP`), so a drag and a drag back
  restore the bytes.
- **edit.move / scale / rotate** (`project.py`): each candidate is
  replayed in one worker run and measured at the same frame (centre within
  0.011, reference point within 0.022, size for scale); a parent's scale is
  calibrated once; other objects the edit moves are reported
  (`also_moves`). Refused while the object or a group it is in animates
  (the last frame of a `play()` counts as its end).
- **Tier-2 overrides**: drags of one object out of a loop, comprehension or
  helper-made group become `group[i].shift(...)` on a new line; property
  edits there are previewed with both choices, **Only this one**
  (`dots[1].set_color(RED)`, `set_fill(opacity=...)`, `set(...)`) and
  **Every one** (the edit inside the loop).
- **Library** (`server/code/inserts.py`): 12 shapes (incl. kit `Blob`), 7
  entrances, 9 presets. A drop writes a creation statement and an entrance
  at the playhead: in a `TimedScene` with `self.at(t)`, in a sequential
  scene after the statement that ends before the playhead, splitting a
  literal `wait()` so later clips keep their times. `place(..., region)`
  when dropped on a region; `style.py` names when the file imports it.
  **New file** from the code_spec §6 template.
- **Delete, duplicate, group, delete clip**: delete removes the creating
  statement and every statement that only uses the object, and refuses
  (naming the line) when other code reads it; duplicate writes
  `x_2 = x.copy().shift(...)` with an entrance; group writes
  `group = VGroup(a, b)` after the later creation.
- **UI** (`web/src`): selection box with move, corner-scale and rotate
  handles; the object's own pixels (cut out with the ID map) follow the
  mouse with the old spot dimmed, so a drag needs no engine until release;
  snapping (centres to the frame centre, `REGIONS` centres and
  `grid_point` cells; edges to the safe area and to other objects' edges;
  centres to other objects' centres) with pink guides; Shift locks an axis,
  Alt turns snapping off (and gives 1° / 0.01× steps); readout of Δx Δy, ×k
  or degrees. Library tab (drag or click); New file; Delete, Ctrl+D,
  Ctrl+G, Ctrl+Y; Shift-click multi-select; Alt-click selects the parent
  group; a click on a part made inside library code (a glyph of a `Tex`)
  selects its owner; Layers as a tree; typed x / y / scale / turn in the
  Inspector; Duplicate / Group / Delete buttons; previews show
  `also_moves` and the "only this one" choice.
- **Protocol**: "Added in Phase 3" in [protocol.md](../protocol.md).

## 2. Exit criteria

| Criterion | Result |
|---|---|
| A short scene built from a blank file without typing code, reading like hand-written Manim | Done twice: by `test_build_a_scene_from_a_blank_file` (engine test: drop a square and a title, drag, scale, rotate, Indicate, duplicate, group; every statement written is census tier 1; undo returns the template bytes) and by hand in the browser pane (section 3) |
| ≥ 90% of on-screen objects drag-editable, verified (corpus.md §4) | **Met: 212 / 233 = 91.0%** (table below) |

Measured by `studio/tests/drag_run.py`. For each scene it takes a still
frame after the last animation and drags every on-screen object that a
user can pick (its owner, not a glyph inside a `Tex`) by (0.5, 0.3).
The edit has to be written and pass verification by replay. Then it
drags the object back and checks that the file bytes are as before.

| Set | Objects | Drag verified | Drag back byte-identical |
|---|---|---|---|
| Corpus (`studio/tests/corpus`, plus `tools/fixtures`) | 193 | 177 (91.7%) | 176 |
| Repo videos, sample (`order_matters.py`, `pythagoras.py`) | 40 | 35 (87.5%) | 35 |
| **Combined** | **233** | **212 (91.0%)** | 211 |

The corpus was rerun on the final code (`drag_report_corpus_final.json`).
The repo files were run after the last planner change
(`drag_report_order_matters_2.json`, `drag_report_pythagoras_2.json`). The
repo-video run was stopped after these two files (the user's call), so
`gradient_descent.py`, `eola_*` and the rest are not measured. Two corpus
scenes that crash on purpose (`broken_runtime`, `late_error`) are skipped.
Reports are in `studio/tests/tmp/`.

There are 21 failed drags and 1 failed drag back. None of them writes a
wrong edit: each one is refused, or the replay rejects it, and the file
is left as it was.

- **Position set every frame by an updater** (6): the `dynamic.py`
  readout, and dots in `SineCurveUnitCircle`, `MovingDots` (2),
  `ArgMinExample` and `PolygonOnAxes`. The studio refuses these and names
  the updater line.
- **Position set later by an animation or a redraw**, so a shift at
  creation doesn't hold (7): `MovingAngle` and `MovingDots` lines,
  `MovingGroupToDestination` and `PointWithTrace`, the `timing.py`
  square, and dots placed only by `MoveAlongPath` in `PointMovingOnShapes`
  and `FollowingGraphCamera`.
- **Re-laid-out after placement** (3): two `CompareMatrices` matrices
  re-placed by `arrange`, and a `pythagoras` `Squares` square whose helper
  result is placed again.
- **`ClippedGrid`, which holds a mobject but is not one** (4): `kit_parts`
  (2) and `order_matters` (`RotateThenShear`, `Takeaway`).
- **Non-linearly transformed `NumberPlane`** (1): `OpeningManim`.
- **Drag back not byte-identical** (1): the `BooleanOperations` title.
  The drag verifies, but it also moves `ellipse1` and `ellipse2`, and the
  way back is written differently.

Fixes made while measuring:
- coefficients within 0.001 of 0 or ±1 snap (`SNAP`), so calibrated
  drags back leave no `0.0003 * UP` residue;
- `.shift` can chain onto an `.animate…next_to()` builder;
- a new shift goes at the end of the method chain (`helper().next_to(...)`);
- a new `x.shift(...)` line merges into the one a previous drag wrote;
- the last frame of a `play()` counts as its end, not as "animating";
- drags start from the owner of a part made in library code.

## 3. Browser check (the built UI, in the pane)

New file `tmp_studio_demo.py` from the button, then without typing code:
Square from the Library at 1 s → `square = Square(side_length=2, color=ACCENT)`
with `self.at(1)` / `self.play(Create(square), run_time=0.8)`; a drag of
two units → `.shift(2 * LEFT)`; the corner handle → `.scale(1.5)`; the
rotate handle → `.rotate(30 * DEGREES)`; Ctrl+D →
`square_2 = square.copy().shift(0.5 * RIGHT + 0.5 * DOWN)` with a FadeIn;
Shift-click + Ctrl+G → `group = VGroup(square, square_2)`; Alt-click
selected the group and a drag moved it (`.shift(2 * RIGHT + 0.1 * UP)`, the
0.1 from snapping its centre to the `main` region line); a Circle dropped
from the Library; Indicate on the group; Delete on the circle removed it
and its `Create`. Undo all the way: the file was byte-identical to the
template. No server errors. The test file was deleted afterwards.

Bugs found and fixed during the check: `file.new` was refused with "file
not open" (routed after the open-file check); a box edge (stroke included)
snapped to a region centre line and wrote `0.8667`; Shift-click selected
page text; Shift- or Alt-drag on a member of a selected group moved the
member alone.

Recheck after the measuring fixes, on a small scratch scene
(`tmp_recheck.py`, deleted afterwards):
- a click on the `MathTex` selected `eq`;
- a Shift-drag on a member of the selected `pair` moved the group on one
  axis and wrote `pair = VGroup(a, b).shift(2 * RIGHT)`;
- setting RED on the middle dot of a comprehension opened the preview
  with Cancel / Only this one / Every one, and **Only this one** wrote
  `dots[1].set_color(RED)` on a new line.

Picking the owner of a glyph wasn't exercised in the browser, because
that `MathTex` is a single drawn object. The drag bench covers it.

## 4. Tests

- Unit: 132 (vectors in every written order, zero removal, unit
  coefficients, angles, scales, helpers, tuples, layouts, loops,
  comprehensions, overrides for moves and properties, inserts, presets,
  duplicate, group, delete, delete clip, new file and its guards).
- Engine (`test_phase3.py`): blank-file build, drag-and-back on every
  object in `helpers.py`, mid-animation refusal, "only this one" property
  override.
- Full studio suite after all changes: **148 passed** (3 min 15 s).
- Drag bench: `studio/tests/drag_run.py [filter] [--max N]` (section 2).
  It isn't part of pytest because it is slow. Its scratch copies live in
  `studio/tests/tmp/`, which the file list hides (`HIDDEN_DIRS`) and
  pytest ignores.

## 5. Gaps and decisions carried forward

- The drag limits in section 2. The biggest group that could still be
  fixed is "set later by an animation" (7): the planner could edit the
  animation's target instead of the creation. Giving `ClippedGrid` a
  `shift` in `manim_kit.py` would fix 4 more. The repo-video drag measure
  covers two files only; run the rest when the machine is free.
- `PI/12`-style angle rewrites were not built; rotations add `+ n * DEGREES`
  terms instead, which round-trip exactly.
- `RIGHT / 2` dragged away and back comes back as `RIGHT * 0.5` (same
  value); a hand-written `1 * UP` comes back as `UP`.
- Kit objects that hold a mobject but are not one (`ClippedGrid`) can't be
  dragged: `.shift()` can't chain on them. The replay refuses it; nothing
  is written.
- Moves inside a loop offer the override first; "every pass of the loop"
  for a move is not offered as a second choice (it is for properties).
- The Inspector lists a `VGroup`'s `*vmobjects` as an editable argument
  (cosmetic).
- A `TimedScene` showed 4.93 s instead of its 5 s `TARGET` after a
  duplicate (74 frames instead of 75): frame rounding in the kit's padding,
  not checked further.
