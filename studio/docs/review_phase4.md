# Review after Phase 4

Date: 2026-11-19. Scope: everything changed since the last review
(`0e094d3`), that is Phase 4 (`23db152`: narration recording, the audio mix
and waveforms, timeline edits, the easing picker, markers), plus the
uncommitted `ClippedGrid` change in `manim_kit.py` (a constant part count).

Method:
- three independent read-throughs: engine and server (narration recorder,
  `/audio`, `/audio/peaks`, edit flow), code layer (`timeline.py`,
  `inserts.py`, `splice.py`), and web UI (`Timeline.tsx`, `App.tsx`,
  `Easing.tsx`, `Inspector.tsx`);
- each finding checked against the code before it was fixed, and given a
  regression test where it can be tested without a browser;
- a hands-on pass in the browser pane on a copy of `order_matters.py`.

Baseline before the fixes: 202 unit tests passing, plus the engine tests.

## 1. Security

No new holes. Checked:
- `/audio` and `/audio/peaks` serve only sounds recorded from the scene's own
  `add_sound()` calls, resolved the way Manim resolves them (assets folder,
  then the path itself). A missing file now raises as it does in Manim; it
  used to be recorded and then fail in the mixer.
- Narration text and captions from the browser are written only through
  `_string_like` (escaped literals). NUL and lone surrogates are now
  refused (see below) instead of producing a file that won't encode.
- The audio routes check that the `rev` they were asked for is still the
  document's rev, so a slow mix can't be served for newer code.

## 2. Code layer (timeline edits)

Regression tests: `tests/unit/test_review_phase4.py` (12) and additions to
the Phase 4 test files.

- **Ripple shift skipped literal `at()`s inside moved `with` blocks.** A
  later clip inside `with self.say(...)` stayed put while the clips around
  it moved. The ripple now shifts `at()`s inside moved compound statements.
  A shift also starts from `max(old, previous end)`, so a clip that was
  waiting on an earlier one doesn't jump by less than the drag.
- **Merge and per-clip offsets dropped keywords.** Merging two plays, or
  offsetting a clip with `clip()`, ignored keywords other than `run_time`
  (`rate_func=`, `lag_ratio=`) on either play; the result ran with
  different timing. Both now refuse such plays and say why.
- **Run-time edits on `clip()`:** a `clip()` with a nonzero start under a
  play `run_time=` is refused (the play stretches the offset too). An existing
  numeric `length=` is updated rather than added twice. A computed value
  is refused by name. `.animate(run_time=k)` is updated in place.
- **A whole literal changed style.** A drag from `at(3)` to 4 wrote `4.0`
  when the file mostly writes `2.0`. A whole literal now keeps its own style.
  Only a fractional one that becomes whole follows the file's habit.
  `TARGET: float = 6.0` (annotated) now counts toward the habit too.
- **A caption written as the second argument** (`say("A squared", "a²")`)
  got a `caption=` keyword as well, so the scene crashed with "multiple
  values". It is now changed in place; removing it is refused with a
  pointer to the code.
- **Reorder missed scene attributes.** `self.t = Text(...)` then
  `self.play(Write(self.t))` could be swapped. `self.X` now counts as a
  shared name, except the scene's own methods (`self.play`, `self.wait`, …).
- **Text from the browser:** NUL and lone surrogates are refused; `\r\n` and
  `\r` become `\n`. Inside triple quotes, new lines use the file's own line
  ending.
- **"What else moved"** now also counts narration lines that start
  elsewhere. It is left out after a reorder, merge or split, where matching
  plays by index would report noise.
- `slot()` no longer writes a second `self.at(t)` when the statements before
  already reach t, or when an `at()`'s end rounds just past t.
- Cleanup: a dead helper and a collapsed line in `_point_style`.

## 3. Engine and server

- **Narration attribution.** A sound was matched to a narration line by
  "the line that is open". A sound added inside a `with self.say(...)`
  block was therefore claimed by the line and shown as its waveform. Only
  the sound the `say()`/`voiceover()` call itself adds now belongs to the
  line (a one-shot marker, cleared on entering the block).
- **Audio cache.** `lru_cache` on decoded clips held up to 128 full decodes
  with no size bound. It is now an LRU bounded by total samples
  (`CACHE_SECONDS = 600`) behind a lock, because the mix and the peaks
  routes run in threads.
- **A bad sound file broke the whole mix.** A clip that fails to open or
  decode is now skipped and logged; the rest still plays. Files with a
  video stream first are decoded from their audio stream.
- **Clip offsets in a stretched play** were shown unscaled. In
  `play(clip(a, start=0.5), run_time=4)`, both the offset and the length of
  `a` are now shown as they really play.
- **`timed` came from a truncated base list** (the first three Manim
  bases), so a scene with several mixins could lose its timeline edits.
  The trace now carries `timed` from the full MRO.
- **"Text-to-speech failed" was matched by `"edge" in message`**, which also
  hit `to_edge`. It now looks for the TTS service's own error or a
  traceback through it.
- **Caption warnings on voiceovers:** bookmarks (`<bookmark mark='x'/>`) are
  stripped before the length is counted. The hold-time warning is only given
  for `say()`: a voiceover's caption is up exactly as long as its speech.
- A refusal caused by a FadeIn/FadeOut of a moving `always_redraw` object
  (zip length mismatch) now explains that, instead of only the raw error.
