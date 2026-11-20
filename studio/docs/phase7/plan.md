# Phase 7 plan: what the first real video showed

The first real video made in the studio (`euler_identity.py`, 2026-11-20,
friction log in `plans/euler_identity.md`) worked, but sent me to the code
for things the studio should do, and hit one crash (fixed) and two traps.
This phase closes those, plus the small items left open after Phase 6. No
new big features.

**Exit:**
- a second real video is made with the friction log's code-only steps
  done in the studio instead: add the scenes, set each scene's length,
  narrate a silent scene, retime without leaving a fade over a spoken
  line. The only code written by hand is what the studio can't express
  (custom maths, updaters, helpers);
- that run's own friction log has no "blocks" entries;
- tests and the corpus run green, `preview_server.py` and the check tools
  untouched in behaviour.

Rules as before: code_spec.md §1 (byte splices, verify by replay, round
trips close). Each milestone ends with tests green and a hands-on pass in
the browser pane, and is a natural point to commit.

## What exists today

- **Scene arrows:** ◀ ▶ beside the scene dropdown send `edit.scene_order`
  (`App.tsx:631`): they reorder the file's `SCENES` list. They sit where
  prev/next buttons usually are; I clicked ▶ for "next scene" and it
  rewrote the render order (undo restored it).
- **New file:** `window.prompt` (`App.tsx:452`). The browser pane throws
  "prompt() is not supported", so the button silently does nothing there.
- **Scenes:** the template (`inserts.py:639`) writes one scene. There is
  no way to add another.
- **`TARGET`:** shown as a "TARGET 12 s" chip (`App.tsx:746`), not
  editable. The padding at the end is a locked clip labelled "timed by
  library code() (line None)" (`project.py:649`). A ripple move of a group
  shifts `TARGET` with it (`timeline.py:792`); retiming a pause or a
  `run_time` doesn't, so a shortened scene stays padded to its old length.
- **Narration:** `+ line` is enabled in a scene with `VOICE = None`, and
  the edit is refused with a message saying to set a voice. Nothing warns
  when a `FadeOut` lands while a line is still being spoken.
- **Inspector:** a computed `at()` (`1.2 + 3.2 * k`) looks editable and
  is refused only after Enter. After a `.scale()` edit the field still
  shows 1. A move made by a helper is written as `0.2419 * LEFT`.
- **Layout:** canvas and timeline have fixed shares; with many lanes the
  canvas is small (a label was a few pixels wide at 1440×900).
- **Timeline:** clicking an empty part of a lane doesn't seek (only the
  ruler does); clicking a lane's name doesn't select its object.
- **Layers:** "Nothing selectable on screen" while a frame's objects are
  still loading.
- **Accessibility:** buttons whose `title` differs from their text have
  the tooltip as their accessible name ("A new scene file from the studio
  template" for "+ New file").
- **Carried from Phase 6:** undo's frame isn't seeded from the frame
  cache (a replay after every undo); the page retries a lost connection
  every second with no backoff; frame times in a visible pane have never
  been measured.

## Steps

### A. Traps (first, they cost the most)

| # | Step | Where | Tests |
|---|---|---|---|
| 1 | **Scene arrows navigate.** ◀ ▶ (and `PageUp` / `PageDown`) go to the previous and next scene; at either end they're disabled. Reordering moves into the dropdown: a small "Render order…" entry opens a list with ↑ ↓ per scene (one edit per move, as now). The keymap and help sheet list both. | `App.tsx`, `keymap.ts` | keymap unit test (no duplicate keys); browser pane: arrows never write the file |
| 2 | **New file in an app dialog.** A small dialog: file name (default `my_scene.py`), scene class name (default from the file name), voice on/off (sets `VOICE` to the house voice or `None`), `TARGET` (blank = none). Name checks stay on the server (`file.new` already refuses bad names and existing files). Esc and Cancel close it. | `App.tsx`, new `NewFileDialog.tsx`, `server/code/inserts.py` (template takes the options) | unit: template with each option parses and traces; browser pane: create a file in the pane |

### B. What sent me to the code

| # | Step | Where | Tests |
|---|---|---|---|
| 3 | **Add a scene.** "+ scene" next to the dropdown: a name, and "after this scene" or "at the end". It writes a new class after the current one, with the same base class as the current scene (so `Beat(TimedScene)` stays `Beat`), `TARGET` if the current scene has one, and `construct()` holding only what the base needs (nothing for a `Beat`, `apply_background()` as in the template otherwise). If the file has a `SCENES` list, the name goes in at the same place. One edit, one undo step, verified by tracing the new scene. Delete scene and rename scene: in the same menu, refused when other code names the class. | `server/code/inserts.py`, `server/project.py`, `App.tsx` | unit: insert into files with and without `SCENES`, with a custom base, with decorators; corpus files: add then undo is byte-identical |
| 4 | **Edit `TARGET`.** The chip becomes a field: type a length, or "fit" (content end + 0.1 s: the last clip or the last narration line, whichever ends later). A scene with no `TARGET` gets "+ target" for `TimedScene`s. Retiming a pause or a `run_time` with ripple on also shifts a literal `TARGET` by the same amount, as a group move already does; the toast says so. The padding clip reads "padding to TARGET" with the `TARGET` line, not "library code (line None)". | `server/code/timeline.py`, `server/code/planner.py`, `server/project.py`, `App.tsx` | unit: TARGET set, fit, ripple on pause and run_time edits, computed TARGET refused with a reason; the six Euler beats re-done this way give the same lengths |
| 5 | **Narrating a silent scene.** `+ line` in a scene with `VOICE = None` asks once: "This scene has no voice. Use the house voice (en-US-AndrewNeural)?" Yes sets `VOICE` on the scene's class (or on its base, if the base is the file's own and every scene of it is silent: asked), then adds the line, as one undo step. | `server/code/inserts.py`, `server/project.py`, `Timeline.tsx` | unit: VOICE set on class vs base; browser pane: from a fresh template to a spoken line with captions |

