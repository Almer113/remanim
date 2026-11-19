# Phase 5 plan: coverage

PLAN.md §5, Phase 5: LaTeX and text editing with part-level colouring.
Graphs and axes. Transform and matching-transform pairs. Camera moves. 3D
scenes (camera gizmo, projected handles). Presets. More tier-1 and tier-2
patterns, driven by the census.

**Exit** (corpus.md §4, measured on all three parts of the corpus):

| Measure | Target | Baseline today |
|---|---|---|
| Files that open and play | 100% (`broken_*` read-only) | 100% (corpus run, 2026-11-19) |
| No-op save byte-identical | 100% | 100% |
| Statements tier 1 or 2 (census) | ≥ 95% | **93.0%** (1,681 statements; repo 94.6%, awkward 94.0%, gallery 87.6%, fixtures 90.9%) |
| On-screen objects drag-editable, verified | ≥ 95% | **91.0%** (212 / 233); repo videos only half measured |
| Timeline clips retimable | ≥ 98% | not measured as a share yet (step 1) |

Plus one hands-on check per feature in the browser pane, as in Phases 3
and 4.

Rules: code_spec.md §1 (byte splices, verify by replay, round trips
close), §2 (tiers), §4 (where each edit is written).

## What exists today

- **Text:** the Inspector edits a `Text("...")` / `MathTex(r"...")`
  string as a constructor argument (quote style and raw prefix kept). A
  click on a glyph selects the whole owner. Nothing knows which glyphs
  come from which part of the TeX. Only one file in the corpus colours
  parts of a formula (`t2c`, `set_color_by_tex`, `{{ }}`), but four index
  into formulas by hand (`eq[0][3:5]`, 25 places).
- **Graphs:** `Axes`/`NumberPlane` are ordinary objects (drag, scale,
  constructor numbers). `axes.plot(lambda x: ...)` is tier 3 because of the
  lambda, so the curve can't be edited, and a dot placed with
  `axes.c2p(2, 4)` is dragged in scene units (a `.shift()`), not in the
  graph's own coordinates.
- **Transforms:** `Transform(a, b)` remembers `b` on `a` for moves (Phase
  3). The timeline shows the clip, but not what goes where. The target `b`
  can't be selected, because it is never on screen.
- **Camera:** `MovingCameraScene` and `ThreeDScene` files play.
  `self.camera.frame.animate...` and `move_camera(...)` are ordinary
  clips. The camera itself isn't an object you can select.
- **3D:** objects in 3D scenes are dragged by a 2D shift in scene units.
  That checks out in the drag bench, but a mouse drag under a rotated
  camera doesn't map to the right 3D vector. There are no 3D handles.
- **Presets:** the Library has 12 shapes, 7 entrances and 9 animation
  presets (Indicate, Circumscribe, ...), each a single statement.
- **Drag misses** (Phase 3 exit, 21): set every frame by an updater (6,
  correctly refused); placed later by an animation or a redraw (7);
  re-laid-out after placement (3); `ClippedGrid` (4); a non-linearly
  transformed `NumberPlane` (1).
- **Carried from Phase 4:** a no-op `at()` anchor can be left behind after
  a move; the TTS cache isn't safe across processes (decision below).

What the tier-3 statements are (all corpus files, 118): conditions and
conditional expressions 29, lambdas 26 (updaters, `always_redraw`, but
also `axes.plot(lambda x: x**2)`), nested `def` 18, `add_updater` 15,
`for` loops 14 (several over a named constant), `always_redraw` 4, other
12.

## Steps

Grouped in five milestones. Each ends with tests green and a short note
in the exit report, and is a natural point to commit.

### 5a. Measure, then the cheap wins

