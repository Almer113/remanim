# Manim Studio: plan

A motion-editor GUI for Manim, inspired by After Effects, CapCut and Figma,
where the `.py` file stays the only source of truth. Write in code and edit in
the GUI, or create in the GUI and edit in code.

"Studio" is a working title. At least five unrelated projects are already
called "Manim Studio", so a real name is needed before any public release.

Status: Phase 0 done (go). Phase 1 done: wireframes and code specification
approved 2026-11-18. Phase 2 done 2026-11-18: exit criteria met
(`docs/phase2/exit_report.md`). Phase 3 is next.

## 1. Decisions already made

| Question | Decision |
|---|---|
| Round-trip model | Tiered editing, always lossless (section 3). No restricted dialect, no separate project format. |
| Audience | The user first. Structured so it can be open-sourced on GitHub later. |
| Effects | Manim-native only: animations, easing, indications, camera moves. No pixel effects (blur, glow). |
| First milestone | Open and edit existing files. Blank-canvas creation follows from it. |
| Engine | Manim CE only, pinned to 0.22.x, behind a thin adapter layer. No ManimGL. |
| Form | Local web app: Python backend on this machine, browser UI. Optional desktop wrapper later. |
| Relation to the preview | Separate. `preview_server.py` stays as the viewer for AI-driven work. |

## 2. Goals and non-goals

**Goals**
- Open any Manim CE scene file and play it: timeline, canvas, every block
  linked to its source line.
- Edit visually: drag, scale and rotate objects; trim, move and reorder clips;
  change properties, colours and easing; add objects and animations by drag and
  drop.
- Every GUI edit is a small, readable change to the `.py` file.
- Every code edit (by hand or by Claude) shows up in the GUI without a restart.
- Everything Manim can do plays in the studio, because the studio runs real
  Manim.

**Non-goals for v1**
- Pixel effects, compositing, masks, or anything with no Manim code equivalent.
- ManimGL, hosted or multi-user operation, mobile, a plugin marketplace.
- Replacing the code editor. The studio links to code; it is not an IDE.

## 3. The round-trip model

### Playing and editing are separate promises

- **Everything plays.** The engine runs the real scene. 3D, updaters,
  `manim_kit`, custom classes: all appear on the canvas and the timeline.
- **Editing is graded** by how the code that produced a thing is written:

| Tier | What it covers | What the GUI can do |
|---|---|---|
| 1. Fully editable | Plain statements with literal arguments: `c = Circle(radius=1)`, `c.move_to(...)`, `c.set_color(BLUE)`, `self.play(Create(c), run_time=2)`, `self.wait(1)` | Everything. An edit rewrites exactly the tokens involved. |
| 2. Tweakable | Objects and animations produced by loops, helper functions or computed values | Select, inspect, retime. Edit the literal a value traces back to, or add an override statement after it. |
| 3. Code-only | Updaters, `always_redraw`, custom `Animation` classes, anything dynamic | Shown, timed and playable, but locked. A click jumps to the source line. |

The share of tier 1 and 2 grows over time as the studio learns more code
patterns. Nothing is ever unsupported: at worst it is tier 3.

### Lossless guarantees (these are tests, not aspirations)

1. **No-op safety:** opening and saving a file without edits changes zero bytes.
2. **Minimal edits:** a GUI edit changes only the tokens it targets. Comments,
   formatting and unrelated code are untouched.
3. **GUI code is tier 1:** anything created in the GUI is written as tier-1
   code, so it reopens fully editable.
4. **No hidden state:** rendering the file with plain `manim` gives the same
   video as the studio. Studio-only data (track order, collapsed panels, colour
   labels) lives in an optional sidecar file. Deleting it loses nothing that
   affects the video.
5. **Undo is exact:** undoing an edit restores the file byte for byte.

## 4. Architecture

```
 Browser UI  <── WebSocket + HTTP ──>  Studio server (Python)
 canvas, timeline,                      ├─ Code layer: parse, locate, edit the .py
 inspector, library                     ├─ Engine: resident Manim process
                                        ├─ Project: file watching, undo history, sidecar
                                        └─ Export: full renders through plain manim
```

### Engine (the resident Manim process)

Extends what `tools/timeline_render.py` and `tools/check_layout.py` already do.
- **Trace:** run the scene with rendering off and record every `play()` and
  `wait()` with start, duration, source line and the animations inside it.
- **Identity:** map each on-screen object to where it was created (file, line,
  variable name, loop index), so a click on the canvas finds the code.
- **Frame at time t:** restore the state at the nearest animation boundary,
  advance the running animation to `t`, render one frame. Fallback: replay the
  scene up to `t` without rendering, then render one frame.
- **Geometry:** bounding boxes, anchors and (for 3D) projected screen positions
  of every object, so the browser can draw selection handles.
