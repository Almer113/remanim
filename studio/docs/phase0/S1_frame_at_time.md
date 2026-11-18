# S1: frame at any time

**Question:** can the engine show any moment of a scene quickly, without
rendering the video?
**Bar (PLAN.md):** median under 0.5 s for 2D scenes in this repo, under 2 s for 3D.
**Verdict: pass, with live cursors.** Plain replay from zero misses the bar by
about 2×, so the engine needs the cursor pool described below. One weak spot
remains: scrubbing a 3D scene runs at about 1 frame a second, because drawing
the surface is the cost. That needs a frame cache (Phase 1), not a faster
replay.

Code: `studio/spikes/frame_engine.py`, `cursor_engine.py`, and the two
benchmarks `s1_bench.py` and `s1_cursor_bench.py`. Results are saved as JSON in
`media/studio_spikes/s1/`.

## How it works

1. **Replay to t** (`frame_engine.py`). Run `construct()` with every play
   skipped: a skipped play only jumps its mobjects to the end state. The play
   that spans t is interpolated to the right point instead, the frame is
   drawn, and construct() stops there. The module is imported once and stays
   loaded.
2. **Live cursors** (`cursor_engine.py`). A cursor is one run of construct()
   in its own thread, paused inside a play(). Asked for t, it moves forward to
   t and draws. It can't go back, so a pool parks about 12 cursors along the
   timeline (one a second). A request uses the latest cursor at or before t.
   After use, a cursor stays where it stopped, which makes scrubbing forward
   cheap. A background thread puts a fresh cursor on the park spot it left.

## Exactness

Every frame was compared with the same frame of a real render: mean
absolute pixel difference, 0–255. Video compression alone gives about 1.5.

| | Result |
|---|---|
| order_matters (3 scenes, uncached reference) | 1.5–1.9 mean, worst 1.95 |
| gradient_descent (11 scenes, 2D and 3D) | worst 1.4–3.4 (reference partly cached, see below) |

Getting this exact needed three fixes. Each is a way the engine can silently
drift from the real video:

- **The clock must advance like a real render.** A real render adds 1/15 s
  per frame (`time += dt`), and a frozen `wait()` adds `frames × dt` in one
  step. Multiplying instead changed the float rounding. `at(1.8)` at
  t ≈ 1.6 then got 3 frames instead of 4, and everything after was a frame
  early.
- **Updaters see the last frame's time, not the full duration.** A play of
  d seconds draws frames at `arange(0, d, 1/fps)`. So `dt`-updaters
  integrate one frame less than d per play. Manim's own skip mode jumps the
  full d, which drifted the spinning grid in `order_matters.Takeaway`.
- **Clock-reading updaters need the clock set.** Captions read
  `renderer.time`. Inside the interpolated play it has to be the time being
  shown, or the wrong caption appears.

**Manim quirk found on the way:** a play served from Manim's partial-movie
cache advances the clock by its exact duration, not by frames. So a partly
cached render can be a frame off from an uncached one. The engine matches an
uncached render. The preview server's videos are usually partly cached.
Phase 1 should pick one of two fixes: render with `--disable_caching` when
the timeline must line up exactly, or accept a frame of slack.

## Speed

480p15, this laptop. "Random" means clicking on random timeline points;
"scrub" means 20 consecutive frames, as when dragging the playhead.

### Replay from zero (no cursors)

| Scenes | Median | Max |
|---|---|---|
| order_matters (5 scenes) | 0.54–1.24 s | 2.7 s |
| gradient_descent, 2D | 0.34–1.63 s | 2.5 s |
| gradient_descent, 3D | 1.39–2.73 s | 3.2 s |

