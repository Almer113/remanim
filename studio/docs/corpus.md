# Compatibility corpus

The files every phase is measured against (PLAN.md: "every file plays, and
the editable share meets the target"). Three parts.

## 1. This repo's videos (real use)

| File | Scenes | What it exercises |
|---|---|---|
| `test_scene.py` | 1 | the minimal case; `TransformMatchingTex` |
| `pythagoras.py` | 5 | manim-voiceover `Beat`, bookmarks, braces, LaTeX |
| `order_matters.py` | 5 | `TimedScene`, kit parts (Blob, bubbles, `ClippedGrid`), helpers, arranged groups |
| `gradient_descent.py` | 9 | 2D and 3D, surfaces, contour maps, images, updaters, tuple-returning helpers |
| `eola_preview.py` | ~20 | recreation layer (`eola_common`), 2016-style sizes, pyramids, bubbles |
| `tools/fixtures/*.py` | – | deliberately bad layout; kit smoke tests |

Read only. The studio's tests never write to these files: edit tests copy
them to a temp folder first.

## 2. Awkward files (`studio/tests/corpus/awkward/`)

Small scenes written to break naive tools. All traced with the spike engine
on 2026-11-18 (results below).

| File | Scenes | The trap |
|---|---|---|
| `formatting.py` | Formatting | comments everywhere, odd spacing, two statements on one line, backslash continuation, trailing commas, unicode, raw strings, a numpy vector literal |
| `helpers.py` | Helpers | comprehensions, a helper used twice, a helper returning a tuple, objects made in a `for` loop, an `.animate` on an indexed child |
| `dynamic.py` | Dynamic | tier 3: `always_redraw`, updaters with and without `dt`, `ValueTracker` |
| `inheritance.py` | BaseScene, Child | a mixin, a base scene, a child that overrides a hook and calls `super()` |
| `timing.py` | Timing, Anchored | `LaggedStart`, per-animation `run_time`, `Succession(Wait, ...)`, play-level `rate_func`, `AnimationGroup`, bare `wait()`, `TimedScene.at()` |
| `transforms.py` | Transforms | `TransformMatchingTex` on a copy, `Transform`, `ReplacementTransform` |
| `randomness.py` | Seeded, Unseeded | seeded randomness (fine) vs unseeded (must be flagged as non-deterministic) |
| `camera.py` | Zoom, Orbit | `MovingCameraScene` frame moves; `ThreeDScene` with fixed-in-frame text and `move_camera` |
| `broken_syntax.py` | – | doesn't parse: open read-only, never write |
| `broken_runtime.py` | CrashLater | crashes at t = 1: show the trace up to there and the line |

Trace check (spike engine): every scene traced and drew a mid-scene frame,
except the two broken files, which failed as intended (`SyntaxError` at line
8; `NameError` at t = 1). Two findings already:
- **Scene discovery.** The spike listed only classes that define
  `construct` themselves, so it missed `Child` (inherits it). The product
  must list every `Scene` subclass defined in the file that has a
  `construct` other than `Scene.construct` anywhere in its MRO, and skip
  bases with none (like our `Beat` classes).
- **`wait(0)` is an error in Manim 0.22** ("duration of 0 <= 0 seconds").
  The studio must never write it: a group moved to zero distance removes
  the `wait()` (code_spec §4.4 already says so).

## 3. Manim CE docs gallery (to collect in Phase 2)

The example scenes from the Manim Community docs ("Example Gallery":
basic concepts, animations, plotting, special camera settings, advanced
projects). They're the most common style of Manim code in the wild.

They live in the Manim repository (MIT licence), not in the installed
package, so collecting them means downloading one `.rst` file from GitHub
and extracting the code blocks. That needs your OK; planned for the start
of Phase 2. They'd go in `studio/tests/corpus/gallery/`, one file per
section, with the licence notice.

## 4. Targets (answers PLAN.md's open question on the editable share)

Measured per phase on all three parts:

| Measure | Phase 2 | Phase 3 | Phase 5 |
|---|---|---|---|
| Files that open and play | 100% (except `broken_*`, which open read-only) | 100% | 100% |
| No-op save byte-identical | 100% | 100% | 100% |
| Timeline clips retimable (tier 1–2 `play`/`wait`) | ≥ 95% | ≥ 95% | ≥ 98% |
| On-screen objects drag-editable (verified) | – | ≥ 90% | ≥ 95% |
| Statements tier 1 or 2 (census) | report | report | ≥ 95% |

Phase 0 baselines: census 94.6% tier 1–2; drags 95% (319 / 336).