- **Isolation:** the engine is a child process. A crash, an infinite loop or a
  syntax error in the scene never takes the studio down; the UI keeps the last
  good state and shows the error.

### Code layer

- Python's built-in `ast` gives the exact source range of every node. Edits are
  text splices at those ranges, which is what keeps guarantee 2. (`libcst` is
  an option later if insertions get complicated; it would need installing.)
- A **pattern library** recognises tier-1 statements and knows how to edit
  them: change a literal, add or remove a keyword argument, insert a statement
  with the right indentation, reorder statements.
- External changes (hand edits, Claude Code) are picked up by a file watcher,
  re-parsed, and matched back to the current selection by identity.

### Timing model

Manim's timing is implicit in the order of `play()` calls. The studio shows it
as clips on a timeline and maps edits back:

| Timeline edit | Code change |
|---|---|
| Trim a clip | `run_time=` on that `play()` |
| Change a gap | the `wait()` between two plays |
| Reorder clips | move statements |
| Change easing | `rate_func=` |
| Stack clips (same start) | several animations in one `play()` |

Two harder cases are open design questions for Phase 0:
- **Overlapping clips with different starts.** Candidates: one `play()` with
  per-animation delays (`Succession(Wait(d), anim)`, `lag_ratio`), or a small
  importable helper. Preference: plain Manim code first, a helper only if
  plain code gets unreadable.
- **Absolute time.** `TimedScene.at(t)` from `manim_kit.py` maps directly onto a
  timeline. The studio should understand it, and may offer it as the style for
  GUI-made scenes.

### UI

| Area | Inspiration | Contents |
|---|---|---|
| Canvas | Figma | The real Manim frame, with selection handles, drag/scale/rotate, snapping to the safe area and `style.py` regions, alignment guides |
| Timeline | After Effects, CapCut | Tracks of clips, playhead, trim and drag, narration, audio waveform, captions, easing-curve editor |
| Layers | Figma, After Effects | The scene's object tree (groups and their children), visibility at the playhead, tier badge |
| Inspector | Figma | Properties built from each class's constructor signature; colours from the palette; LaTeX editor with live preview |
| Library | CapCut | Mobjects, animation presets, `manim_kit` parts (Blob, bubbles, grids), images and SVGs; drag onto canvas or timeline |
| Code peek | | The lines behind the current selection, with a button to open the file |

### Technology

- **Backend:** Python in the project's `.venv`. `aiohttp` (already installed)
  for HTTP and WebSockets, `ast` for the code layer, `watchdog` for file
  watching. No new Python packages needed for Phase 0.
- **Frontend:** TypeScript with React and Vite. Node 24 and npm are installed.
  Installing npm packages inside `studio/web/` needs the user's OK when Phase 2
  starts. Phase 0 spikes use plain JavaScript with no build step.
- **Desktop wrapper (later, optional):** Tauri or similar around the same UI.

## 5. Phases

Each phase ends with something usable and a written check against its exit
criteria. Sizes are relative (S, M, L, XL); no dates until Phase 0 shows how
hard the core is.

### Phase 0. Feasibility spikes (M)

Throwaway prototypes that answer the questions the whole design rests on.

**Status (2026-11-18): done, all bars met, recommendation go.** Results and
plan changes: `studio/docs/phase0/go_no_go.md`, one write-up per spike next
to it.

| Spike | Question | Pass bar |
|---|---|---|
| S1 Frame at time | Can the engine show any moment of a scene quickly? | Median under 0.5 s for 2D scenes in this repo, under 2 s for 3D |
| S2 Round-trip edit | Can a canvas drag become a minimal, correct code edit? | Drag an object in `test_scene.py` and in `order_matters.py`; diff touches only the intended tokens; no-op save is byte-identical |
| S3 Identity | Can a click on the canvas find the creating line, including in loops and helpers? | Correct for at least 95% of objects across the corpus |
| S4 Timing | Can overlapping clips be written as readable plain Manim? | A written recommendation with code samples for each timeline edit |
| S5 Coverage census | How much real code is tier 1, 2 or 3? | A measured breakdown over the corpus, to size later phases |

**Exit:** a go/no-go note. If S1 or S2 fails, the plan changes before any
product code is written.

Also in this phase: `git init` (with the user's OK; the project has no version
control yet, and a tool that rewrites source files needs it).

### Phase 1. Design (M)

- Architecture document and the engine↔UI protocol.
- The editable-code specification: every tier-1 pattern, how each GUI edit
  maps to code, and the generated-code style guide.
- UX wireframes for the five UI areas and the main flows.
- The compatibility corpus: the Manim CE docs gallery, this repo's videos, and
  a set of deliberately awkward files.
- Test strategy (section 6).

**Exit:** the user approves the wireframes and the code specification.

