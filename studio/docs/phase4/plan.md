# Phase 4 plan: the full timeline

PLAN.md §5, Phase 4: reorder, multi-select and ripple edits; overlapping
clips (per S4); an easing-curve editor; a narration track with
text-to-speech, audio tracks with waveforms, captions; sections and markers.

**Exit:** `order_matters.py` can be re-cut and re-narrated entirely in the
GUI. Concretely, without typing code:
- change the order of its scenes and of clips inside a scene;
- move, trim, overlap and re-ease clips, with ripple;
- rewrite, add, move and delete narration lines, and edit their captions;
- hear the result in the studio and get a render that passes
  `tools/audio_check.py`.

Rules: code_spec.md §4.4 (timing) and §1 (byte splices, verify by replay,
round trips close). Evidence: S4 (`phase0/S4_timing.md`).

## What exists today

- Timeline: one row of `play()`/`wait()` clips and one row per animated
  object. Trimming a clip's right edge writes `run_time=`, the `wait()` or
  the `at()` time. The Inspector edits `rate_func=` by name.
- The engine records every `play()`/`wait()` with its call site, but not
  narration: `say()` lines, captions and sounds aren't in the scene model.
- `TimedScene` (`manim_kit.py`) has `at(t)`, `say()`, `line()`, `TARGET`
  and burned-in captions. There is no `clip()` helper yet.

## Steps

| # | Piece | Where | Checked by |
|---|---|---|---|
| 1 | **Audio in the trace**: record every `say()` / `line()` (text, caption, requested and real start, length, audio file, call span, the `with` block's span), every caption shown (text, start, end) and every `add_sound()` (file, offset). `voiceover()` scenes (`pythagoras.py`) are recorded too, read-only, with their bookmarks. | `engine/runtime.py` | engine tests on `order_matters.py` and `pythagoras.py` |
| 2 | **`GET /audio`**: the scene's narration and sounds mixed into one WAV (PyAV, already installed), plus waveform peaks per line. Cached per revision. | `server/app.py`, new `server/audio.py` | unit test: length and peak positions match the trace |
| 3 | **Narration edits** (`edit.voice`): rewrite a line's text, set or clear its caption, move a line (its `at()`), add a line at the playhead (`with self.say("..."):` wrapping nothing → `self.say(...)` form, see decisions), delete a line (its statements stay, unwrapped). New text is synthesised by the trace through `edge_tts_service.py` as today. Captions over 70 characters or shown shorter than `len/15 + 0.3` s get a warning, not a refusal. | `code/timeline.py` (new), `project.py` | unit tests (quotes, raw strings, `\n`, non-ASCII, round trips); engine test |
| 4 | **Moving clips and groups**: drag a group → its `at()` literal (sequential scene: the `wait()` before it, inserted or removed). Drag one clip inside its group → `clip(anim, start=s)`, added and removed as in S4. Drag a clip onto another group → merge the two `play()`s; drag it out → split. Add `clip()` to `manim_kit.py` (3 lines, from S4). | `code/timeline.py`, `manim_kit.py` | unit tests; engine tests check the new times frame-exact (±1 frame) |
| 5 | **Multi-select and ripple**: Shift/Ctrl-click and box-select clips; move or trim them together as one edit and one undo step. Ripple (on by default, toggle `R`): every later `at()` moves by the same amount; `TARGET` grows or shrinks with it. | `project.py`, `web/src` | engine test: ripple on `order_matters.Question`, undo restores the bytes |
| 6 | **Reorder**: drag a clip before or after another → move whole statements within one block, refused when a statement in between reads a name the moved one assigns. In a `TimedScene` the `at()` anchors stay where they are and the clips swap times. **Scene order**: drag scenes in the scene list → rewrite the module's `SCENES = [...]` list (the concat order), and the docstring's "Render order" line if it names the same scenes. | `code/timeline.py`, `web/src` | unit tests (dependency refusal, comments carried with the statement) |
| 7 | **Easing editor**: a curve picker showing every named rate function in `manim.rate_functions` as a small plot, with the clip's motion previewed on the curve; writes `rate_func=` (removing it restores the default). | `web/src` | browser pane |
| 8 | **Sections and markers**: sections are Manim's own `self.next_section("name")`: shown as bands, added, renamed, moved and deleted from the timeline. Markers are the timeline's own: every `at()` anchor, line start and bookmark is a snap point; user markers (a name at a time) live in the browser, not in the file (see decisions). | `code/timeline.py`, `web/src` | unit tests; browser pane |
| 9 | **UI**: tracks for narration (text + waveform), captions and sounds; playback with sound (WebAudio, synced to the frame clock); snapping to anchors, line starts, markers and frames; drag clips and lines; Shift-drag to box-select; the code peek follows the selected clip or line. | `web/src` | browser pane |
| 10 | **Exit check**: re-cut and re-narrate `order_matters.py` through the UI on a copy; render it with `preview_server`'s render path; `audio_check.py` on each scene and the joined video; the corpus timing bench; exit report. | `docs/phase4/exit_report.md` | |

## Decisions taken here (unless you say otherwise)

- **Narration is written as `TimedScene.say()` / `line()`**, the form the
  repo already uses for multi-beat scenes. A new line added from the
  timeline is `with self.say("..."):` around the clips under it, or a bare
  `self.line("...")` when nothing is under it. `voiceover()` scenes
  (`Beat(VoiceoverScene)` in `pythagoras.py`) can have their text edited but
  not their timing, because `voiceover()` blocks and later marks drift.
- **TTS goes to Microsoft, as today.** Every new or changed line is sent
  to Edge TTS when the trace replays it; nothing else leaves the machine.
  Synthesis takes 1–3 s per line, so the timeline shows the line as
  "synthesising" until its length is known. With no network the line is
  refused with the reason, and the file is not changed.
- **Captions come from the code**: `caption=` on `say()`, else the spoken
  text. They are a derived row; editing one sets `caption=` (or removes it
  when it equals the spoken text).
- **User markers are not written into the file.** The `.py` file stays the
  only source of truth for the video, and a marker changes nothing in it.
  They are kept per file in the browser. Sections, which do change the
  output (`--save_sections`), are code.
- **The easing editor picks from named rate functions only.** A custom
  Bézier curve would need generated helper code (a lambda is tier 3);
  that can come later as a kit helper if you want it.
- **No new packages.** Audio decoding and mixing use PyAV and NumPy, both
  already installed with Manim.
- **`clip()` is added to `manim_kit.py`**, as code_spec §4.4 already says.
  It is the only change to a shared module in this phase.
