# Phase 4 exit report: the full timeline

**Exit criterion (PLAN.md §5):** `order_matters.py` can be re-cut and
re-narrated entirely in the GUI.

**Result: met.** A copy of `order_matters.py` was re-cut and re-narrated
with the edit messages the timeline sends. The result renders, passes
`check_layout.py` with the same warnings as the original, and passes
`tools/audio_check.py` on every scene and on the joined video. Undoing every
edit restores the original bytes exactly. Every kind of edit used was also
done by hand in the browser pane. Details and the rough edges follow.

## 1. The re-cut

Script: `studio/tests/exit_phase4.py`. It opens the copy in a `Document`,
the same object the server uses, and sends the edits a user makes on the
timeline. It does not run inside the browser. Output:
`studio/tests/tmp/exit/order_matters_recut.py`.

| # | Scene | Edit | Written as |
|---|---|---|---|
| 1 | Question | section at 0 s | `self.next_section("Opening")` |
| 2 | Question | drag the first group +0.3 s, ripple | `at(0.2)` → `at(0.5)`, 4 later `at()`s +0.3, `TARGET 7.5` → `7.8` |
| 3 | Question | overlap: blob fade starts 0.4 s into its group | `clip(FadeIn(blob, ...), start=0.4, length=0.8)`; `run_time=0.8` spread onto `FadeIn(title)` |
| 4 | Question | re-ease the title | `rate_func=rate_functions.ease_out_back` (wrapped under the paren) |
| 5 | Question | move the narration line to 1.8 s | `self.at(1.8)` before the `with` |
| 6 | Question | rewrite the words | new text, synthesised by Edge TTS on replay |
| 7 | Question | caption differs from the words | `caption="Rotate then shear, or shear then rotate: same result?"` |
| 8 | RotateThenShear | trim the first sweep | `run_time=1.8` → `1.4` |
| 9 | CompareMatrices | reorder: RS written before SR | the two `play()`s swap, `at()` anchors stay |
| 10 | CompareMatrices | add a line at 5.0 s | `self.line("...")`, placed at 5.6 s, after the running `play()` |
| 11 | CompareMatrices | push the fade-out later so the line ends first, ripple | `at(8.5)` → `at(10.4)`, `TARGET 9` → `10.9` |
| 12 | Takeaway | delete the narration line | `with` unwrapped; its 4 statements stay, dedented |
| 13 | Takeaway | add a new line at 1.8 s | `self.line("So read S R from the right: R happens first.")` |
| 14 | Takeaway | move it to 1.6 s | **refused**, see §3.1 |
| 15 | Takeaway | move it to 2.0 s instead | `self.at(1.8)` → `self.at(2)`; the `Write(rule)` after it starts 0.2 s later (reported) |
| 16 | file | scene order: Takeaway before CompareMatrices | `SCENES = [...]` and the docstring's wrapped "Render order" line |

Fifteen edits were written and one was refused, with its reason. Each took
1.5–6.8 s, including the replay that verifies it (68 s for all 16). Then
15 undos gave back `order_matters.py` byte for byte, and 15 redos gave the
re-cut again.

## 2. Checks on the result

- **Render:** `tools/timeline_render.py render -ql -a` rendered all five
  scenes; `tools/concat.py` joined them into
  `media/order_matters_recut_full.mp4` (48.1 s).
- **Audio:** `tools/audio_check.py` passed on all five scenes and on the
  joined video (audio 48.1 s / video 48.1 s, sound in 27 spans).
- **Layout:** `tools/check_layout.py` gives 0 errors and the same 3 warnings
  as the original file. They are mid-animation overlaps of the landing
  labels with grid lines, already in `order_matters.py`.
- **Frames:** I read the contact sheets for Question, CompareMatrices and
  Takeaway. The first CompareMatrices render left its new line's caption on
  an empty screen for 1.6 s after the fade-out. That came from my cut, not a
  studio bug, and the timeline did say "the scene is now 10.13 s". Edit 11
  fixes it; the re-render shows the line ending before the fade.
- **Tests:** 221 pass, engine tests included (§5).

## 3. Rough edges found

### 3.1 Takeaway can't take some timing edits (scene, not studio)

