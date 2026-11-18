# Review after Phase 3

Date: 2026-11-18. Scope: everything changed since the last review
(`1978a30`), committed as `138bc33`: `studio/server/` (engine recorder,
move/scale/rotate planner, library inserts, edit flow), `studio/web/src/`
(canvas gestures, Library, keys, preview dialog), and the docs.

Method:
- three independent read-throughs (engine and process layer; code layer and
  edit flow, with pure-Python probes for every byte-level claim; web UI);
- a hands-on pass in the browser pane on a scratch scene (drag, scale,
  rotate, delete, duplicate, group, a library insert, undo all the way);
- each finding checked against the code before fixing, and re-tested in the
  pane after.

Baseline before the fixes: 148 tests passing.

## 1. Security

| Problem | Fix |
|---|---|
| **Code injection through an object's `ancestors[].index`.** The object a drag or property edit names comes from the browser. The index was written into the file as `row[<index>]` unchecked, so `"0]; __import__('os').system(...); row[0"` became a statement, and the verify replay ran it before anything was written. The Origin check limited this to the studio's own page | `override_target` accepts only a plain non-negative `int`; the `#n` occurrence from an object id must be digits. Everything else the client sends was already checked |
| A foreign page could make the server render frames with `<img src="http://127.0.0.1:8770/frame?...">` (no `Origin` header) | `local_only` also refuses `Sec-Fetch-Site: cross-site` |

## 2. Code layer (planner and inserts)

Each item has a regression test in `tests/unit/test_review_phase3.py`. 19 of
its 24 tests fail on the old code.

- **Delete could remove unrelated code** on a line with non-ASCII text.
  `remove_statement` and `_remove_argument` compared ast byte columns with
  `str` indices:
  - `t = Text("Привет мир"); f()` lost `f()`.
  - Fix: new `Source.before()` / `after()` slice bytes.
- **Dragging a `move_to(RIGHT + UP)` to the origin was refused** ("overlapping
  edits"), and the error also stopped the later candidates. It now writes
  `ORIGIN`, and a bad candidate is skipped, not fatal.
- **Scale drag and drag back left `scale(1.9998)`** (k arrives rounded).
  - A product within 0.05% of a two-decimal number is that number.
  - A chained `.scale()` back near 1 is removed (`SNAP`).
- **A drop during a play in a TimedScene wrote a dead `self.at(2)` after a
  play ending at 4**, and verify then looked at the wrong frame and refused.
  The new lines now start when the play ends, with no `at()`. The same
  applies to duplicate and presets.
- **`self.wait(0)` (refused by Manim)** when a drop used up a wait that
  couldn't be removed (trailing comment, shared line, only statement). The
  wait becomes `pass` instead.
- **Deleting a clip in `with self.voiceover(...): self.play(...)` (one
  line) deleted the `with` and its narration.** A statement on its block's
  header line is refused. The same goes for an insert into a one-line
  `def construct(self): pass`, which used to remove the `def` line.
- **Group bound the wrong object when a name is reused.** `a = Circle()` …
  `a = Square()`: grouping the Square inserted `VGroup(a, b)` after the
  Circle.
  - The binding is now the one that made the selected object.
  - A name reassigned before the group line is refused.
- **Delete treated the file's own names as library names** (`rotation`,
  `scene`: `dir(manim)` and `manim_kit` export them), so it removed a
  `Transform(c, rotation)` that also used another object. Names the file
  assigns are its own.
- **A file without a final newline:** insert, duplicate, preset and group
  glued code onto the last line. They now start a new line first.
- Statements with a trailing comment (`self.add(c)  # show`) can be removed
  (the comment goes with them).
- `new file circle.py` made `class Circle(TimedScene)`, which shadows the
  library's Circle. Names that are library classes get `Scene` added
  (`CircleScene`).
- A new x term goes before the y term (`UP` → `0.5 * RIGHT + UP`), so a drag
  to zero and back restores the bytes.

## 3. Engine and processes

- **An `.animate` move inside a multi-line `self.play(` was recorded as moved
  by an animation.**
  - `_MethodAnimation.finish()` applies the methods again. The duplicate
    was matched by line, and in the house style (one argument per line)
    the lines differ.
  - So a drag there got an override line, or a refusal, instead of a
    change to the `.animate` numbers.
  - Records made inside `_MethodAnimation.finish` are now skipped outright.
  - "Moved by an animation" is decided by the frame's `self` being an
    `Animation`, not by `"animation"` in the file path (a project folder
    named `animations` broke that; custom animations were missed).
  - Engine test: `test_animate_in_a_multi_line_play_edits_the_animate_vector`
    fails on the old recorder.
- **A slow first `import manim` broke the whole server run.**
  - Found in the pane: a cold start took over 60 s, `hello` timed out, and
    the hub cached an empty list of library names.
  - Every file then had wrong tiers (37.5% instead of 100% tier 1), and
    delete's safety check had no library names.
  - The empty answer is no longer cached. `hello` is asked again after the
    load, and its deadline is 180 s.
- **Old revisions stayed alive.** Two `lru_cache`s keyed by class and the
  `co_positions` cache keyed by code object pinned every module a scene file
  defined classes in. They are cleared when an engine closes.
