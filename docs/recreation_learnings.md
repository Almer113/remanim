# Recreation learnings (EoLA preview experiment)

A running log, written while recreating 3Blue1Brown's "Essence of linear algebra
preview". The final evaluation is at the bottom.

## Reference analysis

- **yt-dlp works without FFmpeg if you fetch streams separately.** Video-only
  (`-f "bv*[height<=1080][ext=mp4]"`) and audio-only (`-f "ba[ext=m4a]"`), plus
  `--write-auto-subs --sub-format vtt`. PyAV reads the VP9 stream fine. yt-dlp
  warns about a missing JS runtime; the download still worked.
- **3Blue1Brown barely cuts.** A fixed-threshold cut detector found 2 cuts in
  5 minutes. Scenes end in a fade to black or an animated morph. What worked:
  - A 1 fps contact-sheet pass (13 sheets for 5 minutes) gives a complete
    visual inventory.
  - A 10 fps scan for near-black frames and change spikes pins section
    boundaries to about 0.1 s.
- **Find the source first.** Grant's scene code for most videos is public at
  `3b1b/videos` (`_2016/eola/chapter0.py` here). It has exact matrices, words,
  colours and `run_time`s. It is CC BY-NC-SA 4.0, so a non-commercial
  adaptation must credit it and carry the same license.
- **The video was edited, not rendered in one go.** The source has comments such
  as `### Paste in linear transformation` and calls to `make_green_screen()`.
  Grids inside boxes and thought bubbles were rendered separately and composited
  in an editor. To get the same look in one Manim CE render, we clip the grid
  geometry ourselves.
- **The transcript is a timing map.** Cue timestamps show when talking starts per
  section (here, the voice starts at 0:12, after the quote). We use it for
  section topics and timing only; the narration is written fresh.

- **The published code is not always the final cut.** At 0:55 the video shows
  `[[1,0],[1,-1]]`, but the code's `EXAMPLE_TRANFORM` is `[[0,1],[-1,1]]`. The
  composition example shows `[[1,2],[2,1]]`; the code has `[[2,1],[1,2]]`.
  The frames are the ground truth; use the code for structure and styling.
  It goes further: in the numeric-vs-geometric shot the *numbers* show
  `[[1,0],[1,-1]]` while the *grid* plays the code's `[[0,1],[-1,1]]` (read off
  the frames: the yellow (1,2) vector lands on (2,1)). The tell was that our
  grid collapsed to a line mid-animation and the reference's never did:
  interpolating `I → [[1,0],[1,-1]]` passes through a singular matrix
  (det = 1 − 2t). Check each visual against the frames on its own; don't
  assume one shot uses one matrix.
- **2016 default colours differ from today's.** With no colour set, old Manim
  drew `Arrow` and `Rectangle` yellow and `Polygon` green. Manim CE defaults
  to white. Set those colours explicitly or the look is off.


## Building and checking

- **A network call with no hard deadline can stall a whole batch.** One Edge TTS
  request hung for about two hours, with edge-tts's own timeouts set and the
  process idle (3 s of CPU). `EdgeTTSService` now wraps each request in
  `asyncio.wait_for(…, 45)` with 4 retries. Signs of a hang: the log file stops
  changing, and CPU time stays flat.
- **Check scenes one at a time, under a watchdog, on long files.** One
  `check_layout.py file.py` call for 23 scenes gave no output until it hung. A
  per-scene loop with `faulthandler.dump_traceback_later(N, exit=True)` shows
  progress and prints a stack trace instead of hanging silently.
- **Don't name a helper script after a package.** A scratch `watchdog.py` was
  imported in place of the `watchdog` package Manim uses.
- **Chained `.animate` in a `Succession` is a trap.** Each `.animate` target is
  built when the line runs, not when its step starts. `Succession(eyes.animate
  .stretch(0.1), eyes.animate.stretch(10))` makes the eyes 10× tall halfway
  through. Use one `UpdateFromAlphaFunc` with `there_and_back`, or build the
  second step after playing the first. The layout checker caught this because
  the eyes went off-frame mid-animation.