| # | Piece | Where | Checked by |
|---|---|---|---|
| 1 | **Full baseline.** Finish the drag bench on the repo videos it skipped (`gradient_descent.py`, `eola_preview.py`, fixtures). Add a **retimable-clip share** to the corpus run: every `play()`/`wait()` clip is planned with a +0.1 s trim, and the edit is classed as planned or refused (with the reason). One in five planned edits is replayed and verified, and every refusal is listed. A census report over the whole corpus, with tier-3 lines grouped as above. All three go in `docs/phase5/baseline.md`. | `tests/drag_run.py`, `tests/corpus_run.py`, `tests/census_run.py` (new) | the reports themselves |
| 2 | **Census patterns that the GUI can really edit** (only with an editor behind them, never a count-only change): a conditional expression (`0.7 if k < 3 else 0.45`): each branch's literals are editable, the condition read-only → tier 2. A `for` loop over a named constant or a literal list → tier 2 (the list is edited where it is defined). Lambdas passed to `plot`/`FunctionGraph`/`ParametricFunction` → tier 2 via step 7. | `code/census.py`, `code/planner.py` | unit tests: each pattern edits and round-trips |
| 3 | **Drag misses that have a rule:** an object placed later by an animation (`MoveAlongPath`, `.animate.move_to(...)`, a `Transform` target): the drag edits the animation's target, with the creation untouched (ranked after the current candidates). `ClippedGrid`: `.shift()` is added to the kit class (moves its box, its grid and its stand-ins), so the planner's normal chain works. A re-layout by `arrange`: refuse with the `arrange` line, or offer `buff=`/order (§ decisions). No-op `at()` anchors left by a move are removed in the same edit. | `code/moves.py`, `manim_kit.py`, `code/timeline.py` | drag bench rerun; unit tests; `kit_parts.py` |

### 5b. Text and LaTeX

