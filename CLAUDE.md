# Manim project — rules for Claude

Math/explainer animations made with **Manim Community Edition 0.22.1** on Windows,
driven from the Claude desktop app. The user previews videos in the app's browser
pane, not VS Code.

## Environment

- Manim CE 0.22.1 in `.venv` (Python 3.13). MiKTeX provides LaTeX; PyAV encodes
  video, so no separate FFmpeg is needed.
- Always run through the venv: `.venv/Scripts/python -m manim ...` (Bash) or
  `.venv\Scripts\python -m manim ...` (PowerShell). Bare `manim` is not on PATH.
- **CE only — never ManimGL.** Don't use `manimlib`, `from manimlib import *`,
  `ShowCreation`, `TexText`, `t2c=` on Tex, `self.frame`, `self.embed()`,
  `checkpoint_paste`, or `-se`. Tutorials/snippets from before 2021 or from
  3b1b/videos are ManimGL or old Cairo code; translate, don't paste.
- Don't install packages or change the environment without asking.

## Files

- `style.py` — palette, text sizes, safe area, named regions, `place()`,
  `grid_point()`. Every scene does `from style import *` and uses these instead of
  ad-hoc colours and coordinates.
- `preview_server.py` — live preview (launch config `manim-preview`, port 8765).
  Re-renders a file's scenes on save. Start it with the browser preview tool when
  the user wants to watch; don't start it if they didn't ask. Per scene it shows:
  - a timeline linked to the code (each `play()`/`wait()` with its source
    line, narration cues from the `.srt`, audio waveform; click to seek, and
    the line under it names the code running at the playhead);
  - an "outdated" badge when the scene file, `style.py` or `manim_kit.py` is
    newer than the video, or while it re-renders;
  - Compare: the previous render (kept in `media/preview_prev/`) next to
    the current one, in sync.
  The page fetches `/api/detail?video=<media path>` for timeline, cues and
  waveform.
- `tools/timeline_render.py` — `manim` with the same arguments, plus a
  `<Scene>.timeline.json` next to each video (start, duration and calling line
  of every `play()`/`wait()`). The preview server renders through it; scene code
  needs no changes. Plain `manim` renders leave the timeline out of date (the
  page says so).
- `tools/check_layout.py` — static layout check (no rendering). In a
  `ThreeDScene` it checks only screen-pinned text.
- `tools/frames.py` — renders and builds a contact sheet / exact frames.
- `tools/audio_check.py` — checks narration is really in the file: every
  `.srt` cue has sound under it; joined videos have an audio track
  (`--scenes <file>.py S1 S2 ... --quality l`, or a path to the full video).
- `tools/concat.py` — joins rendered scenes into one video. Video is remuxed;
  audio is rebuilt as one track, with silence for scenes without narration.
  The scenes' `.srt` cues are joined too (`<out>.srt`, shifted to each
  scene's start), so `audio_check.py` checks every cue of the joined file:
  `tools/concat.py media/<video>_full.mp4 --scenes <file>.py Scene1 Scene2 ... --quality h`.
- `tools/fixtures/` — deliberately broken scenes for testing the tools. Not content.
- **Never run two Manim renders of the same file at once.** On Windows they
  fight over LaTeX temp files (`PermissionError: WinError 32`). When the preview
  server is running, it re-renders on every save. In that case, start renders
  through it (`POST /api/render?file=...&quality=l`) and use
  `tools/frames.py --no-render`. `check_layout.py` is safe: it uses its own
  `media/Tex_check` folder.
- Plans for a video go in `plans/<video>.md` (see Workflow).
- `studio/` — the Manim Studio GUI project (a motion editor where the `.py`
  file stays the source of truth). Its plan, decisions and phases are in
  `studio/PLAN.md`; read it before any studio work. It is separate from
  `preview_server.py`, shares no code with the videos, and nothing in it may
  break the preview or the check tools. `README.md` maps the whole folder.
  Run it with launch config `manim-studio` (port 8770; rebuild the UI with
  `npm run build` in `studio/web` after changing it). Tests:
  `.venv/Scripts/python -m pytest -q studio/tests`; full corpus:
  `studio/tests/corpus_run.py`. Its workers share `media/Tex_studio`, so
  don't run studio tests while the studio server is busy.
- `tools/compare.py` — reference | ours frames side by side at matching times
  (`--ours clip.mp4 --ref-start <s> --at t1 t2 ...`). Used for recreations.