- **Manim's default edge gap conflicts with our safe area.** `to_edge`/
  `to_corner` leave a gap of 0.5 (`MED_LARGE_BUFF`), so text lands at
  |x| = 6.61, just outside our 6.5 safe area. 3b1b positions everything this
  way, so in a recreation those warnings are expected; in our own videos, use
  `place()`.
- **`next_to` also centres along the other axis.** `Line(full width)
  .next_to(title, DOWN)` moves the line's centre under a left-aligned title, so
  half of it goes off-frame. Add `.set_x(0)`.
- **Expected checker hits in a recreation:** full-width rule lines (they touch
  the frame edge), exit moves that slide content off-screen, and morphs where
  many labels pass through each other (chapters → icons). Read each one and
  decide; don't "fix" what the reference does on purpose.


## Comparing against the reference (round 1)

- **The side-by-side sheet is the most useful tool in the loop.** One
  `compare.py` run over ~26 timestamps found more than all the layout checks:
  timing drift, a size mismatch, broken bubbles and a sparse grid. The layout
  checker can only judge a scene against itself, not against a target.
- **Timing locks per scene are not enough; time inside a scene drifts too.**
  Section lengths matched within 0.07 s, but visuals still ran seconds late.
  manim-voiceover's `with self.voiceover():` waits for the audio at the end of
  the block, so every `at(t)` after a long line was already past. A first fix
  (wait at the *start* of the next line instead) still held back the visuals
  queued behind it. What worked: `say()` puts the audio on the timeline with
  `add_sound(path, time_offset=start - now)`, where start is "now, or when the
  previous line ends", and never waits. The visuals follow the reference's
  clock through `at(t)`, as in a video editor; the voice fits into the gaps.
  After this, S05/S06 beats landed within a few tenths of a second.
- **A filled shape added after a label hides it.** A thought cloud has a black
  fill. Creating it after the "Linear Algebra" label covered the label and
  every topic morphed from it: the cloud looked empty. Add the container
  first, then `bring_to_front()` whatever lives inside it.
- **2016 text was about 1.2× today's default size.** We measured the same
  formula's width in both frames (sine series: 440 px vs 370 px) and set
  `Tex`/`MathTex.set_default(font_size=58)`. Grid units were similarly
  undersized (0.42 → 0.6).
- **Boolean shapes need matching winding.** `Union(ellipse, tail)` drew the tail
  as its own outlined sliver crossing the text: the ellipse runs
  counter-clockwise, the tail polygon ran clockwise, and the union cancelled
  instead of merging. Fix: reverse the polygon's points when its winding is
  wrong.
- **A transformed grid needs a bigger extent than an untransformed one.** A
  shear like `[[1,0],[1,-1]]` maps the ±12 grid to a diagonal band, so the box
  showed a stripe with empty corners. Use an extent of about 20 for anything
  that shears or squashes.

- **Look at 2–3 frames around a moment before retiming it.** One frame at 3:03
  suggested our S14 transform was late. Frames at 3:02.5, 3:03.5 and 3:05
  showed the reference was only starting its transform, and the original
  timing was right. A single frame can't tell "early in the motion" from "late
  in the motion".

## ManimGL 2016 → Manim CE translation

| 2016 (chapter0.py) | Manim CE 0.22 |
|---|---|
| `OldTexText("...")` | `Tex("...")` (LaTeX text, serif) |
| `OldTex("...")` | `MathTex("...")` |
| `ShowCreation` | `Create` |
| `VMobject(*mobs)` as a group | `VGroup(*mobs)` |
| `ApplyMethod(m.f, x)` | `m.animate.f(x)` |
| `matrix_to_mobject(M)` | `Matrix(M)` / `MathTex` with `bmatrix` |
| `Randolph`, `Mortimer` (Pi creatures) | our own `Blob` character |
| `ThoughtBubble`, `SpeechBubble` | our own, built with `Union` of shapes |
| `LinearTransformationScene` + editor compositing | `ClippedGrid` (lines clipped to a rect or ellipse) |
| `FRAME_X_RADIUS` | `config.frame_width / 2` |
| `digest_locals(self)` | normal attributes |


