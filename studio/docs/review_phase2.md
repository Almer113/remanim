# Review after Phase 2 (Phases 0–2)

Date: 2026-11-18. Scope: everything under `studio/server/` and `studio/web/src/`
as committed in `6c44686`. Method: three independent read-throughs (engine and
process layer; code layer and edit flow; web UI), each claim checked against
the code (pure-Python probes for byte-level claims), then fixed here and
tested by hand in the browser pane. Baseline before the fixes: 36 tests
passing.

Every fix has a regression test. Run against the old code (a worktree at
`6c44686`), 36 of the 42 new tests fail; the 6 that pass guard behaviour
that was already right, plus the library-copy id fix (see below).

## 1. Security

| Problem | Fix |
|---|---|
| **Any web page could edit your files.** Browsers let any site open `ws://127.0.0.1:8770/ws`; the server checked no `Origin`. Opening a file runs it, and `rate_func` was written into the file unchecked, so `__import__('os').system(...)` could be planted and run by the verify replay | Middleware `local_only` (`app.py`): the `Host` must be local (no DNS rebinding) and a browser `Origin` must be this server (either local name, same port) or the Vite dev server. `rate_func` and `name` values must be (dotted) Python names; property names must be identifiers; numbers must be finite |
| `open` accepted any `.py` under the project, including `.venv` and `studio/server`, and running it is what opening does | `normalise()`: same folder rules as the file list; `./x.py` and `x.py` are one document (the second name used to start a second worker and leak the first) |

## 2. Code layer (splices and planners)

- Confirming a "check this edit first" preview after another edit or an undo
  wrote bytes planned from the old file, silently dropping the later change.
  Pending edits now remember their base and are refused if it moved; any
  reload clears them.
- A save in your editor while an edit was verifying was overwritten, and so
  was undo. Writes now re-read the disk first and refuse if it changed;
  external-change handling waits for the edit in flight.
- `f(\n  a,\n  b,)` + keyword wrote `k=2,` after the closing paren.
- `x.animate(run_time=1).shift(...)`: run_time went into `shift()`.
- `self.wait(frozen_frame=False)` became `wait(frozen_frame=False2)`.
- A UTF-8 BOM shifted every line-1 span by 3 bytes.
- `"""..."""` strings with quotes in them, and raw strings given a newline,
  were written unparseable (refused, but the edit could never work).
- Edits inside a loop changed every pass without asking; replacing a
  computed value (`radius=r * 2`) did too. Both now ask first (spec §4).
- `at()` times came out as `at(2.9667)`; now rounded to 0.01 s.
  Durations that round to 0 are refused before planning.
- Bad requests (unknown clip index, a scene still tracing, a locked file on
  Windows) now refuse with a reason instead of a Python exception text, and
  leave no `.studio-tmp` behind.
- Loads could overlap (open, reload after restart and an external save at
  once). They are serialised, and a newer load stops an older one between
  scenes.

## 3. Engine and worker processes

- **Every ID map left `fill_opacity=1` on the live objects** (found by the
  corpus run after the other fixes). Painting the ID map calls `set_fill` /
  `set_stroke`, which also overwrite plain attributes (`fill_opacity`,
  `color`, ...); only the colour arrays were put back. So the Inspector
  showed 1 for every opacity, opacity edits were refused as "something
  later sets it again" (the `pythagoras.py` and `basic_concepts.py`
  refusals in the Phase 2 exit report were this bug, not test mistakes),
  and scene code later in the same cursor saw the wrong values. Those
  attributes are now saved and restored too. Numeric checks also refuse
  only when the edit had no effect, not when an animated value differs.