**Fails the bar.** The time goes into the deep copies that `begin()` makes
for every animation, into stepping frame by frame through the current play
(captions are a `dt`-updater, so the steps can't be skipped), and into
parsing text SVGs.

### Live cursors (pool warm)

| Scene | Kind | Random median | Random max | Scrub median | Warm-up |
|---|---|---|---|---|---|
| order_matters.ShearThenRotate | 2D | 0.29 s | 4.3 s | 0.045 s | 14 s |
| order_matters.Takeaway | 2D | 0.12 s | 1.2 s | 0.032 s | 4 s |
| Foggy | 2D | 0.12 s | 0.6 s | 0.040 s | 4 s |
| FeelTheSlope | 2D | 0.24 s | 2.1 s | 0.033 s | 5 s |
| OneDimension | 2D | 0.12 s | 1.4 s | 0.046 s | 5 s |
| StepSize | 2D | 0.14 s | 0.6 s | 0.086 s | 6 s |
| ContourMap | 2D | 0.20 s | 2.1 s | 0.106 s | 20 s |
| TooBig | 2D | 0.51 s | 3.5 s | 0.121 s | 20 s |
| Takeaway | 2D | 0.10 s | 2.1 s | 0.020 s | 5 s |
| Landscape | 3D | 1.23 s | 2.6 s | 0.61 s | 17 s |
| Gradient | 3D | 1.01 s | 3.8 s | 0.96 s | 25 s |
| Descent3D | 3D | 0.81 s | 1.7 s | 0.66 s | 10 s |
| LocalMinimum | 3D | 1.45 s | 2.0 s | 0.64 s | 12 s |

- **2D: pass.** Random median 0.10–0.29 s, except TooBig at 0.51 s.
  Scrubbing runs at 10–50 frames a second.
- **3D: pass on the bar (median 0.8–1.45 s), but scrubbing is slow.** Each
  3D frame costs about 0.6 s to draw: Cairo sorts and fills about 1,000
  surface faces. A faster replay can't fix that.
- **Outliers (the max column)** are clicks that land before every free cursor
  while background refills compete for the CPU (Python threads share the
  GIL). The engine then replays from zero.
- **Memory:** about 50–130 MB per open scene's pool.
- **Warm-up** is background time after opening a scene or saving an edit.
  The first frame after an edit is a replay from zero: 0.3–2.7 s.

## Tried and dropped

- **Skipping `begin()`'s copies for skipped plays.** This was the biggest
  potential win, about 40% of replay time. But whether it's safe depends on
  each animation's internals. FadeIn fades its own "copy" of the mobject
  (which then vanished), and DrawBorderThenFill reuses its start state (which
  crashed). Exactness wins.

## Kept: two exact caches

- Text SVGs reuse Manim's own SVG cache. It's off for `Text` by default, but
  Text's SVG file name is already a hash of the text and all its settings.
- Narration length is memoised by path and mtime, instead of decoding the mp3
  on every `say()`.

## Problems found outside the studio (fixed)

1. **The voiceover cache grew on every render and got corrupted.**
   manim-voiceover appends an entry to `media/voiceovers/cache.json` on every
   `say()`, cache hits included. It had 934 entries for 95 lines (2.7 MB),
   re-parsed on every line. Two writers then left it as invalid JSON, which
   breaks every narrated render. Fixes:
   - `EdgeTTSService` now returns cache hits without writing;
   - the cache was rebuilt with duplicates removed;
   - the corrupt original is kept in `media/backups/`.
2. **Concurrent Text creation can leave 0-byte SVGs in `media/texts/`.**
   Text rewrites its SVG file. Two threads (or processes) building the same
   text can leave an empty file, and every later render of that text then
   fails with `ParseError: no element found`. Nine such files were removed.
   The cursor engine now serialises Text/MathTex/SVG creation with one lock.

## What this means for the plan

- The Phase 1 engine is the cursor pool, plus a **frame cache**: an LRU of
  drawn frames keyed by scene, frame index and code hash. In 3D, it should
  also fill in the background so scrubbing a 3D scene becomes smooth after one
  pass.
- **Run cursors in worker processes, not threads,** once the engine is a
  server. That removes the GIL contention behind the outliers and gives each
  worker its own file state. Frames are 0.9 MB at 480p, cheap to pass back.
- **During a drag, draw at lower resolution.** 3D frame cost scales with
  pixels and faces. A 240p proxy, or fewer surface faces, while dragging,
  then full quality on release.
- **Known limit:** a `dt`-updater that is non-linear in dt (physics-style
  integration) is approximated in skipped plays, as it is in Manim's own skip
  mode. Every scene in this repo was exact; flag it if one appears.