## Final evaluation

**Result:** `media/eola_preview_l.mp4`, 309.5 s against 309.3 s for the
reference. 23 scenes, each within 0.2 s of its section length. After three
compare rounds, the beats we checked land within a few tenths of a second.
Narration is original (Edge TTS), the characters are original, and there's no
logo or music.

**How close it got:**

| Aspect | Match | Notes |
|---|---|---|
| Section structure and timing | Very close | Timing lock + editor-style timeline (`at()`, non-blocking `say()`) |
| Maths content (formulas, matrices, chapter list) | Exact | From the licensed source, corrected against frames where the code differs |
| Layout and positions | Close | Measured from frames (box rects, bubble sizes); small offsets remain |
| Text size and font | Close | LaTeX Computer Modern; 2016 size ≈ CE × 1.2 |
| Grid transformations | Close | Analytic clipping reproduces the editor compositing; arrow weights and grid brightness differ slightly |
| Characters | Deliberately different | Original "Blob" design in place of Pi creatures |
| Narration and on-screen speech | Deliberately different | Our own words, so words and pauses don't line up with the original |
| 3D lattice (S18) | Approximate | Wireframe projection, less colourful than the original's 3D render |

**What the stress test showed about our method:**

1. *Our tools caught real bugs, but only against the scene itself.*
   `check_layout.py` found the blink bug (eyes ballooning mid-animation),
   clouds clipped at the frame edge and a misplaced rule line. It couldn't see
   that something was late, too small or the wrong matrix; that needed a
   reference. **`compare.py` was the most valuable new tool.**
2. *Timing is the hard part, not drawing.* Per-scene locks were easy. Keeping
   beats aligned *within* scenes needed the voice off the critical path:
   schedule audio on the timeline and drive visuals by absolute time.
3. *The source code speeds things up but isn't the truth.* About 90 % of the
   structure, words and colours came straight from chapter0.py. The
   remaining 10 % (two matrices, a grid that uses a different matrix from the
   numbers beside it, default colours and sizes) only showed up by comparing
   frames.
4. *The workflow scaled.* 23 scenes, one shared module (now split: the reusable,
   original parts in `manim_kit.py`; recreation-only settings in
   `eola_common.py`), and
   a check → render → concat → compare loop of about 10 minutes for a full
   low-quality pass.
5. *Failure modes worth guarding:* network calls without hard timeouts, chained
   `.animate` in `Succession`, fill-covered labels, boolean-shape winding,
   NumPy 2 API changes (`np.cross` on 2-D), and scripts that keep going after a
   failed render (the concat silently reused stale clips once).

## Follow-up: testing manim_kit on a new video

`order_matters.py` (plan: `plans/order_matters.md`) is 45 s, narrated, in the
house `style.py` look, and uses every kit part. What the test found:

- **Missing: on-screen captions.** Our house style burns captions in, but a
  non-blocking `say()` can't show and hide a caption around a `with` block.
  Added to `TimedScene`: captions are scheduled on the same timeline (hard
  cuts, len/15 + 0.3 s minimum), and the next line waits until the caption
  has been read.
- **Missing: proper rotation steps.** `chain_matrices` blended every step
  linearly, so a 90° turn shrank the grid to 71 % halfway. Added `turn(θ)`
  steps.
- **Missing: freezing a finished grid.** Carrying the end state into the next
  scene, or dimming it, needed a static copy: `ClippedGrid.snapshot()`.
- **Bug found by the check loop: fading a changing grid.** `FadeIn` on a grid
  that was already turning crashed, because its line count changes from frame
  to frame. Rule: fade while still, then animate.
- **Bug found by the frame review: `set_opacity` dimming.** Dimming a panel
  with `set_opacity(0.3)` filled its outline-only border grey, and restoring
  with `set_opacity(1)` painted it solid white. Use `save_state` / `fade` /
  `Restore`.