Moving Takeaway's line to 1.6 s was refused. On replay, `fade_all()` crashes
in `FadeOut` with `zip() argument 2 is shorter than argument 1`. Takeaway
fades out a `ClippedGrid` while its tracker is still turning. `manim_kit.py`
says not to do that: the grid's number of lines changes with the angle.
Whether it crashes depends on when the grid last redrew. A real render of
that code happened to work: its grid had 30 parts at the fade, the studio's
had 28, and a fresh draw has 26. So the real render is lucky, not correct.

The studio refuses the edit and leaves the file unchanged. The refusal now
says what is going on ("an object changed its number of parts while an
animation ran, most often a FadeIn/FadeOut of an always_redraw object (a
ClippedGrid) that is still moving ... fade it while it is still").

**Your call:** make `ClippedGrid` keep a constant number of parts (pad with
invisible lines). That would fix this for every scene and every render. It
changes `manim_kit.py`, so I haven't done it.

### 3.2 Leftover no-op anchors

Two edits leave a `self.at()` that does nothing:
- In Question, the line was moved to 1.8 s, so the `self.at(1.5)` inside its
  `with` block is already past.
- In Takeaway, `self.at(2.0)` comes before the line and `self.at(1.8)` after
  it.

The video is right in both cases, but the code reads as if something
happened at 1.5 s and 1.8 s. A clean-up pass that removes `at(t)` calls
that can no longer wait would fix both. I suggest doing it in Phase 5.

### 3.3 A bare line moved later delays the clip that shares its anchor

A bare `self.line()` runs at the time its `at()` sets. When the next clip
uses the same anchor, moving the line later moves that clip too. The
summary says so ("1 clip now starts 0.20 s later"). It can't be avoided
without moving the line into a `with` block.

### 3.4 Smaller things

- The ripple summary says "4 clips now start 0.27 s later" for a +0.3 s
  drag. At 15 fps the clips land on whole frames, so that is true, but it
  reads oddly. 0.27 is 4 frames.
- Adding a line in the middle of a running `play()` puts it after the
  `play()`, and the summary says where it went. The scene grows, and
  `TARGET` doesn't grow with it unless you ripple something.
- The scene-order edit was refused while the retrace after an earlier edit
  was still running. Fixed: `SCENES` belongs to no scene, so it is now
  verified against any traced one.

## 4. Fixed during the exit check

From testing in the browser pane and the re-cut:

- **Easing picker:** the grid opened under the timeline, so clicks landed on
  clips. It now renders on `<body>` and opens upward when there's no room
  below.
- **Easing names:** the picker offered `ease_*` curves that
  `from manim import *` doesn't export (`NameError`). They are now written as
  `rate_functions.<name>`.
- **Long keyword lines:** adding a keyword to a call nested in a long line
  left a 112-character line. The rest of the outer call now moves onto its
  own line too.
- **Duplicate `at()` (two cases):** adding a section or line at an existing
  `at(t)` wrote a second `self.at(t)`. That happened both when the `at()`
  ended exactly at t and when its end rounded just past t.
- **Docstring render order:** it wasn't updated when the list wraps over two
  lines.
- **File dropdown:** it showed the wrong file for test copies, which aren't
  in `/api/files`.

Each server fix has a unit test.

## 5. Tests

- Unit: 202 pass (`studio/tests/unit`).
- Full suite with engine tests (`pytest -q studio/tests`): 221 pass in
  4 min 6 s, after the last change.

## 6. Not done

- **Timing bench:** the plan's corpus timing bench wasn't run as a separate
  bench. The per-edit times above (1.5–6.8 s with verification) are the
  only timing evidence.
- **Re-cut through the UI:** the re-cut was made with the same edit
  messages, not by clicking through the UI. Each kind of edit was clicked
  through in the browser pane on its own. The exception is reorder, which
  was only refused in the UI (Question's plays all change `blob`); the
  re-cut wrote one in CompareMatrices.
- **High quality:** no high-quality render.

## 7. Recommendation

Go to Phase 5, after you decide on the `ClippedGrid` fix (§3.1). The no-op
anchor clean-up (§3.2) fits Phase 5's tier-1/tier-2 work.