- **`ClippedGrid` keeps a constant part count** (invisible stand-ins for
  clipped lines and squashed arrows), so it can be faded while it moves. A
  new fixture (`kit_parts.py` `GridFade`) checks 61 tracker values; it
  fails on the old code (34 to 44 parts).

## 4. Web UI

Found in the browser pass (not by the read-throughs):
- **Playing from the middle of a scene played the sound from 0.** `/audio`
  had no Range support, so Chrome could not seek the WAV (`seekable` was
  empty), and since the audio clock drives the picture, the picture jumped
  back too. `/audio` now answers `Range` requests (206 / 416). The client
  also checks where the sound really started: more than 0.25 s off, and
  the picture keeps the wall clock and the sound is stopped rather than
  playing the wrong words.
- **Timeline drags wrote frame-rounding residue into the code:**
  `at(6.98)` after a move, `run_time=1.0333` after a trim. Clip starts sit
  on frames (`at(6.6)` plays from 6.667 at 15 fps), and the snap rounded
  the *landing time* to the 0.05 s grid. On the plain grid it now rounds the
  move or length itself, so the same drags write `at(6.9)` and
  `run_time=1.0`; on a snap point (a clip edge, line, marker) it still lands
  exactly on it.
- **`/frame`, `/objects` and `/idmap` answered 500 when an edit or undo
  landed during the render,** and `/idmap` never checked the revision, so
  it could cache newer code's ids under an old revision's URL. All three
  now answer 410 if the revision changed before or after the render, and a
  malformed `rev`/`f` is a 400.

From the read-throughs:
- **Playback:**
  - the audio URL carries the session, so a restarted server's mix isn't
    served from the browser cache;
  - frames hold until the audio is really playing (no drift at start), and
    an audio error falls back to the wall clock;
  - mute applies live;
  - changing file, scene, rev or session stops playback and releases the
    audio element.
- **Timeline:**
  - markers from local storage are validated, and new names come from the
    highest number in use (no duplicates after a delete);
  - the selection and drag state reset on a new rev or scene;
  - bookmarks are snap points;
  - trims snap, count only after a real move, and respect `editable`;
  - groups dragged together show as moving;
  - R and M (markers) are registered once and ignored while a dialog is
    open;
  - waveforms are matched to their narration line by index, not by order;
  - the ripple checkbox and zoom slider give the focus back after use, so
    keys reach the timeline.
- **Easing picker:** Escape closes the picker only (not the selection too),
  the grid closes on resize, and the picker resets when the selection
  changes.
- Accessibility: titles and labels on the scene-order arrows and the mute
  button.

## 5. Not changed (open)

- **The TTS cache is not safe across processes.** Two workers synthesising
  the same new line at once can both write `media/voiceovers/`. The fix
  belongs in `edge_tts_service.py`, which the videos share; left for a
  decision.
- **Removing a keyword from a wrapped call keeps the wrapped layout.** It
  stays valid code, just one line longer than needed.
- Known from the exit report: a no-op `at()` anchor can be left behind after a
  move; a bare line moved later delays the clip that shares its anchor; at
  15 fps a +0.3 s shift shows as 0.27 s.
- Locked play groups can be dragged: that edits their `at()`. Intended.

## 6. Results after the fixes

| | Before (`23db152`) | After |
|---|---|---|
| Pytest (`studio/tests`) | 202 unit tests + engine tests, all passing | **234 passed** (4 min 58 s), including 13 new regression tests in `test_review_phase4.py` |
| `npm run build` (strict `tsc`) | passes | passes |
| Corpus run (`corpus_run.py`, 27 files) | all byte-identical | all byte-identical; the only bad frame is the deliberate one in `late_error.py`; the only refusal is a colour edit on `eq` in `order_matters.py`, correctly refused because the code recolours it right after |
| Phase 4 exit script (`exit_phase4.py`) | 15 edits written, 1 refused (Takeaway line to 1.6 s: the grid-fade crash) | **15 of 15 written**, none refused (the Takeaway move now succeeds thanks to the `ClippedGrid` change); 15 undos restore the original bytes |

Browser pane, on a copy of `order_matters.py` (`tests/tmp/ui/om_ui.py`):
- play from 3.0 s: the sound starts at 3.0 (it started at 0 before the fix);
  the whole WAV is seekable; playback stops on the last frame;
- mute while playing applies at once; switching scene while playing stops
  the sound and releases it;
- trim of `Write(landing)`: `run_time=0.6` → `1.0` (was `1.0333`); move of
  that play: `at(6.6)` → `at(6.9)` (was `6.98`); ripple carries the later
  `at()` and `TARGET` by the same amount;
- box select (4 clips including a narration line) and a drag of one moves
  them all by 0.2 s, with an `at(0.2)` written before the line;
- markers: M adds one at the playhead with the next free name; with the
  add-line dialog open, M types into the dialog instead; Escape closes the
  dialog and keeps the clip selection;
- undo of every edit: the file is byte-identical to the original;
- `/idmap` for an old rev → 410, malformed rev → 400, `/audio` with
  `Range` → 206 / 416.

Not covered by hand: merge and split in the pane (covered by unit tests and
the exit script), and a narrated scene with `voiceover()` (no such scene in
the test copy; the caption-warning change has unit tests).