- **What worked first time:** timeline timing (every beat within 0.03 s of
  TARGET), bubbles and clouds with `fill_color=BG`, both clip shapes, the
  character's moods, blink and gaze, and `style.py` integration.

Side effect for the recreation: the next line now also waits for the previous
caption's minimum reading time, so re-rendering `eola_preview.py` could shift
a few narration starts slightly. The 1080p file was rendered before this
change.

## Follow-up: the narration was missing, and nothing caught it

The user noticed `order_matters_full.mp4` had no sound. Measuring showed:
- `eola_preview_full.mp4` (1080p) had no audio track either.
- One recreation scene and one test scene were missing lines.

**Cause 1 (kit):** a cached `play()` sets `renderer.skip_animations` and leaves
it on until the next play, and `add_sound()` drops audio while it's on. Our
non-blocking `say()` called `add_sound()` directly, so a line that started
right after a cached animation vanished. First renders were fine and
re-renders lost lines, which is why it looked random. manim-voiceover resets
the flag before adding sound; `TimedScene.say()` now does too. Verified with
renders that reused 25, 4 and 4 cached animations: narration intact.

**Cause 2 (concat):** `tools/concat.py` kept audio only if *every* clip had an
audio track. One scene without narration (a title card, or a scene that had
lost its lines) silently dropped the whole track. It now rebuilds one
continuous track, with silence where a clip has none.

**Process lesson:** every check we had was visual: layout, frames,
side-by-side. Nothing listened. `tools/audio_check.py` now makes sure there's
sound under every subtitle cue and that the joined video has an audio track,
and it's part of the check loop in CLAUDE.md. Before saying "narrated",
measure it.

## Follow-up: a harder test, gradient descent in 2D and 3D

`gradient_descent.py` (plan: `plans/gradient_descent.md`): 11 beats, about
2:10, 4 of them in 3D.

**What worked first time**
- `TimedScene` combined with `ThreeDScene` (`class Beat3D(Beat, ThreeDScene)`).
- Our own contour lines (marching squares, ~25 lines) plus a heightmap image
  coloured on the same scale as the 3D surface. The 2D map and the 3D surface
  read as the same landscape.
- Timing visuals from narration: a `line()` helper returns each line's start
  and end on the timeline, so `at(start + 0.5)` lands on the words even when a
  line has to wait for the previous caption.
- Checking the maths numerically before planning. Every failure case (too
  big a step jumping the ridge, the local minimum) happens for real.

**What went wrong, and the fixes**
1. **Captions froze during waits.** This was a kit bug that order_matters had
   too. Manim renders a `wait()` as one still frame when nothing on screen has
   a time-based updater (one taking `dt`), and the caption updater didn't take
   `dt`. A caption due to change mid-wait stayed up until the next animation.
   It was invisible in 2D because animations usually covered the changes, and
   obvious in a 3D beat with a long static hold. Fix: give the updater a `dt`
   argument.
2. **3D drawing order.** The camera sorts shaded parts by depth, face by face,
   so nearer surface faces covered the arrows. Fix: lift them and mark them
   unshaded, so they are drawn last.
3. **Camera framing.** At the first camera angle the start point was on the
   far side and nearly hidden. The landscape is symmetric front to back, so the
   starts were mirrored to the near side (same maths, y flipped).
4. **Text sizes.** LaTeX numbers next to Pango text looked half-size at the
   same `font_size`. Set both in LaTeX.
5. **Pacing.** The first cut was 2:43 with up to 9 s of silent hold at the
   end of beats. Cutting each beat to its last visual or line plus about 1 s
   gave 2:10.
6. **Clutter.** The first gradient demonstration was drawn on the path itself,
   where "uphill" points straight back along the path. A clear spot on the map
   reads better.

**Tooling:** `check_layout.py` now checks only screen-pinned text in 3D
scenes. Frame review found every problem above; the checker found only
smaller ones (labels on the path in `TooBig`, text 0.01 past the safe area).

**Cost:** about 9 s of rendering per second of 3D video at 480p, and 38 s at
1080p60. One full low-quality pass of all 11 beats took about 12 min.