- **Unseeded randomness was really random.** `Scene.__init__` calls
  `random.seed(config.seed)` and `config.seed` is `None`, which seeds from
  the OS: an unseeded scene looked different in every cursor (objects jumped
  when scrubbing across a spot) and after every reload. Each thread now has
  its own `random` / `np.random` generators, and an unseeded `seed()` means
  seed 0, so every cursor and every reload agree. (A plain `manim` render of
  such a scene still differs run to run; that is Manim's behaviour.)
- **Thread leak on every reload for voiceover scenes.** A cursor being closed
  unwound through `finally: self.wait_for_voiceover()` (manim-voiceover),
  which re-entered the hook and blocked forever. About 12 threads, each
  holding a whole scene, were left per reload or scene switch. A stopping
  cursor now raises at once, and cursors that never started are not started
  just to be stopped.
- A negative frame index looped, building cursors until the 60 s deadline
  killed the worker. Frame indices are clamped to the scene.
- A cursor still warming toward a later spot could be picked for an earlier
  frame and run past it; the spot was then lost for good. Only parked
  cursors, or ones warming to a spot at or before the frame, are picked, and
  a spot whose cursor dies is refilled.
- An error partway through a play used up one parked cursor per request, and
  prefetch retried the failing frames forever (CPU stayed busy). The pool
  now remembers the error time and answers later frames with it; prefetch
  skips frames that failed.
- After a worker restart caused by a slow `trace` or `verify`, nothing was
  loaded until the file changed. Any restart now reloads (at most 3 times
  for the same bytes, so code that hangs every time doesn't restart forever).
- Old modules from each load and verify stayed in `sys.modules`; the
  cursor cap (40) could keep 40 whole scenes alive. Modules are dropped on
  close; the cap is 24 and moved-on cursors go first. Closing a file no
  longer blocks the server for up to 8 s, and old pipes are closed.
- Objects made in library code from one user call all got `#0`. They are
  now counted per class and calling line. (I could not make the reported
  collision happen with `TransformFromCopy`; the test passes before and
  after, so this is a safeguard, not a confirmed bug.)

## 4. Web UI

- Picking a scene still tracing blanked the whole app (`duration` of a
  pending scene). Guarded, and an error boundary now catches any render
  crash with a reload button.
- A server restart left the UI dead until a page reload: the file is now
  re-opened on every reconnect (checked in the pane: same page, file back,
  cursors parked).
- An edit in flight when the connection dropped kept "Verifying…" and
  disabled every button forever. Requests now always settle (disconnect or
  a 4-minute timeout).
- Pausing left the playhead "not at rest": half-size frame, no ID map, so
  clicks selected nothing. Pausing now rests.
- Objects from the previous frame were used to resolve clicks on the next
  one; selection kept showing an object that was gone. Objects are tied to
  (server run, revision, scene, frame); an object not on screen stays
  selected but its fields are disabled with a note.
- Frames cached by the browser from an earlier server run could be shown
  (revisions restart at 1). Frame URLs carry a per-run id.
- Ctrl+Z ignored "busy" and the preview dialog; trim drags could stick
  after Alt-Tab or send an edit against an old model; the diff highlight
  could vanish early.
- Inspector: invalid values were dropped silently; now the box keeps the
  text, turns red and says why. `1e-3` is accepted, `Infinity` is not;
  "↵ to apply" shows while a field is changed. Easing has a "(default)"
  option. Failed frames show a message on the canvas; slow ones say
  "Rendering this frame…". The code peek no longer re-renders on every
  playback frame.
- Edit replies came only after every scene in the file was traced again
  (seconds to minutes in a large file). They now come once the active scene
  is traced (1.5 s for a run_time edit in `order_matters.py`, was the full
  reload); undo right after an edit 3.2 s (was 8.5 s).

## 5. Not changed (open)

- ~~`@types/react` not installed, no type check~~ **Done (approved):**
  `@types/react` / `@types/react-dom` 19.3 in `studio/web`; `npm run build`
  now runs `tsc --noEmit` first (strict mode; the only error was the CSS
  import, fixed with `vite-env.d.ts`). `npm audit` reports 5 high issues in
  Vite's own dev dependencies (picomatch, tinyglobby), present before this;
  they affect the dev tooling, not the built page. Not changed.
- ~~Preview server and studio side by side untested~~ **Done:** both servers
  on the same folder and the same root scene file: 4 studio edits (3 new
  `Text` strings, 1 wait) each followed by a preview re-render, then 3
  editor saves with new `MathTex`. Every studio edit verified, every
  preview render `ok`, no `WinError 32` / `PermissionError` in either log;
  the studio reloaded after each save. (Separate LaTeX folders; the shared
  `media/texts` cache caused no clash.)
- A module-level `config.x = ...` in a scene file is undone by `tempconfig`
  (no file in this repo does it; `apply_background()` is only called inside
  scenes).
- 3D frames are still 7–12 s cold (Phase 3 work).
- Unseeded scenes are made deterministic but not yet flagged in the UI.

## 6. Results after the fixes

| | Before (Phase 2 exit) | After |
|---|---|---|
| Pytest (`studio/tests`) | 36 passed | **85 passed** (2.5 min) |
| Corpus files / scenes | 25 / 88 | 27 / 92 (added `finally_wait.py`, `late_error.py`) |
| Bad frames | 0 | 1, on purpose: `late_error.py` fails mid-play, and the error is served instead of a frame |
| Edits round-tripped, bytes restored | 34 of 38 | **41 of 42**; the one refusal is correct (`order_matters.py` recolours `eq` parts later) |
| No-op plans that changed bytes | 0 | 0 |
| Worker restarts during the run | 0 | 0 |
| Corpus run time | ~21 min | ~15 min (edit replies no longer wait for every scene) |
| Frame time, median / p95 | 0.21 / 6.68 s | 0.30 / 4.25 s |

Browser pane, by hand: seek, play/pause (frame and Layers come back after
pausing), click-select, a bad value marked red without being sent, a height
edit 2.0 → 2.4 then Ctrl+Z (file byte-identical), a server restart while the
page stayed open (reconnected and re-opened the file without a reload).
Requests with a foreign `Origin` or `Host`, and `open` on `studio/server/`,
`.venv/` or `../`, are refused.
