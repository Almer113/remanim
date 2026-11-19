# Review after Phase 5

Date: 2026-11-20. Scope: everything changed since the last review
(`9745f78`), that is Phase 5 (`2cae20e`: text and TeX editing, part
colour, graphs, transform pairs, 2D and 3D camera, 3D drags, presets, the
census/drag/clip benches), plus the tailnet `--allow-host` flag and the
`edge_tts_service.py` cache lock.

Method:
- three independent read-throughs: code layer (`studio/server/code`),
  engine and server (`engine/`, `app.py`, `project.py`, `__main__.py`,
  `edge_tts_service.py`, `manim_kit.py`), and web UI (`studio/web/src`);
- each finding checked against the code (most with a small repro) before
  it was fixed, and given a regression test where it can be tested without
  a browser;
- a hands-on pass in the browser pane on scratch copies of
  `plotting_with_manim.py`, `gradient_descent.py` and the corpus
  `camera.py` (curve formula, area fields, 2D drag under a zoomed camera,
  3D drag, camera mode, the text editor).

Baseline before the fixes: 331 tests passing (unit + engine).

## 1. Security

- **Tailnet access was unauthenticated code execution** (the most serious
  finding). With `--allow-host`, the only gate was the Host name plus an
  Origin check. Any device the tailnet ACLs let reach the
  `tailscale serve` name could open, run and edit scene files. A formula
  typed into the curve field could also write files, because `np.savetxt`
  passed the name check and ran during the verify replay. Fixed in three
  ways:
  - **Token:** requests under a non-local name now need a random token,
    printed in the start-up link (`/?token=…`). The server moves it into
    an HttpOnly, Secure, SameSite=Strict cookie and drops it from the URL.
  - **Origin:** a browser `Origin` must be the request's own host. A local
    page can't drive the tailnet name, and the reverse.
  - **Formulas:** curve formulas only call maths. Allowed: `np.` and
    `math.` functions on an allow-list (or numpy ufuncs), and names the
    file binds itself. Refused: `eval`, `open`, `getattr`, `__import__`,
    attributes of other modules, any method call outside np/math, and
    `#` or newlines.
- **Dev server origins:** the Vite dev origins (port 5173) were always
  allowed, so any project's dev server on that port could drive the
  studio. They now need `--dev`.
- **Re-checked:** no new holes in string escaping (`_string_like`
  round-trips quotes, backslashes and line separators), in names written
  as code, or in the file paths the server opens.

Regression tests: `tests/unit/test_review_phase5_server.py` (8), and the
curve tests in `tests/unit/test_review_phase5.py`.

## 2. Engine and server

- **Ghosts and glyph probes shifted object ids.** The transform ghost and
  the part-colour glyph probe build objects while the user's `play()` is
  on the stack. That used up occurrence numbers for that line.
  - The effect: in a loop of `TransformMatchingTex` plays, later objects
    had different ids in cursor frames than in verify runs. After an edit
    the result was "the object isn't on screen", or the wrong object.
  - Fix: both now run with the id counters saved and restored
    (`OriginTracker.counts_kept`).
- **A part-colour edit that needed a yes skipped the glyph check.** The
  confirm path only checked that the scene ran. Every candidate is now
  replayed and glyph-checked first. One that needs no yes wins, and a yes
  is asked only for a checked candidate.
- **The no-op `at()` tidy-up was written without a replay.** It is now
  replayed. It is kept only if every event's timing is unchanged and the
  edit's checks still pass.
- **Camera edits ignored a planner's `confirm`.** They now ask, after the
  replay (for example a camera move inside a loop).
- **`TransformMatchingTex(a, b, False, False, {...})` crashed under the
  studio.** The key_map patch didn't accept the map positionally. It now
  reads it from either place and passes everything on unchanged.
- **Text builds took two locks in opposite orders** in one path, a rare
  deadlock between cursor threads. They now share one lock.
- **LaTeX error messages kept Manim's `\special` markers**, because the
  regex never matched. Fixed.
- **Narration cache hits waited behind another process's synthesis**
  (`edge_tts_service.py`), for minutes when Edge stalls. This affected
  plain renders and the preview server too. A hit is now looked up
  without the lock first; only a miss takes the lock and checks again.
- **An overlapping-edits error from `apply()`** now becomes a refusal
  instead of a failed request.

## 3. Code layer

Regression tests: `tests/unit/test_review_phase5.py` (52).

- **Part colour by `tex_to_color_map` renumbered parts that other code
  indexes**, such as `self.eq[0][0:2]`, a formula inside a group, or an
  alias. The map is now offered only for a formula used whole: a plain
  local name handed to animations and scene methods, or an inline formula.
  Otherwise the index override is used.
- **An `at()` in a loop over a literal list could edit the wrong pass.** A
  pass that made no wait event, or an inner loop, shifted the mapping.
  - The pass is now found by its time value.
  - Anything ambiguous is refused: an `if`, `try` or inner loop between
    the call and the loop, or two equal values.
  - An edit that changes nothing is refused too.
- **A brace or box preset could attach to a different object** when the
  name was rebound between the object and the insertion point. The
  composite, duplicate and preset paths now refuse that.
- **Adding to a dict with a trailing comma, or with one entry per line,
  broke the file** (`t2c=`, `tex_to_color_map=`, `key_map=`). Both
  layouts are handled; anything else falls back.
- **3D camera calls with positional angles got a duplicate keyword** (a
  TypeError). Positional arguments are now mapped by the real CE
  signatures. Two missing keywords in an empty call used to run together
  without a comma; they now go in as one insert.
- **Curve formulas:** a tuple starting with `(` (`(t + 1) * 2, t`) became
  two arguments, and a `#` commented out the rest of the call. Both are
  fixed: the tuple is wrapped, and `#` is refused.
