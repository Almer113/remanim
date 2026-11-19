# Phase 5: measurements and progress (2026-11-19)

Benches run one at a time on the current code, after the full test suite
(`pytest studio/tests`: all passed). Reports in `studio/tests/tmp/`:
`clip_report_5a.json`, `drag_report_5a.json`, `corpus_report.json`,
`census_report.json`.

## Against the exit targets

| Measure | Target | Phase 4 baseline | Now | Notes |
|---|---|---|---|---|
| Census, tier 1–2 statements | ≥ 95% | 93.0% | **95.1%** (1,686 statements) | repo 96.7%, awkward 94.0%, gallery 90.0%, fixtures 91.8% |
| Drags that land | ≥ 95% | 91.0% | **92.7%** (179/193) | every moved object went back on undo |
| Retimable clips | ≥ 98% | not measured | **76.9%** (553/719) | 0 verify failures in 78 replayed edits |
| Every file plays, no-op edits byte-identical | all | all | **all** | see below |

The drag and clip numbers miss their targets. They aren't rounded up or
redefined here; what's left is listed below.

## Census (step 2)

Each rule that moved a pattern to tier 2 has an editor behind it (the
code peek's literal editing, `code/literals.py`):
- conditional expressions: each branch's numbers are editable;
- `for` over a literal list or a named constant: edited where the list is made;
- lambdas handed to `plot` / `FunctionGraph` / `ParametricFunction` and
  the other plotters: numbers editable, and the whole formula through the
  Inspector (step 7).

Still tier 3: updater 24, condition 21, nested `def` 20, `always_redraw` 9,
other 6, lambda 2, try/with 1. Updaters, `always_redraw` and nested defs
stay tier 3 by decision.

## Drags (step 3)

14 misses out of 193:
- 8: an updater positions the object every frame (tier 3 by decision).
  Without these, 179/185 = 96.8%.
- 3: an animation carries the object afterwards (`MoveAlongPath`, an
  `.animate` move worked out from other objects). Refused, naming the line.
- 3: a chain the planner tried but the replay disagreed (a `NumberPlane`, a
  `Line`, a `Dot` placed by computed points). Refused with what was tried.

Every refusal now says what puts the object back: an updater (with its
line), the animation that carries it, or a later `.animate`.
`ClippedGrid.shift()` / `move_to()` are in `manim_kit.py`, checked by
`tools/fixtures/kit_parts.py`. No-op `self.at()` anchors left by a timeline
edit are removed in the same edit.

## Clip share (step 1)

Of 719 clips:
- 553 retimable;
- 130 locked:
  - 103 "inside a helper". In `pythagoras.py` these are manim-voiceover's
    own end-of-block waits (narration timing, moved with Phase 4's voice
    edits). The rest are `Beat.fade_all`, `draw_path` and kit helpers, where
    one edit would change every use.
  - 27 timed by library code (`wait_until_bookmark`, `move_camera`).
- 36 refused. The biggest groups: `run_time=(0.6 if k < 2 else 0.35)` in a
  loop (10), `run_time=rt` with `rt` computed (9), `at(t)` with `t` computed
  in a nested loop (8). The code peek can still edit their numbers.

Not locked by design: 553/589 = 93.9%.

Two rules added while measuring, both verified by the replay:
- `at(t)` in a loop over a literal list (`for t, s in zip((5.5, 7.8), ...)`)
  edits that pass's number only;
- `at(a + 1.2)` / `at(self.TARGET - 0.6)`, a time relative to a spoken line,
  edits the offset only. This took `gradient_descent.py` from 74 to 104
  retimable clips.

## Corpus run

Every file loads and plays as before. The only errors are the ones the
corpus is built to have (`broken_syntax`, `broken_runtime`, `late_error`)
and `reference/source/chapter0.py`, which is ManimGL code.

The first run found one bad frame in `gradient_descent.py` `Takeaway`: an
empty Pango SVG in `media/texts/` ("no element found"). Manim writes that
file straight to its cache path, and the engine's cursor threads can build
the same `Text` at once. Fixed in `engine/runtime.py`:
- `Text` is now built one at a time per process;
- a zero-byte cache file is cleared and rebuilt.

The rerun had 0 bad frames.

`order_matters.py` `Question`: the colour edit is refused ("something later
sets it again"). That's correct: lines 92–95 recolour the formula's parts
after it is made.

## What was built after 5a

| Step | State | Checked by |
|---|---|---|
| 4. Spike S6 | go: 80/80 formulas, 1,021/1,021 glyphs (`docs/phase0/S6_tex_parts.md`) | spike report |
| 5. Edit text in place | done: double-click → editor over the object; several parts in one edit; a TeX error is refused with LaTeX's message | unit, engine, browser |
| 6. Part colour | done: Inspector "Colour part…", pick glyphs, pick a colour. Writes `t2c=`, `tex_to_color_map=` or `eq[i][a:b].set_color()`, best first; the replay checks the exact glyphs | unit, engine, browser |
| 7. Graphs | done: a curve's formula in the Inspector (checked names, replayed); Axes `x_range`/`y_range`/lengths, and `get_area` / `get_riemann_rectangles` ranges and `dx`, as fields; a point made with `axes.c2p(x, y)` / `n2p(x)` drags in axis units | unit, engine, browser |
| 8. Transform pairs | done: switch the kind in the clip Inspector (refused when later code uses what leaves the screen); with the clip selected, the canvas outlines where each transform goes and colours `TransformMatchingTex`'s matched parts in pairs; click two grey parts to match them (`key_map=`) | unit, engine, browser |
| 9. 2D camera | done: Camera fields, and "Move on canvas" (drag pans, wheel zooms, live preview). Frame 0 places the camera without a move; later it edits the last move or inserts one. **Open:** an out-of-camera view (seeing what lies outside the frame) | unit, engine, browser |
| 10. 3D camera | done: phi/theta/zoom fields and an orbit drag with an axis tripod; a warning with "Start here instead" when a 3D scene doesn't start where the scene before ends; ambient rotation rate as a field | unit, engine, browser |
| 11. 3D handles | partly: the engine reports each 3D object's axes on screen; a drag moves it on the world's x-y plane, checked by replay. Pinned text moves in screen space. **Open:** moving along z | engine |
| 12. Composite presets | done, including the 3D surface (ThreeDAxes + Surface coloured by height; refused outside a ThreeDScene) | unit (census tier, parse), engine (each one built, verified, undone) |
| 13. Exit check | done 2026-11-20: census and corpus met; drags 92.7% and clips 77.0% short (`exit_report.md`) | benches, suite |

Tests: 293 unit tests, 6 Phase 5 engine tests, and the earlier engine
suites all pass.