- `tools/analyze_reference.py` — contact sheets and cut list for a reference video.
- `manim_kit.py` — reusable parts, original code with no licence strings attached
  (`from manim_kit import *`):
  - `TimedScene`: absolute timeline `at(t)`, non-blocking narration
    `say(text, caption=)`, `line(text, caption=)` → `(start, end)` for
    landing visuals on the words, optional `TARGET` length lock. `CAPTIONS = True`
    burns in captions (hard cuts, minimum reading time); override
    `caption_mobject()` for the house look (see `Beat` in `order_matters.py`).
  - `Blob` character with moods, and `blink`.
  - `ThoughtCloud` / `thought_cloud_for`, `SpeechBubble` (opaque; add first,
    then `bring_to_front()` the contents).
  - `ClippedGrid`: linear-transformation grid clipped to a box or ellipse,
    driven by `.tracker`. `.snapshot()` gives a static copy of the end state.
    It keeps the same number of parts at every tracker value (invisible
    stand-ins for clipped lines), so it can be faded while it moves.
  - Helpers: `chain_matrices(step, ...)` (a step is a matrix, or `turn(θ)`
    for a real rotation), `lerp_matrix`, `rotation`, `bmatrix`,
    `video_icon`, `clip_rect`, `clip_ellipse`, and `clip(anim, start=,
    length=)` (an animation that starts `start` s into its `play()`; the
    studio writes it for overlapping clips).
  It changes no global config. Smoke test: `tools/fixtures/kit_parts.py`
  (`Parts`, `KitTiming`).
  Use it in new videos; never import `eola_common.py` there. Example videos:
  `order_matters.py` (2D), `gradient_descent.py` (2D and 3D, contour map,
  heightmap image).
- `eola_common.py` — recreation-only layer on top of `manim_kit` (2016 text
  size, `EolaScene`). Carries 3b1b's CC BY-NC-SA licence, which spreads to
  anything that imports it.

## Workflow for a new video or scene

1. **Plan first, in `plans/<video>.md`, and get the user's OK before coding**:
   goal and audience; the maths, checked; a beat list (one beat ≈ one Scene class,
   5–30 s each) with what is on screen, where (region), and what moves; narration
   lines if any; a notation/colour ledger (which symbol gets which colour — keep it
   consistent across scenes).
2. **Code one beat at a time.** One `Scene` subclass per beat, constants at the
   top, helpers named `get_*`, explicit `run_time=` and `self.wait()`.
3. **Run the check loop below** for each beat before moving on.
4. Only render high quality (`-qh`) when the user asks or approves the low-quality
   version.

## Check loop (after every change to a scene)

Never say a scene is done or fixed without running these and looking at the result.

1. `.venv/Scripts/python tools/check_layout.py <file>.py [Scene]`
   - Fix every ERROR. Fix WARNs unless clearly intentional (then say why).
   - It checks halfway through each animation too, because objects that are fine
     at the start and end can collide in between.
2. `.venv/Scripts/python tools/frames.py <file>.py <Scene>` then **Read**
   `media/review/<Scene>_sheet.png`. Use `--at <seconds>` to read exact frames
   full size, including mid-transition moments that look suspicious.
3. Review against this checklist, report at most the 3 most important problems,
   fix, and repeat (max 2–3 rounds before checking in with the user):
   - nothing overlapping, clipped, or off-frame
   - leftover objects removed (FadeOut/clear before reusing a region)
   - text readable (≥ `MIN_FONT_SIZE`), not too much text on screen at once
   - the eye knows where to look: one focus at a time, the rest dimmed (`MUTED`)
   - colours follow the plan's ledger and `style.py`
   - pacing: pauses after key reveals, nothing rushed
4. For narrated videos, run `tools/audio_check.py` on the scenes and on the
   joined video. Never say a video has narration without it: a frame review
   can't hear anything.
5. When the user mentions a timestamp ("at 0:12 the label jumps"), extract that
   exact frame with `frames.py --at 12` and look at it before editing.
6. When a render crashes, fix from the traceback starting at the failing line;
   widen to the block, then the scene, only if needed. Missing LaTeX or a codec
   error is an environment problem — report it, don't rewrite the scene around it.

## Narration and captions

- Voiceover is manim-voiceover 0.4.0 with Edge TTS through `edge_tts_service.py`
  (free Microsoft neural voices, no key; the narration text goes to Microsoft).
  The voice is `en-US-AndrewNeural` at -5%. Audio is cached in
  `media/voiceovers/`, so only new or changed lines are synthesised.
  `EdgeTTSService` overrides `_wrap_generate_from_text` so cache hits don't
  write `cache.json`: manim-voiceover 0.4.0 appends an entry on every line,
  hits included, which bloated and then corrupted the file. Keep the override.
  It also runs under a lock file (`media/voiceovers/.cache.lock`), so two
  processes meeting the same new line synthesise it once. Keep that too.
