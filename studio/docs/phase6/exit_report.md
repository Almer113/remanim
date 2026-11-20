# Phase 6 exit report

Plan: `plan.md`. Speed: `baseline.md`. Errors: `errors.md`. Checked on
2026-11-20.

## The exit criteria

| Criterion | Result |
|---|---|
| A whole video made in the studio without a terminal: open, edit, export joined and narrated, `audio_check.py` passes | **Met**, see "Hands-on run". One gap found and fixed on the way (narration in a scene with `VOICE = None`). |
| The speed targets of step 1 | **Met**, with two files over the reopen target (below) |
| Every failure in the error catalogue shows a clear message and recovers without a restart | **Met**: 33 rows, each with a test, a UI try or a code reading; one row added by the hands-on run |
| A fresh clone starts from the README alone | **Met**: dry run in a scratch folder (below) |

## Speed (6a)

Back to back on a quiet machine, old code path (`speed_run.py --old`)
against the new one, medians over 10 files:

| Measure | Old | New | Target | Met |
|---|---|---|---|---|
| Cold open, first scene shown | 7.1 s | 6.3 s | no slower | yes |
| Cold open, all traced | 9.5 s | 8.7 s | no slower | yes |
| Reopen, every scene shown | 8.3 s | 1.2 s | ≤ 3 s | 8 of 10 files; `eola_preview` 4.7 s (was 49 s), `gradient_descent` 3.7 s (was 31 s) |
| Edit → new frame (retime, drag, colour) | 3.9, 2.8, 3.1 s | 1.9, 1.9, 1.9 s | ≤ 2 s in 2D | yes; 3D files and `pythagoras` 2–9 s, which is the scene's own play time in the verify run |
| Scrub median | 0.02 s | 0.03 s | ≤ 0.3 s | yes |
| UI frame while scrubbing `S16_ExampleMatrixMultiplication` (112 clips) | | render + layout median 9.6 ms, p95 18.3 ms, max 34.9 ms | ≤ 50 ms | yes |

What made the difference: a per-scene trace cache (`server/tracecache.py`,
on disk under `media/studio_cache/`), a spare engine kept started, cached
traces applied before any tracing, and the edit's own verify run drawing
the frame at the playhead.

Caveats:
- **UI frame time** was measured with the browser pane hidden, so paint
  isn't in it; with timers included, spikes reach 175 ms, from timers and
  image loads in a background page. A visible-pane measurement is still
  owed.
- **The first frame after a cached reopen** costs one replay (2.2 s on
  `order_matters`, against 0.2 s after a full trace). Time to the first
  frame is still lower overall (3.4 s against 6.7 s).
- **Undo isn't seeded**: an undo has no verify run, so its frame costs one
  replay (3–4 s on the big videos). The frame cache could serve it from
  the earlier bytes; not done.

## Export (6b)

- Export dialog: scenes (all, this one, a choice), quality `l/m/h/k`,
  format (mp4, webm, gif, png, mov), join, narration check, cancel,
  progress per scene, play in the studio, "Show in folder" (local pages
  only).
- Export renders through `tools/timeline_render.py`, never the studio's
  engine, under the lock in `tools/render_lock.py`, which
  `preview_server.py` now waits for as well.
- Browser check: 5 scenes of an `order_matters.py` copy at `-ql` in 86 s,
  joined to one 45.7 s video, narration check passed, played in the
  studio. Engine test: `test_phase6.py::test_export…`.

## Keyboard (6c)

One keymap (`web/src/keymap.ts`) feeds the handler, the tooltips, the `?`
help sheet and the README table (`web/checks/keymap_md.ts`). A check
refuses duplicate keys. Nudges with the arrows (Shift ×10, Alt fine) merge
into one undo step. Dropped: Ctrl+F (there is no layer filter).

## Errors (6d)