**Status (2026-11-18): done; the user approved the wireframes and the code
specification.** `docs/architecture.md`,
`docs/protocol.md`, `docs/code_spec.md`, `docs/wireframes/index.html`,
`docs/corpus.md` (+ `tests/corpus/awkward/`), `docs/testing.md`.

### Phase 2. The viewer that edits (L)

Open any file. Timeline with clips linked to code. Scrub and play. Select
objects on the canvas and in the layers panel. Inspector shows properties.
First edits: `run_time`, waits, literal property values, colours.

**Exit:** all corpus files open and play; no-op save is byte-identical for all
of them; retiming and property edits round-trip on tier-1 code.

### Phase 3. Direct manipulation (L)

Drag, scale and rotate on the canvas, written back to code. Snapping and
alignment guides. Add objects and animations from the library by drag and drop.
Delete, duplicate, group. Undo and redo. Tier-2 overrides.

**Exit:** a short scene can be built from a blank file without typing code,
and the result reads like hand-written Manim.

### Phase 4. Full timeline (L)

Reorder, multi-select, ripple edits. Overlapping clips (per S4). Easing-curve
editor. Narration track with text-to-speech, audio tracks with waveform,
captions. Sections and markers.

**Exit:** `order_matters.py` can be re-cut and re-narrated entirely in the GUI.

### Phase 5. Coverage (XL)

LaTeX and text editing with part-level colouring. Graphs and axes. Transform
and matching-transform pairs. Camera moves. 3D scenes (camera gizmo, projected
handles). Presets. More tier-1 and tier-2 patterns, driven by the census.

**Exit:** measured against the corpus: every file plays, and the editable share
meets the target set after S5.

### Phase 6. Polish and release readiness (M)

Export dialog (quality, format, joined video). Keyboard shortcuts. Performance
passes. Error and recovery UX. Docs. Optional: desktop wrapper, a Claude panel,
a real name and licence for open-sourcing.

## 6. Testing

- **Round-trip suite:** for every corpus file: open → save is byte-identical;
  each edit → undo is byte-identical; GUI-generated code reopens as the same
  model.
- **Render equivalence:** frames from the studio match frames from plain
  `manim` for the same file.
- **Edit fuzzing:** random sequences of GUI edits on corpus files; the file
  must always still parse and render.
- **Existing tools:** `check_layout.py`, `frames.py` and `audio_check.py` run on
  GUI-made scenes like any other.
- **UI checks:** driven through the browser pane, as with the preview server.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Round-trip on arbitrary Python is harder than the tiers suggest | S2, S3 and S5 measure it before product work; tier 3 is always available as the safe fallback |
| Preview too slow (LaTeX, 3D, long scenes) | S1 sets the bar; snapshots at animation boundaries; low-resolution frames while scrubbing |
| Manim internals change (0.22 moved to a `Manager`; more refactors are under way) | Pin the version; keep all engine hooks behind one adapter module |
| Scope: "full After Effects" is decades of work | Phases with usable exits; Manim-native effects only; census-driven coverage |
| The studio corrupts a source file | Guarantees 1, 2 and 5 as tests; edits are atomic writes; git from Phase 0 |
| Scenes that depend on randomness or wall-clock time | Seeded runs in the engine; flag non-deterministic scenes |
| GUI and Claude edit the same file at once | The file is the only state; the studio re-reads on every change and never holds unsaved edits |

## 8. Folder layout

```
studio/
  PLAN.md          this file
  docs/            design documents (Phase 1)
  spikes/          Phase 0 prototypes, throwaway
  server/          Python backend: engine, code layer, project
  web/             browser UI
  tests/           round-trip suite and corpus
```

`PLAN.md`, `docs/`, `spikes/` and `tests/corpus/` exist now. The studio imports nothing from the video files and
the video files import nothing from it. It reuses ideas from
`tools/timeline_render.py` and `tools/check_layout.py`, not their code paths, so
the preview and the check tools keep working unchanged.

## 9. Open questions (answered in Phase 0 or 1)

- ~~Overlapping clips: plain Manim or a small helper (S4)?~~ Plain Manim, one
  `play()` per overlap group, delays via a 3-line `clip()` helper (S4).
- ~~Should GUI-made scenes default to sequential code or to `at(t)` absolute
  time?~~ `at(t)` anchors in a `TimedScene`; sequential scenes stay editable (S4).
- ~~How should tier-2 overrides read in code?~~ As ordinary statements right
  after the code that made the object, no markers (code_spec.md §5).
- ~~What editable share is a realistic target for Phase 5?~~ ≥ 95% of objects
  drag-editable, ≥ 98% of clips retimable (corpus.md §4).
- ~~How should the studio and the preview server avoid rendering the same
  file at once?~~ The engine never renders video (dry_run, own Tex folder);
  exports go through the preview server when it runs, else a lock file
  (architecture.md §9).