| # | Piece | Where | Checked by |
|---|---|---|---|
| 4 | **Spike S6, glyphs ↔ TeX source.** For a `MathTex`/`Tex`, which glyph indices come from which characters of which string. Manim splits the TeX into parts (one per argument, `{{ }}`, `substrings_to_isolate`, `tex_to_color_map`) and compiles each part separately. Inside a part, there's no character map. The spike measures whether isolating a candidate substring and comparing glyph counts (Manim's own method) is reliable on the 107 `MathTex`/`Tex` calls in the corpus, and how fast it is (each try is one LaTeX compile, ~0.3–1 s, cached). Go / no-go for step 6. | `spikes/s6_tex_parts.py`, `docs/phase0/S6_tex_parts.md` | the spike report |
| 5 | **Edit text in place.** Double-click a `Text`/`MathTex`/`Tex`/`MarkupText` on the canvas → an editor over it with the source string (raw TeX for maths). Enter → the same splice as the Inspector. The new frame comes from the engine (LaTeX compiles in the worker), and a TeX error is shown with LaTeX's own message and refused, leaving the file unchanged. `font_size` and alignment in the Inspector. Strings built from f-strings or concatenation are tier 2: only their literal pieces are editable, and the editor says so. | `code/planner.py`, `web/src` (new `TextEditor.tsx`) | unit tests (quotes, raw strings, `\\`, braces, non-ASCII, f-string pieces); engine test with a TeX error; browser pane |
| 6 | **Part-level colour.** Drag across glyphs (or click one part) → a colour from the palette. **`Text`:** write `t2c={"word": C}` (doesn't change the glyph structure). **`MathTex`, part already isolated** (an argument, `{{ }}`, `substrings_to_isolate`): `eq.set_color_by_tex(...)`, or `eq[i].set_color(C)` on a new line. **Not isolated:** add `{{ }}` around the substring in the string, but only when no later code indexes the formula (`eq[0][3:5]`, `TransformMatchingTex` partners). Otherwise write `eq[0][a:b].set_color(C)` on a new line, the same "only this one" override as Phase 3. Every result is verified by replay: the coloured glyphs must be exactly the selected ones, and nothing else changes colour. | `code/tex.py` (new), `engine/runtime.py` (glyph → part map in the model) | unit tests; engine tests on `pythagoras.py` copies; browser pane |

### 5c. Graphs and transforms

| # | Piece | Where | Checked by |
|---|---|---|---|
| 7 | **Graphs.** Axes in the Inspector: `x_range`/`y_range` (min, max, step), `x_length`/`y_length`, axis labels and number labels (`include_numbers`, `add_coordinates`). **Curves:** a lambda passed to `plot` / `plot_parametric_curve` / `FunctionGraph` / `ParametricFunction` is shown as an expression of its argument (`t * t`) with its `x_range`. Editing the expression is checked before writing (it must parse as one expression of that argument, using only names already in scope or from `numpy`/`math`) and verified by replay (the curve renders, no exception). **Points on a graph:** an object placed with `axes.c2p(x, y)` / `coords_to_point` / `input_to_graph_point(x, curve)` is dragged in graph coordinates: the drag edits `x, y` (or `x` on the curve), snapped to the axes' step. Area/Riemann helpers: their `x_range`/`dx` in the Inspector. | `code/graphs.py` (new), `code/moves.py`, `web/src` | unit tests; engine tests on `plotting_with_manim.py` and `gradient_descent.py` copies; drag bench |
| 8 | **Transform pairs.** Selecting a `Transform`-family clip shows source → target on the canvas: the target's end state as a ghost at the clip's last frame, selectable and draggable (its edits go to the code that makes or places the target). The Inspector switches the kind (`Transform` / `ReplacementTransform` / `FadeTransform` / `TransformFromCopy`), keeping the arguments, and refuses when later code relies on the difference (after `Transform(a, b)`, `a` is on screen, not `b`). **`TransformMatchingTex`/`Shapes`:** the matched parts are shown in pairs of colours, and unmatched parts fade. A "match these" action isolates the same substring with `{{ }}` in both formulas (step 6's rules), or writes `key_map=`. | `code/transforms.py` (new), `engine/runtime.py`, `web/src` | unit tests; engine tests on `transforms.py`, `test_scene.py`; browser pane |

### 5d. Camera and 3D

| # | Piece | Where | Checked by |
|---|---|---|---|
| 9 | **2D camera** (`MovingCameraScene`). The camera frame is an object in Layers ("Camera"). Out of camera view (a toggle that shows the whole scene with the frame drawn on it), it can be moved and resized with handles. A drag at a time when no camera clip is running edits the last `self.camera.frame.animate.move_to(...)` / `.set(width=...)` / `.scale(...)` before that time. With none, it inserts a camera move at the playhead (like a preset). Saved and restored frames (`save_state`/`Restore`) are shown but read-only. `ZoomedScene` stays read-only. | `code/camera.py` (new), `engine/runtime.py` (frame state in the model), `web/src` | unit tests; engine tests on `camera.py` `Zoom` and gallery `FollowingGraphCamera`; browser pane |
| 10 | **3D camera gizmo.** A small orbit widget (phi, theta, zoom, focal distance) drawn in a corner of the canvas in 3D scenes. Dragging it edits the `set_camera_orientation(...)` before the playhead, or the `move_camera(...)` clip under it, in `DEGREES` as the file writes them. `begin_ambient_camera_rotation(rate=)` in the Inspector. The camera-continuity rule from CLAUDE.md (end an orbit where the next beat starts) becomes a warning when a scene's starting angle differs from the previous scene's last angle. | `code/camera.py`, `web/src` (new `OrbitGizmo.tsx`) | unit tests; engine tests on `camera.py` `Orbit` and `gradient_descent.py` 3D beats; browser pane |
| 11 | **3D handles.** The engine sends each selected 3D object's centre and the screen direction of the x, y and z axes at that frame (the camera's projection). The canvas draws three axis arrows on the object. Dragging the body moves it on the plane of the two axes facing the camera most; dragging an arrow moves along that axis. The drag becomes a `shift(a * RIGHT + b * UP + c * OUT)` (the 2D planner's rules with a third term) and is verified by replay in 3D coordinates. Screen-pinned text keeps today's 2D drag. | `engine/runtime.py`, `code/moves.py`, `web/src` | unit tests (3-term vectors); engine test: drag on a rotated camera lands where the mouse is (within 2 px); browser pane |

### 5e. Presets, then the exit check

| # | Piece | Where | Checked by |
|---|---|---|---|
| 12 | **Composite presets** in the Library: several statements written as one insert, with one undo step, each reading like hand-written code: axes with a curve and a label; a number line with a moving dot (`ValueTracker`, the only updater the studio writes, from a fixed template); a labelled vector; a brace with a label; an equation reveal (`TransformMatchingTex` from one formula to the next); a title card (`place(..., "title")` + subtitle); a highlight box (`SurroundingRectangle` + `Create` + `FadeOut`); a 3D surface with axes (3D scenes only). | `code/inserts.py`, `web/src` | unit tests (each preset's code is census tier 1–2 and round-trips); blank-file build test extended |
| 13 | **Exit check:** the corpus run (all files play, no-op byte-identical), the census, the drag bench and the clip share against the targets above. A hands-on pass in the browser pane: edit a formula and colour a part in a `pythagoras.py` copy, change a curve and drag a point on it in `plotting_with_manim.py`, move the camera in `camera.py`, orbit and drag in a 3D beat of `gradient_descent.py`, build a short scene from presets. Then the exit report. | `docs/phase5/exit_report.md` | |

Rough sizes: 5a M, 5b L (most of the risk is in S6), 5c L, 5d L, 5e M.

## Decisions taken here (unless you say otherwise)

- **A tier changes only when there is an editor behind it.** Step 2 doesn't
  reclassify lines to reach 95%. A pattern moves to tier 2 only when the
  GUI can edit it and the round trip closes. If the corpus still lands
  under 95% after step 7, the exit report says so and lists what's left.
  The target is not lowered quietly.
- **Updaters, `always_redraw` and nested `def`s stay tier 3** (code,
  read-only, "open in editor"). The one exception is the number-line
  preset in step 12, which writes a fixed, tested template.
- **Part colouring prefers the form that doesn't restructure the
  formula.** `{{ }}` is added only when nothing later indexes the formula.
  Otherwise it falls back to an index override on a new line. A user
  never gets a colour edit that silently shifts `eq[0][3:5]` to different
  glyphs: the replay checks the exact glyphs.
- **No new npm packages.** The TeX editor previews by asking the engine,
  not by KaTeX in the browser. That costs a LaTeX compile per preview
  (~0.3–1 s, cached), but it's exactly what the render will look like. If
  that turns out too slow in 5b, I'll ask before adding KaTeX.
- **Expressions typed by the user (curves in step 7) are code** and are
  treated as such: they must parse as one expression, may use only names
  already in scope or from `numpy`/`math`, and are verified by replay
  before writing. No `eval` in the server: the worker runs the file, as it
  does today.
- **3D drags default to the plane that faces the camera most**, with
  arrows for single axes. The alternative, always the floor (x–y), is
  simpler but fights the camera when it looks from the side.
- **`ZoomedScene`, saved camera states and `ThreeDScene` light sources
  stay read-only** in this phase. They're rare in the corpus (one gallery
  scene each).
- **`manim_kit.py` gets one change:** `ClippedGrid.shift()` (and
  `move_to`) in step 3, with a fixture check, as with `clip()` in Phase 4.

## Decided (2026-11-19)

All three as recommended: the TTS cache gets a file lock in 5a;
`arrange` re-layouts are refused with a clearer message (an `arrange`
edit only if the bench shows it's common); milestones run 5a → 5e.

## The questions as asked

1. **TTS cache across processes** (carried from the Phase 4 review): two
   studio workers synthesising the same new line at once can both write
   `media/voiceovers/`. The fix is a file lock in `edge_tts_service.py`,
   which the videos share. It changes nothing about how they render. Do it
   in 5a, or leave it?
2. **`arrange` re-layouts** (step 3): when a drag hits an object that a
   later `arrange()` puts back, refuse (today, naming the line), or offer
   to edit the `arrange` (`buff=`, direction, or the order of the group)?
   I'd start with the refusal plus a clearer message, and offer the
   `arrange` edit only if the bench shows it's common.
3. **Order of the milestones.** Planned 5a → 5e. If you'd rather see
   text and LaTeX first (most visible for the videos), 5b can go straight
   after step 1.