- **Dragging a `Line`, `Polygon` or `Vector` built from graph points**
  edited only its first point. The graph-point edit is now only for
  point-placed objects (`Dot`, `Dot3D`, `point=`); the others get a
  `.shift()`.
- **A negative number as the base of `**`** (`3 ** 2` → `-3 ** 2`, which
  is −9) is now bracketed.
- **Edits that change every pass now ask first:**
  - camera moves in a loop or helper;
  - literals in scene methods other than `construct`;
  - a transform-kind switch in a loop, or on an argument that isn't a
    plain name.

  Switching to or from `Transform` warns when the source is used later.
- **Smaller fixes:**
  - `scene_construct` took the first `def construct`; Python runs the
    last.
  - Inserting at the top of a one-line `def construct(self): ...` is
    refused, as `inserts.slot` already did.
  - `SingleStringMathTex` was indexed as if it had parts.

## 4. Web UI

- **Under a moved or zoomed 2D camera, the canvas used the default
  frame.**
  - After `frame.scale(0.5)`, a drag moved objects twice as far as the
    mouse, and the server verified the wrong distance.
  - Glyph boxes, transform ghosts, guides and library drops were
    misplaced.

  The canvas now maps through the camera's frame (centre and width).
  Checked in the browser: a quarter-width drag of the square in the corpus
  `camera.py` `Zoom` wrote `.shift(1.75 * RIGHT)`; before, it would have
  been 3.5.
- **3D:**
  - the drag preview was drawn as a screen move; it now goes through the
    camera, like the edit;
  - a drag with the floor seen edge-on did nothing, silently; it now says
    why;
  - the rotate handle is hidden for 3D objects, because a turn on screen
    isn't a turn about OUT under a tilted camera;
  - transform ghosts are hidden in 3D, because their boxes are in world
    units.

  Checked in the browser: dragging the cube in `Orbit` (theta −45°) to the
  right wrote `shift(1.2 * RIGHT + 1.2 * UP)`.
- **Shortcuts leaked into overlays.** With the glyph picker, the text
  editor or camera mode open:
  - Delete deleted the object underneath;
  - Space played;
  - Escape also cleared the selection.

  App shortcuts are now off while an overlay is open, and each overlay
  handles its own Escape. A focused literal in the code peek takes Space
  and Delete itself.
- **Camera mode:**
  - Escape never closed it, because the handler sat on an element that
    couldn't take focus;
  - a drag that left the canvas was lost;
  - a pan right after a wheel zoom used the wrong scale.

  Now Escape closes it (checked in the browser), drags follow the mouse
  to the window edge, and a pending zoom is sent before a pan starts.
  Camera mode also turns off when the scene or file changes.
- **The text editor cancelled on a click on its own header or a fixed
  part.** Inner clicks now keep the focus (checked in the browser).
- **Glyph picker:**
  - a click between glyphs threw away the whole pick; it now only closes
    when nothing is picked yet;
  - a stale revision (410) showed "can't match this text's glyphs"; it
    now closes quietly.
- **Transform ghost:** a half-made "match these" pick now expires when its
  part is no longer shown unmatched, and Escape clears it.
- **Found in the hands-on pass:**
  - a remembered file that no longer exists left the app stuck on
    "Tracing the scene…"; it now starts empty;
  - after switching to a scene still being traced, Layers stayed at
    "Nothing selectable" until the playhead moved; the objects now load
    when the trace lands.

## 5. Not fixed (noted)

- 3D drags still use the world's x-y floor only. Moving along z, and
  choosing the plane that faces the camera most, are the open Phase 5
  step 11 work.
- Glyph boxes for non-pinned text in a 3D scene are unprojected. Part
  colour on 3D text that isn't pinned to the screen is rare.
- `_clear_empty_text_svgs` clears every empty SVG in the text cache, not
  only this Text's. That is harmless on Windows, where open files can't
  be deleted.
- **Ghosts:**
  - they are worked out for every play of a cursor run;
  - Manim's own pairing of `key_map` parts that also match by key isn't
    mirrored exactly, so the overlay may colour one pair differently from
    Manim.
- A "not a scene file in this project" toast still shows once when the
  remembered file is gone; the app then starts empty.

## 6. Results after the fixes

Tests: **392 passing** (unit + engine; 331 before the review). That is
52 code-layer and 8 server regression tests, plus the updated `at_clip`
durations. One older engine test changed on purpose:
`test_axes_range_and_transform_kind` now expects a preview for
Transform → TransformFromCopy, then confirms it. With TransformFromCopy,
`a` keeps its own shape, so the `FadeOut(a)` on the next line fades a
different shape.

Benches, against the Phase 5 results:

| Bench | Phase 5 | Now |
|---|---|---|
| Drags moved and verified | 92.7% (179/193) | 92.7% (179/193), 178 undone to the same bytes |
| Retimable clips | 77.0% (560/727) | 77.0% (560/727), 0 failed replays |
| Census, tier 1–2 | 95.1% | 95.1% |
| Corpus run | all files | all files: 0 changed bytes, 0 engine restarts |

The only corpus errors are expected: `reference/source/chapter0.py` is
ManimGL code, and `awkward/broken_syntax.py` is broken on purpose.
The first clip run also counted the review's scratch copies at the
project root, so its raw total was 1006 clips. Without those copies, the
figures above match the Phase 5 run exactly.

The new refusals and confirms didn't cost coverage: no bench number
went down.

Behaviour changes to know about:
- Remote (tailnet) use needs the token link printed at start-up. The
  plain tailnet URL now answers 403.
- The Vite dev server (`npm run dev`) needs `--dev` on the studio server.
- Curve formulas that call methods outside `np`/`math` are refused (for
  example `self.f(x)`). Plain functions defined in the file still work.