- Scenes subclass a `Beat(VoiceoverScene)` with a `say(spoken, caption=...)`
  context manager (see `pythagoras.py`). Animations inside the `with` block run
  during that line. Use `<bookmark mark='x'/>` in the spoken text plus
  `self.wait_until_bookmark("x")` to land an animation on a word.
- Captions:
  - One spoken line per caption, at most 70 characters.
  - Captions cut in hard; never fade two captions over each other.
  - Each caption stays up at least `len/15 + 0.3` s (15 characters per second
    reading speed).
  - The caption shows the written form (a², 90°, numerals). The spoken text
    spells things out ("A squared"; capital letters so the voice says "ay").
- To check caption timing after a render, compare each `.srt` start time with
  the next one (`media/videos/<file>/<quality>/<Scene>.srt`).
- The "SoX could not be found" warning on import is harmless; SoX is only used
  for speeding up audio, which we don't use.

## Narration timing (multi-beat scenes)

- `with self.voiceover():` waits for the audio at the end of the block, so
  absolute marks after it drift late. When visuals must hit fixed times, use a
  non-blocking `say()` that schedules audio with `add_sound(path,
  time_offset=...)` and drive visuals with `at(t)`: subclass `TimedScene` from
  `manim_kit.py`. Lines must never overlap: start each at max(now, end of
  previous line).
- Manim's `add_sound()` silently drops audio while `renderer.skip_animations`
  is on, and a cached `play()` leaves it on until the next play. So custom
  narration code must reset it first
  (`self.renderer.skip_animations = self.renderer._original_skipping_status`),
  as `TimedScene.say()` and manim-voiceover do. Symptom: narration present
  on the first render, missing on re-renders.
- Edge TTS can stall. `EdgeTTSService` has a hard 45 s timeout with retries;
  keep it. If a check or render goes quiet, look at CPU time before waiting
  longer.

## Recreating an existing video

Full write-up: `docs/recreation_learnings.md`.

1. Download with yt-dlp as separate video-only and audio-only streams (no
   FFmpeg needed). Run `tools/analyze_reference.py` for contact sheets, then
   pin section boundaries with a black-frame/spike scan.
2. Look for the source code first (3b1b: `github.com/3b1b/videos`,
   CC BY-NC-SA: credit it and stay non-commercial). Treat it as structure, not
   truth: matrices, colours and text can differ from the final cut.
3. Plan a shot list with reference start/end times; one Scene per section with
   `TARGET` = section length.
4. Narration, characters, logos and music that belong to the original creator
   are replaced with our own.
5. Loop: `check_layout.py` → render `-ql -a` → `tools/concat.py` →
   `tools/compare.py` at 20–30 timestamps. Before retiming a beat, check 2–3
   frames around it.
6. 2016 Manim differences: text ≈ 1.2× CE default (`font_size≈58`); `Arrow`
   and `Rectangle` defaulted to yellow, `Polygon` to green.
7. In a recreation, safe-area warnings from `to_edge` (gap 0.5 → |x| 6.61),
   full-width rule lines, and morphs that pass labels through each other are
   expected. Say so rather than "fixing" them.

## Layout rules

- Frame is 14.22 × 8 units. Keep content inside the safe area (|x| ≤ 6.5,
  |y| ≤ 3.5) and ≥ 0.5 from edges.
- Position with `place(mob, "title" | "main" | "left" | "right" | "footer")`,
  `grid_point(col, row)`, `next_to`, `arrange`, `to_edge`, `move_to` — not hand-typed
  coordinates.
- Long text: break lines manually, then `scale_to_fit_width` if still too wide.
- Clear a region before putting something new there; dim things next to new
  content, fade out things under it.
- Prefer few objects on screen; split into another beat rather than crowd.

## Manim CE 0.22 notes

- Don't chain `.animate` steps on the same mobject in a `Succession`: all
  targets are built up front from the starting state. Use
  `UpdateFromAlphaFunc`.
- A filled container (cloud, bubble) added after a label hides it: add the
  container first, then `bring_to_front()` the contents.