### C. Narration safety

| # | Step | Where | Tests |
|---|---|---|---|
| 6 | **Warn when things leave mid-sentence.** After every trace, find animations that remove objects (`FadeOut`, `Uncreate`, `ShrinkToCenter`, and helpers such as `fade_all` that play them) that start while a narration line is playing and end before it. Mark the clip on the timeline (a small speech-bubble badge) and say once in the edit's toast: "fades out 1.4 s before 'After π, it's halfway…' ends". A warning, never a refusal. | `server/project.py` (scene model), `Timeline.tsx` | unit: the Euler `Walk` case from the log (fade at 9.27 s, line to 10.6 s) is flagged; the fixed version isn't |
| 7 | **Snap to the narration.** When dragging or editing a pause end, clip start or `at()` time, the end of each narration line is a snap point (like clip edges now), and "end of line" is offered in the pause field's menu. | `Timeline.tsx`, `Inspector.tsx` | browser pane |

### D. Inspector, timeline and layout polish

| # | Step | Where | Tests |
|---|---|---|---|
| 8 | **Read-only up front.** Fields whose value is computed (an `at()` from an expression, a `run_time` from a variable, a helper's argument used elsewhere) show the value greyed with the reason on hover, instead of refusing after Enter. The server already knows (`plan_timing` raises the reason); the scene model carries it per field. | `server/project.py`, `Inspector.tsx` | unit: each refusal reason now arrives in the model; browser pane |
| 9 | **Inspector values after an edit.** Scale and turn show the object's current scale and rotation (from its points, as position already is), so a chained `.scale(1.3)` reads 1.3. Moves and shifts are written to 2 decimals (`0.24 * LEFT`), unless the user typed more. | `Inspector.tsx`, `server/code/` (number formatting for moves) | unit: move formatting; existing drag tests still close |
| 10 | **A splitter between canvas and timeline**, dragged or double-clicked to reset; the share is remembered per browser (localStorage, wrapped as now). Also the existing panels' minimum sizes checked at 1100–1920 px wide. | `App.tsx`, `styles.css` | browser pane at three widths |
| 11 | **Timeline clicks.** A click on an empty part of a lane seeks there (as the ruler does). A click on a lane's name selects that object (as Layers does). | `Timeline.tsx` | browser pane |
| 12 | **Small ones.** Layers says "loading…" while the frame's objects are on their way. Buttons get accessible names that match their text, with the tooltip as a description. | `App.tsx`, `Layers` | browser pane (`find` sees "New file") |

### E. Carried from Phase 6

| # | Step | Where | Tests |
|---|---|---|---|
| 13 | **Undo's frame from the frame cache.** Undo restores exact bytes, so the frame for those bytes is already cached (same key: bytes, scene, frame). Use it instead of a replay; fall back to the replay if it isn't there. | `server/project.py` | engine test: undo after an edit shows the frame with no replay (counter) |
| 14 | **Reconnect with backoff:** 1 s, then 2, 4, up to 10 s; at once on focus or when the network comes back. | `api.ts` | unit-ish test of the delay sequence; browser pane (stop and start the server) |
| 15 | **UI frame time in a visible pane.** Add a frame-time probe (`performance.now()` per animation frame while scrubbing `eola_preview.py`) and record it in the bench; target from Phase 6: no frame over 50 ms. | `web/src`, `tests/speed_run.py`, `docs/phase7/` | the measurement |

### F. Exit

| # | Step | Where |
|---|---|---|
| 16 | **Exit check.** A second real video, planned in `plans/` first (topic picked with you), made in the studio with the steps above, exported at `-ql` then `-qh`, narration checked. Who drives is your call (question 1). Its friction log, the full test suite, the corpus run, the clip and drag benches against Phase 6, and an exit report. | `docs/phase7/exit_report.md`, `plans/<video>.md` |

Order: A, then B (the biggest win), C, D, E, F. Commit after each group.

## Not in this phase

- z moves in 3D and an out-of-camera view in 2D: real work, and nothing
  in the first video needed them. They stay open.
- A name and licence: your decision, needed only before open-sourcing.
- A desktop wrapper: `--app` covers it.

## Decisions taken here (unless you say otherwise)

- "+ scene" copies the current scene's base class and `TARGET`, nothing
  from its `construct()`. Copying the body would be "duplicate scene",
  which can come later if wanted.
- The mid-sentence warning is a warning only. Some fades over speech are
  deliberate.
- `PageUp` / `PageDown` for previous/next scene (they aren't taken; Alt+
  arrows are nudges).
- Moves are rounded to 2 decimals (0.01 units ≈ 1.4 px at 1080p), which
  is finer than anyone can see.

## Questions

1. Who drives the exit video: you (the better test of the studio; I
   write the plan and help), or me in the pane as last time?
2. Anything from "Not in this phase" you want in after all?
