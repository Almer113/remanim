# Phase 5 exit report (2026-11-20)

Phase 5 (coverage) is built. One of the three share targets is met. The
other two are short, and this report says by how much and why. It doesn't
round them up or redefine them.

## How it was measured

All runs were on the current working tree, one at a time, with no studio
server running:
- the full test suite: `pytest studio/tests`, 331 passed in 7 min
  (`tests/tmp/exit_pytest.log`), plus the area/Riemann engine test added
  after it, which passes on its own;
- the drag bench, `tests/drag_run.py` → `tests/tmp/drag_report.json`;
- the clip share, `tests/clip_run.py` → `tests/tmp/clip_report.json`;
- the corpus run, `tests/corpus_run.py` → `tests/tmp/corpus_report.json`;
- the census, `tests/census_run.py` → `tests/tmp/census_report.json`.

## Against the targets

| Measure | Target | Phase 4 | Exit | Met |
|---|---|---|---|---|
| Census, tier 1–2 statements | ≥ 95% | 93.0% | **95.1%** | yes |
| Drags that land, verified | ≥ 95% | 91.0% | **92.7%** (179/193; 178 back on undo) | no |
| Retimable clips | ≥ 98% | not measured | **77.0%** (560/727; 0 of 79 replayed edits failed) | no |
| Every file plays, no-op edits byte-identical | all | all | **all** (27 files) | yes |

The corpus run's only errors are the expected ones:
- `broken_syntax.py`, `broken_runtime.py` and `late_error.py` are broken on
  purpose;
- `reference/source/chapter0.py` is ManimGL code (`manim_imports_ext`).

No file had a bad frame, and every file's bytes were unchanged.

### Why the drags are short

There are 14 misses, unchanged since 5a:
- 8 objects are positioned every frame by an updater. Updaters stay tier 3
  by decision. Without them the share is 179/185 = **96.8%**.
- 3 objects are carried afterwards by an animation (`MoveAlongPath`, or an
  `.animate` move worked out from other objects). The drag is refused, and
  the message names the line.
- 3 are chains the planner wrote but the replay disagreed with (a
  `NumberPlane`, a `Line`, and a `Dot` placed by computed points). These
  are refused with what was tried.

The Phase 5 graph and 3D drags don't change the bench: its objects were
already dragged by a scene-unit `.shift()`. What changed is how they move.
Engine tests check that:
- a point made with `axes.c2p` moves in graph units;
- a 3D object moves on the world's x-y plane under a rotated camera.

### Why the clip share is short

Of 727 clips:
- **131 are locked**:
  - 104 are inside a helper. Most are manim-voiceover's end-of-block waits,
    which follow the narration. The rest are `fade_all` and kit helpers,
    where one edit would change every use.
  - 27 are timed by library code (`wait_until_bookmark`, `move_camera`).
- **36 are refused** because the time is computed (`0.6 if k < 2 else
  0.35`, `rt`, `at(t)` inside a nested loop). The code peek can still edit
  their numbers.

Leaving out the clips that are locked by design, the share is 560/596 =
**94.0%**.

The 98% target was set before the share had ever been measured. On these
files it can only be reached by retiming helper and library waits, and
that would change every use or fight the narration. The measured figure
should replace that guess (see "Suggested decisions").

## What Phase 5 built

| Step | Result |
|---|---|
| 1. Baseline | drag, clip and census benches over the whole corpus |
| 2. Census | 93.0% → 95.1%: conditional branches, loops over literal lists, plotted lambdas |
| 3. Drag rules | animation targets; `ClippedGrid.shift()`/`move_to()` in the kit; no-op `at()` anchors removed; `arrange` re-layouts refused with the line |
| 4. Spike S6 | go: 80/80 formulas, 1,021/1,021 glyphs |
| 5. Text in place | double-click to edit; a TeX error is refused with LaTeX's message |
| 6. Part colour | `t2c=` / `tex_to_color_map=` / `eq[i][a:b].set_color()`; the replay checks the exact glyphs |
| 7. Graphs | Axes ranges and lengths; a curve's formula; area and Riemann `x_range`/`dx`; `c2p`/`n2p` points drag in axis units |
| 8. Transforms | switch the kind; on the canvas, the target outline and the matched pairs of a `TransformMatchingTex`; click two parts to write `key_map=` |
| 9. 2D camera | fields, plus "Move on canvas" (drag pans, wheel zooms). At frame 0 the camera is placed without a move (the line already there is edited); later, the last move is edited or a 1 s move is inserted |
| 10. 3D camera | phi/theta/zoom fields; an orbit drag with a tripod; a warning with "Start here instead" when a scene doesn't start where the previous one ended; ambient rotation rate |
| 11. 3D handles | per-object screen axes from the engine; a drag on the world's x-y plane, verified by replay |
| 12. Presets | composites read like hand-written code; a 3D surface preset (refused outside a `ThreeDScene`, and it tilts the camera only if the scene has none) |

### Hands-on pass in the browser pane

These were checked in the browser pane, each one undone afterwards:
- formula edit and part colour (5b);
- curve formula and area fields;
- the transform ghost with its matched pairs, and "match these" writing
  `key_map=`;
- 2D camera pan (`move_to(3.54 * RIGHT + 0.72 * DOWN)`) and wheel zoom;
- the 3D continuity warning and "Start here instead" (phi 70, theta −45);
- ambient rate 0.25;
- an orbit drag (theta −67.4).

The pane was hidden for part of the session, so these checks used page
refs and JS state rather than screenshots. The step 13 pass in the plan
covers all of this except dragging a point in `plotting_with_manim.py` and
dragging an object in a 3D beat. Both of those have engine tests, not a
browser check.

## Open, carried to Phase 6 or later

- **Moving along z** in 3D. The drag only works on the x-y plane; an axis
  arrow drag along `OUT` isn't built.
- **An out-of-camera view** for 2D cameras: the whole scene with the frame
  drawn on it.
- **Drags:** the 6 non-updater misses. The two kinds can be fixed by
  editing the carrying animation's own target, and by better chains for
  computed points.
- **Clips:** the 36 computed times. One possible rule: edit the number
  inside a conditional `run_time`, as the census already does.

## Decisions (accepted by the user, 2026-11-20)

1. Accept Phase 5 as done, with the drag share stated as 92.7% overall and
   96.8% without updater-driven objects.
2. Change the clip target to "≥ 95% of clips not locked by design". It is
   94.0% now; the computed-time rule above would pass it.