- `Union`/boolean ops need shapes wound the same way, or the overlap cancels.
- NumPy 2: `np.cross` rejects 2-D vectors; write the 2-D cross out by hand.
- To dim and undo, use `save_state()` + `.animate.fade(x)` + `Restore()`, not
  `set_opacity()`. `set_opacity` sets fill and stroke absolutely, so
  outline-only shapes (borders, frames) get filled, and "undoing" with
  `set_opacity(1)` paints them solid.
- Don't `FadeIn`/`FadeOut` an `always_redraw` mobject whose number of parts
  changes while it animates (crash: zip length mismatch). Fade while still,
  then animate, or keep the part count fixed with invisible stand-ins, as
  `ClippedGrid` does. Whether it crashes depends on frame timing, so one
  clean render proves nothing.
- A `run_time=` on `play()` overrides every animation in it. Without one,
  each keeps its own (`FadeIn(a, run_time=1)`, `b.animate(run_time=2)...`)
  and the play lasts as long as the longest. Delay one with
  `Succession(Wait(d), anim)`. `.animate....set_run_time()` does nothing.
  A motion that must outlast its `play()` needs an updater.
- A `wait()` with no time-based updater on screen (one that takes `dt`) is
  rendered as one frozen frame. Updaters without `dt` don't run during it, so
  anything they drive (a caption change, a readout) waits for the next
  `play()`. Give such updaters a `dt` argument.
- At the same `font_size`, LaTeX (`MathTex`, `Tex`, `DecimalNumber`) comes out
  much smaller than Pango `Text`: "slope" as `Text` was ~1.9× the height of a
  number at 36. Don't mix the two in one label; use `Tex` for the words.

- `MathTex` for maths (no `$`), `Tex` for LaTeX text with inline `$...$`, `Text`
  for plain text (Pango, no LaTeX). `Typst` mobjects also exist (0.21+) if LaTeX
  is a problem.
- Equation morphs: `TransformMatchingTex` (split the TeX into parts with `{{ }}`
  or `substrings_to_isolate`) or `TransformMatchingShapes`. Chains of transforms:
  `ReplacementTransform`.
- `.animate` only inside `self.play(...)`. Camera moves need `MovingCameraScene`;
  3D needs `ThreeDScene`.

### 3D (Cairo renderer)

Example: the 3D beats of `gradient_descent.py`.
- Narrated 3D scene: `class Beat3D(Beat, ThreeDScene)` (our `TimedScene` first).
  Kit captions pin themselves to the screen in 3D. Pin other screen text with
  `self.camera.add_fixed_in_frame_mobjects(m)`; the scene's own
  `add_fixed_in_frame_mobjects` also adds it, which may not be what you want.
- The camera draws parts marked `shade_in_3d` sorted by depth, one face at a
  time, then everything else on top. So a ball or arrow on a surface gets
  covered by nearer faces. Lift it a little and set `shade_in_3d = False` on
  its family so it is drawn last. `Line`s already are.
- `Surface(checkerboard_colors=False)` to turn the checkerboard off (`None`
  crashes). Faces have `u1, u2, v1, v2`: colour each one yourself by height.
  An opaque surface sorts more cleanly than a see-through one.
- `Transform(flat_surface, surface)` works when both have the same
  resolution: a neat way to raise a landscape.
- Looking straight down through the 3D camera gives a warped, perspective
  view. For a top-down view, cut to a separate flat 2D scene.
- Keep camera angles continuous across beats: end an orbit where the next
  beat starts (`set_camera_orientation(theta=end - rate * length)` at the start).
- Cost: a 32×32 surface took ~9 s of rendering per second of video at
  480p15, and ~38 s at 1080p60. Draft at low quality, or at a lower
  surface resolution.
- `check_layout.py` only checks screen-pinned text in a 3D scene. Review 3D
  objects with frames.
- CLI: `-ql/-qm/-qh` quality, `-a` all scenes, `-s` last frame only,
  `--format png|gif|mp4|webm|mov`, `-t` transparent, `-n a,b` animation range,
  `--save_sections`, `--dry_run`.
- `manim.cfg` only reads render settings from the `[CLI]` section; other
  section names are ignored.
- Output: `media/videos/<file>/<480p15|720p30|1080p60>/<Scene>.mp4`.

## Don'ts

- Don't delete or wipe `media/` (the cache makes re-renders fast).
- Don't use `-p` (opens an external player); the user watches in the preview pane
  or gets the file sent.
- Don't render high quality before low-quality frames pass review.
- Don't chain render → concat without stopping on a failed render (`|| exit`);
  concat will silently reuse stale clips.
