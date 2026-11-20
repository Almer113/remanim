# Phase 6 baseline: speed

Step 1 of `plan.md`. Bench: `tests/speed_run.py`, report
`tests/tmp/speed_report_baseline.json`. Run on 2026-11-20 with the code of
`5a13157` (before any Phase 6 change), on the repo videos and the gallery,
each on a copy, through the same `Document` path the server uses.

## Results

| File | Scenes | First scene shown | All traced | Reopen (all) | Where open time went | First frame | Scrub median / max | Edit reply: retime, drag, colour |
|---|---|---|---|---|---|---|---|---|
| `eola_preview.py` | 23 | 5.0 s | 38.3 s | 33.9 s | engine 4.3, trace 30.7 | 0.30 s | 0.02 / 0.27 s | 1.6, 0.9, 1.5 s |
| `gradient_descent.py` | 11 | 6.7 s | 35.3 s | 30.7 s | engine 5.6, trace 27.4 | 0.68 s | 0.08 / 0.61 s | 2.0, 2.7, 2.4 s |
| `order_matters.py` | 5 | 6.8 s | 19.8 s | 17.9 s | engine 5.6, trace 13.9 | 0.16 s | 0.11 / 0.50 s | 3.0, 3.1, **17.4** s |
| `pythagoras.py` | 5 | 9.6 s | 27.9 s | 19.9 s | engine 6.9, trace 20.1 | 0.23 s | 0.03 / 0.36 s | 3.2, 3.6, **9.3** s |
| `test_scene.py` | 1 | 7.2 s | 7.2 s | 7.0 s | engine 6.8, trace 0.3 | 0.52 s | 0.02 / 0.07 s | 1.5, 1.5, 1.6 s |
| gallery (5 files) | 2–8 | 6.2–9.5 s | 7.4–14.2 s | 7.3–10.5 s | engine 6.0–8.8, trace 1.2–5.3 | 0.07–2.5 s | ≤ 0.02 s | 1.3–2.6 s |

"Engine" is starting the process, importing Manim and running the file
(the module, not the scenes). Measured separately: process start plus
`import manim` is 5.5 s of it, and running a file is 0.5–1.5 s.

After every edit, the studio traced every scene of the file again in the
background: 26 s for `eola_preview.py`. The reply came back once the
edited scene was traced (the "edit reply" column), but the engine stayed
busy for the rest of the file. A frame asked for meanwhile waited for the
scene being traced, and playback prefetch stalled.

The two slow colour changes (17.4 s and 9.3 s) were the machine, not
the code: another project's tests were using the CPU during that run. On
a quiet machine (the `--old` run below), colour changes take as long as
the other edits.

## Where the time goes

1. **Engine start (5.5 s on every open).** It's the same for every file,
   and it's most of the time for small ones.
2. **Tracing every scene, on every open and after every edit.** 14–31 s
   for the four big videos. The scenes' code rarely changes between
   two opens, and an edit touches one scene.
3. Everything else is already fast: frames (median 0.02–0.1 s while
   scrubbing) and the replies to edits (1–3 s).

## Targets (from `plan.md`, kept)

| Measure | Target |
|---|---|
| Reopen, file unchanged | ≤ 3 s to every scene shown |
| Cold open | no slower than now |
| Edit → new frame, median | ≤ 2 s in 2D, ≤ 5 s in 3D |
| Scrub median | ≤ 0.3 s in 2D |
| UI frame time while scrubbing the biggest timeline | ≤ 50 ms |

## What step 2 does about it

- **A trace cache, per scene** (`server/tracecache.py`). The key is the
  code the scene can depend on: its own class, the classes it inherits
  from, and all code outside other scenes' classes, each with its line
  position, because traces record line numbers. It also covers the bytes
  of the local modules the file imports (the engine reports them), the
  `manim.cfg` files, the engine's own code, the Manim and Python
  versions, and the quality. Traces are kept in memory and in
  `media/studio_cache/traces/`. Traces that end in an error are never
  kept.
- **The verify run's trace is kept too.** An edit already traces the
  edited scene once to verify it. The reload after the write takes that
  trace and the untouched scenes' traces from the cache, so no scene is
  traced twice.
- **A spare engine.** The server keeps one engine process started and
  imported, and a file being opened adopts it. A new spare starts two
  seconds later. Cost: one idle process (~150 MB).
- **Found on the way:** an edit to `style.py` or `manim_kit.py` never
  reached an open file. The engine kept the old module until it
  restarted. Now a change to any local module an open file imports
  restarts that file's engine and traces it again.

## Note on measuring

Timings depend on what else the machine is doing. During step 2, another
project's test run kept the CPU busy and made a cold open look twice as
slow. So comparisons are run back to back: `speed_run.py --old` measures
the pre-Phase-6 behaviour (no cache, no spare engine) with today's code,
and the plain run measures the new one.

## After (step 3)

Run back to back on a quiet machine, 2026-11-20: `speed_run.py --old`
(no cache, no spare engine, no frame from the edit's run), then the new
code. Reports: `tests/tmp/speed_report_old.json`,
`tests/tmp/speed_report.json`. Medians over the 10 files:

| Measure | Old | New | Target | Met |
|---|---|---|---|---|
| Cold open, first scene shown | 7.1 s | 6.3 s | no slower | yes |
| Cold open, all scenes traced | 9.5 s | 8.7 s | no slower | yes |
| Reopen, first scene shown | 6.5 s | 1.2 s | | |
| Reopen, every scene shown | 8.3 s | 1.2 s | ≤ 3 s | 8 of 10 files; `eola_preview` 4.7 s (was 49 s), `gradient_descent` 3.7 s (was 31 s) |
| Edit → new frame (retime, drag, colour) | 3.9, 2.8, 3.1 s | 1.9, 1.9, 1.9 s | ≤ 2 s in 2D | yes (medians); the 3D files and `pythagoras` take 2–9 s |
| Undo → new frame | 3.2, 2.6, 2.8 s | 4.4, 2.7, 3.0 s | | no target; see below |
| Scrub median | 0.02 s | 0.03 s | ≤ 0.3 s | yes |
| First frame after open | 0.24 s | 0.55 s | | see below |

The third change, made after the first new run:

- **The edit's own run draws the next frame.** Verifying an edit replays
  the edited scene once. That run now also draws the frame at the
  playhead (the UI sends it with every edit), and after the write it is
  cached as the new revision's frame there. Before, the first frame after
  an edit ran the scene a second time (2–3 s on the big videos), because
  the reload takes traces from the cache and the engine had not run the
  new version yet. A test checks the cached frame is the frame the engine
  draws (image, id map, objects).

Left as they are:

- **The first frame after a cached reopen** is slower than after a full
  trace (2.2 s instead of 0.2 s on `order_matters`): nothing has run the
  scene in the new process yet. Time to the first frame is still lower
  (1.2 + 2.2 s against 6.5 + 0.2 s).
- **Undo** doesn't verify, so it has no run to take the frame from; its
  frame costs one replay (3–4 s on the big videos). The same cache could
  serve it: an undone edit's bytes are the bytes from before, whose frames
  were drawn. Not done here.
- The long edits on the 3D files and on `pythagoras` (up to 8.6 s for a
  colour) are the verify run itself: those scenes take that long to play.