All rows of `errors.md` are filled. Bugs found by trying them in the UI,
all fixed:
- the "loading…" pill stayed after a failed load;
- a stopped scene's frame ran the endless loop again;
- the last good version's objects lost their names and tiers;
- the frame error showed raw JSON;
- a looping scene hid the scenes that had a cached trace;
- creating or opening any file restarted every open file's engine
  (Windows reports reads as changes; now only a changed digest counts);
- the header wrapped at 1440 px (file picker, and again during an export,
  found in the hands-on run: pills now shorten instead);
- narration in a `VOICE = None` scene failed with "no attribute
  'speech_service'" (hands-on run; now a message that says to set
  `VOICE`).

Also fixed in the suite: a race in which Stop on a looping scene could be
reported as a timeout.

## Docs and install (6e)

- `studio/README.md`: start-up (local, tailnet, app window), the tour with
  a screenshot (`docs/img/studio.png`), tiers, shortcuts, export,
  troubleshooting, Claude Code alongside, the Claude panel.
- `requirements.txt` records the venv as it is. The server says to run
  `npm run build` when `web/dist` is missing or older than `web/src`.
  `python -m studio.tests` runs unit, engine and corpus.
- Fresh-clone dry run (git files copied to a scratch folder): `npm ci
  --offline`, build, server start with no UI warning, 387 unit tests in
  12 s. The copy was removed.

## Optional items

- **App window:** `python -m studio.server --app` (or double-click
  `studio/Manim Studio.cmd`) opens Edge or Chrome with `--app=`; if the
  studio is already running it just opens a window onto it.
- **Claude panel:** `claude -p` with read/edit/search tools only,
  `acceptEdits`, project root, follow-ups resume the session. Off on pages
  from another machine unless `--allow-claude-remote`. Real run: one line
  edited, the studio reloaded, 10.2 s, **$0.45**. Each question costs
  about $0.40–0.45 because Claude Code reads the project instructions each
  time. Tests use a stand-in CLI.

## Hands-on run

From a blank file made in the studio (`+ New file`, template
`TimedScene`, `TARGET = 5`), without typing code in the studio:
1. dragged a circle from the Library onto the canvas (verified, rev 2);
2. added the narration line "Here is a circle, drawn in one smooth
   stroke." from the timeline's `+ line`. The template has
   `VOICE = None`, so this was refused, first with an unclear error, after
   the fix with "set a voice". Set `VOICE` in the file (the one step done
   outside the studio), added the line again: verified, waveform and
   caption lane shown;
3. exported at `-ql`: 14.1 s, narration check passed in the dialog;
   `tools/audio_check.py` on the file: ok (audio 3.4 s, sound under the
   cue);
4. exported at `-qh`: 11.6 s, 1920×1080 at 60 fps, `audio_check.py` ok, a
   frame at 2 s shows the circle.

The scene had one scene, so "join" was greyed out; the joined path was
proven on the 5-scene `order_matters` copy above. The file and its media
were deleted afterwards.

**Gap left:** the `+ line` button is enabled in a scene with
`VOICE = None`; it could offer to set the voice. The refusal now says what
to do, which is enough for now.

## Tests

- **Full suite** (`pytest -q studio/tests`, unit + engine): 426 passed
  in 11 min 32 s, after the last change (the `manim_kit.py` message and
  the header CSS).
- **Corpus run** (`tests/corpus_run.py`): 27 files, 93 scenes, every file
  plays, no bad frames, a no-op save byte-identical on all 27, all edit
  round trips ok. (A 28th entry, `ui_handson.py`, crashed with "file not
  found" because the hands-on file was deleted while the run was going;
  it is not a corpus file.)
- **Web checks:** `tsc` clean, the keymap check passes, UI rebuilt.

## Open after Phase 6

- Seed undo's frame from the frame cache.
- A visible-pane UI frame-time measurement.
- `+ line` could set `VOICE` itself in a silent scene.
- Carried from Phase 5: z moves in 3D, an out-of-camera view for 2D.
- Name and licence (waiting for a decision).