- `Transform(counter, MathTex(str(i)))` in a loop stored one morph target per
  pass, sent all of them in every object reply, and could make a drag
  produce overlapping edits. Targets are kept once per code site, last 4.
- The verify reply computed group boxes it never had (removed); the runtime
  docstring now names `moves.py` as a place that patches Manim.

## 4. Web UI

- **The frame was drawn stretched** whenever the stage was narrower than
  16:9: 789×455 for an 854×480 frame, so circles showed as ellipses.
  - The canvas is now the largest rectangle with the frame's aspect in its
    box (container query units).
  - Checked: 789×443.5, aspect 1.7792.
- **Delete / trim / Inspector acted on a clip by index after the indexes
  moved** (an insert above it, undo). Clip selections are found again by
  line and text after every model, or dropped.
- **The preview dialog:**
  - A second Enter in the field behind it sent a second edit, and the first
    token was never cancelled.
  - Now: no edit can be sent while it is open, and the Inspector is
    disabled.
  - The dialog takes the focus itself, not a button, so a reflexive Enter
    doesn't apply "Every one" unread. Tab reaches the buttons; Escape
    cancels.
- **A drag ignored changes during it.**
  - Start a drag, press Space or an arrow, or undo, then release: the edit
    went out for the new frame with the old object.
  - A drag now remembers its frame and is dropped if the frame changed or
    editing stopped.
- **Stuck drags:** after Alt-Tab with the button released outside, the ghost
  followed the mouse.
  - A move without the button pressed, a window blur, or Escape now cancels.
  - Escape during a drag keeps the selection.
- **A small selected object (a Dot) could only be scaled**: its corner
  handles covered it. A press on a small object's own box moves it.
- **A hollow shape could be grabbed only by its outline**, even when
  selected. A press inside the selection's box drags the selection, unless
  another object is under the pointer.
- The ghost used modifier keys from the last mouse move while the edit used
  those at release. Now Shift and Alt are tracked during the drag, and the
  edit is what was drawn.
- The ghost of a gesture vanished before the edited frame arrived, so the
  object jumped back and forth. It now stays until the new frame shows, or
  goes with a refusal.
- Clicks could resolve against a new ID map while the old image was still
  shown. Picking waits for the frame on screen.
- Ctrl+D / Ctrl+G / Delete skipped the guards the buttons have (object off
  screen, locked, virtual), and Delete cleared the selection even when
  refused. Keys and buttons now share the rules, and the selection is
  cleared only when the delete is done.
- Backspace deletes only when nothing has focus (not after clicking a
  button).
- A library drop while editing is off says why. Hover is cleared when a drag
  leaves the canvas. Alt-click on a top-level group stays on it.
- Side effects (`onSelect`, the cut-out) no longer run inside a React state
  updater.

## 5. Not changed (open)

- **A literal `2.0` comes back as `2`** after a drag away and back.
  `2 → 2.5 → 2` and `2.0 → 2.5 → 2.0` pass through the same text. Whole
  numbers are far more common, so they win.
- **A scale drag by hand can't land exactly on the reciprocal.** The UI
  steps k (0.05, or 0.01 with Alt), so ×1.5 then back gives `scale(0.975)`.
  Undo, or the Inspector's scale field, restores it exactly.
- **Moves made through methods the recorder doesn't wrap** (`become`,
  `Restore`, `put_start_and_end_on`, `apply_matrix`) leave an older
  placement on record. The planner then edits a call with no effect at that
  frame. Verify refuses it, so no wrong code is written; the user gets a
  refusal.
- Mobjects defined at class or module level are shared by all cursor
  threads, so their move records can mix times. Rendering such objects was
  already unsafe across cursors.
- The Inspector still lists a `VGroup`'s `*vmobjects` as an editable
  argument (cosmetic, from the exit report).

## 6. Results after the fixes

| | Before (`138bc33`) | After |
|---|---|---|
| Pytest (`studio/tests`) | 148 passed | **173 passed** (3 min 38 s): 24 code-layer regression tests, 1 engine test, 2 updated term-order expectations |
| `npm run build` (strict `tsc`) | passes | passes |
| Corpus drag bench (`drag_run.py`) | 177 / 193 verified, 176 back byte-identical | **177 / 193, 176**: the same objects, no new misses |
| Census of `tmp_review.py` after a cold start | 37.5% tier 1 (empty library names) | 100% tier 1 |

The repo-video drag sample (`order_matters.py`, `pythagoras.py`) was not run
again; it takes about 40 minutes. The `.animate` fix applies to their
multi-line `self.play(` calls, so a rerun can only gain.

Browser pane, by hand:
- On the old code: drag, scale, rotate, delete (one statement, one
  argument), duplicate (a `wait(2)` split into `wait(1)` + play + `wait(0.4)`),
  group, a Library insert, and undo all the way: the file was
  byte-identical.
- After the fixes:
  - the frame keeps its aspect;
  - a drag from inside a selected hollow Square moves it;
  - Escape during a drag sends nothing and keeps the selection;
  - a drag whose button was released outside the window sends nothing;
  - the preview dialog takes the focus, a second Enter neither answers it
    nor sends a second edit, and Escape cancels;
  - a cold start with a 60+ s import comes up with the right tiers.
