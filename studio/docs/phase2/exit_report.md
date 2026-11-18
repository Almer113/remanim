# Phase 2 exit report: the viewer that edits

Date: 2026-11-18. Verdict: **exit criteria met**, with the gaps listed in
section 5 carried into Phase 3.

## 1. What was built

- **Server** (`studio/server/`, aiohttp on 127.0.0.1:8770, launch config
  `manim-studio`): one spawned worker process per open file, request
  deadlines with kill and restart, frame cache (LRU, 400 MB), prefetch of
  half-size JPEGs while idle, file watching, undo and redo as whole-byte
  stacks.
- **Engine** (`server/engine/`): replay with `dry_run`, a clock that mirrors
  a real render, live cursors parked along the timeline (threads inside the
  worker), ID maps for picking, object identity by creating call.
- **Code layer** (`server/code/`): spans, byte splices that keep number
  style and line endings, timing and property planners that refuse with a
  reason, census tiers.
- **Web UI** (`studio/web/`, React + Vite): canvas with hover and click
  picking, Layers, Inspector (clip and object), timeline with clips linked
  to code, trim handles, zoom, playback, code peek, diff on preview,
  toasts, undo and redo.
- **Protocol** as built: see the "As built in Phase 2" section of
  [protocol.md](../protocol.md) (frames over HTTP, ids without end position,
  numbered clips).

## 2. Exit criteria

| Criterion | Result |
|---|---|
| All corpus files open and play | 25 files, 88 scenes: every scene traces and renders frames at start, middle and end; 0 bad frames. Broken files open read-only with the right error (`broken_syntax.py` parse error line 8; `broken_runtime.py` scene error `NameError`; 3b1b's ManimGL `reference/source/chapter0.py` reports the missing `manim_imports_ext`) |
| No-op save is byte-identical | Every file is byte-identical after open, trace, frames and objects. Planning each editable clip back to its own value changes no byte (some bare `wait()` get an explicit `1` inserted when planned, which is same-time; the UI never sends an unchanged value) |
| Retiming and property edits round-trip on tier-1 code | 34 edits went edit → replay-verify → write → undo with the original bytes back every time: 18 timing, 10 number, 6 colour. 4 were refused, each correctly (below) |

Refusals, all correct behaviour:
- `order_matters.py` colour of `eq`: the next lines recolour `eq[0]` and
  `eq[4]`, so "something later sets it again" is true.
- `pythagoras.py` and gallery `basic_concepts.py`: refused because
  `fill_opacity` read back as 1. **Correction (review, same day):** this was
  a bug, not the test: painting the ID map overwrote `fill_opacity` on the
  live objects. Fixed; see [review_phase2.md](../review_phase2.md).
- awkward `dynamic.py`: the test asked for `num_decimal_places=1.35`; the
  edited scene crashed in verification and nothing was written. (The test
  now keeps whole numbers whole.)

Run it: `.venv/Scripts/python -u studio/tests/corpus_run.py [filter]`
(report in `studio/tests/tmp/corpus_report.json`; about 20 minutes, most of
it `eola_preview.py` and the 3D scenes). Pytest: 36 passing
(`studio/tests`: 31 unit, 2 engine, 3 round-trip; 2.5 minutes).

## 3. UI check (browser pane, `order_matters.py` copy)

Seek to 4 s shows the frame and Layers; clicking the title and the blob
selects them (outline, Layers highlight, Inspector, code peek on the right
line); dragging the first clip's edge wrote `run_time=0.8 → 1.1333` (now
snapped to 0.05 s); Inspector `height 2.0 → 2.6` rewrote line 87 and the
served frame shows the body 2.58 units tall; Undo restored the original
bytes; playback runs in real time (2.2 s of video in about 2.2 s).

## 4. Bugs found during the exit checks (fixed)

- Clip duration was the frame-rounded value (`wait(0.5)` = 7 frames =
  0.4667 s), so writing a clip back unchanged rewrote `0.5` as `0.4667`.
  Traces now carry `nominal` (the code's number); clips edit that and show
  `played` separately.
- Reading `Square.side_length` mid-`Create` raised, and the error killed
  the whole cursor. Property reads are now guarded, and a failed capture
  answers that one request without killing the cursor.
- Colour verification compared hex exactly; `#fb6254` vs `#fc6255` is float
  rounding. Now ±2 per channel.
- Code peek scrolled to the wrong line (`offsetTop` measured from the page).
- "Colour now" showed a group's own default white; now its first drawn part.
- Status pill said "cursors 15/8": it counted threads, not covered spots.
- `/api/status` returned 404 before a file was open (console noise).
- Cold start: all ~12 cursors started at once and the requested frame
  queued behind them (37 s for the first frame of `eola_preview`
  S18). Cursors now warm two at a time from the start: 6.9 s.

## 5. Not done yet (carried into Phase 3)

From testing.md, not built in Phase 2:
- Clock check against `tools/timeline_render.py` JSON, and studio frames vs
  `manim -s` pixel comparison (S1 did this as a spike; not a test yet).
- Redo round-trip in the suite (redo works in the UI; untested in bulk).
- Edit fuzzing, the identity and move benches as tests, the
  `while True` deadline test, the determinism test.
- Preview server and studio running side by side on the same folder.

Performance gaps against architecture.md's budgets:
- 3D scenes: frames take 7 to 12 s cold (budget: 1.5 s, then cached).
  Proxy resolution while dragging and a faster first cursor are Phase 3 work.
- Opening a large file traces every scene first: `eola_preview.py` (23
  scenes) takes about 33 s before the model is complete; the active scene
  appears earlier.

Other notes:
- Objects made inside helpers get edits only after a confirm step; objects
  from an inherited `construct()` or library code show as locked.
- Timeline and Inspector show `duration` (the code's number); the frames
  actually played (`played`) differ by less than one frame.
