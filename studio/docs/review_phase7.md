# Review after Phase 7

Date: 2026-11-25. Scope: everything changed since the last review
(`4dc96d3`):
- Phase 7 steps A–E (target length, voice, scene add/rename/delete,
  render order, undo frames from the cache, reconnect backoff, the
  Inspector and timeline follow-ups);
- running reManim permanently: `serve.py`, the access token, the Hub
  entry, the installable app;
- the logo;
- the fixes made during the F16 video;
- the speed fix in `b7a3ec6`.

Method:
- three independent read-throughs:
  - security and deployment (`app.py`'s middleware and token page,
    `__main__.py`, `serve.py`, the Hub's log view), probed against the
    live server with a tailnet Host header;
  - server and code layer (`scenes.py`, `timeline.py`, `project.py`,
    `source.py`, `splice.py`), each finding confirmed with a snippet;
  - the web UI (`studio/web/src`, the backoff check);
- each finding checked against the code before it was fixed, with a
  regression test where one can be written without a browser;
- a hands-on pass in the browser pane on the deployed server (port
  8770), on a scratch copy of `odd_squares.py`:
  - the scene menu, the TARGET field and the splitter;
  - Undo, Export and New file.

Baseline before the fixes: 443 unit tests passing.

## 1. Security and deployment

- **The access token was in `server.log`, which the Hub shows without a
  login.** Every start printed the tailnet link with `?token=…`, and any
  tailnet peer could read it through the Hub's "View log". With
  `--token-file` the server now prints only where the token is kept. The
  six copies already in `server.log` were replaced with `<token>`
  (`server.log.1` didn't exist). The token itself is unchanged: rotating
  it is your call (see "Left as they are"). Test: `test_deploy` (the
  kept token is never printed).
- **A non-ASCII token gave an unauthenticated 500 with a traceback.**
  `hmac.compare_digest` raises on non-ASCII `str`. The middleware now
  compares bytes (`token_ok`), and any error counts as a mismatch, so
  the visitor gets the token page or a 403. Test: `test_deploy`.
- **A token file the server couldn't read was silently overwritten.**
  This happened to a short token, a non-ASCII one, or one saved with a
  BOM by Notepad. Now:
  - a BOM is ignored (`utf-8-sig`);
  - an unusable token stops the start with a clear message;
  - only an empty or missing file gets a new token.

  Tests: `test_deploy` (BOM, empty, a parametrised set of bad files).
- **The token page sent the token in the URL (GET).** The form now posts
  it:
  - a right token answers `303 /` and sets the cookie;
  - a wrong one shows the page again with "That isn't the token; try
    again."

  `?token=` links still work (302 and the cookie). Test: `test_deploy`.
- **Two `start`s at once could leave the server without a pid file.**
  When a start loses the race, it now:
  - reports success if the server answers its health check;
  - removes the pid file only if it holds its own pid.
- **`stop` could kill the wrong process after pid reuse.** A recorded
  pid only counts as ours (`hub_server`) when:
  - the process is alive;
  - its command line has `studio.server`, `--token-file` and
    `--port 8770`.

  `status` uses the same check.

## 2. Server and code layer

All of these wrote wrong text into your file, where replay can't catch
it, because a docstring, a comment or a `SCENES` string doesn't change
the trace.

- **The docstring's "render order" matched any mention of the scene
  name.** In a one-scene file, `"""Intro scene for the Euler video."""`
  had "+ scene" turn it into `"""Intro, Outro scene for…"""`, and rename
  rewrote the prose. The names must now follow a label on their line
  (`Render order:`, `Order:`, `Beats:`, `Scenes:`). Test:
  `test_review_phase7`.
- **A one-per-line `SCENES` list moved comments to the wrong name.**
  Deleting the last name took the previous name's comment with it.
  Adding after a name put the new one before that name's comment. When
  every name is alone on its line, the studio now inserts and deletes
  whole lines, so each comment stays with its name. Test:
  `test_review_phase7`.
- **"+ scene" put the new class in front of the current class's trailing
  comments.** Commented-out code after a scene's last statement ended up
  inside the new scene. Delete left the same comments behind as orphans.
  A class now extends over the comment lines indented under it
  (`_class_end`), for both add and delete. Test: `test_review_phase7`.
- **`SCENES` tuple edge cases.** `SCENES = ()` plus a scene gave
  `("C")`, a string, which quietly lost the render order. Deleting the
  only name gave `(,)`. Now it writes `("C",)` and `()` (or `[]`).
  Test: `test_review_phase7`.
- **The "padding to TARGET" lock could land on the narration tail.**
  `lock_to_target` can add two waits:
  - first one that runs until the last narration line ends;
  - then the padding.

  The first was labelled as padding, or as "timed by library code (line
  None)". `ending_waits()` now tells them apart. The narration one reads
  "waiting for the last narration line to end: move or shorten that line
  instead". Test: `test_review_phase7`.
- **A Python keyword was accepted as a scene name** (`class`, `None`),
  which gives a file that doesn't parse. It's refused now: "class is a
  word Python reserves; pick another name". Tests: `test_phase7`.
- **New file accepted the name of a module the scenes import.**
  `manim.py`, `style.py` or `numpy.py` would shadow that module for every
  scene in the folder. They're refused: "manim is the name of a module
  scenes import; pick another name" (checked in the pane). Test:
  `test_review_phase7`.
- **A new `SCENES` list was glued to the code above it.** It now gets
  the two blank lines PEP 8 expects.

## 3. Web UI

- **An edit could run after the UI said it had failed.** A request sent
  while the socket was down was queued and later settled as "Lost the
  connection". It stayed queued, though, and went out on the next
  reconnect. The new backoff (up to 10 s) made this likely. A nudge
  during a server restart could be written to the `.py` seconds after
  the error toast. `request()` now answers at once with "Not connected
  to the studio server; try again when it reconnects" and never queues.
  Only fire-and-forget messages (open file, pick scene) are still queued.
- **The splitter could squeeze the canvas, Layers and Inspector to
  nothing.** The old limit (70 % of the window) ignored the header, the
  tools row and the code panel. A height saved on a big monitor broke
  the layout in a smaller window. The timeline is now capped at the
  window height minus 470 px, in both the drag and the CSS. The CSS cap
  holds even for an old saved height. In the pane, a 2000 px height came
  out at 435 px in a 905 px window.
- **Arrow keys on the scene dropdown opened the scene dialogs.** The
  actions were options in the same `<select>`, and Chromium fires a
  change on every arrow step. The select now holds only scenes. Rename,
  Delete and Render order moved to a "⋯" menu (`SceneMenu.tsx`), which
  supports arrow keys and Escape and gives focus back to its button.
- **Scene add, rename and delete were blocked where the server allows
  them.** They needed a scene that traced, a paused playhead and a
  resting state. Now they need only a ready, idle studio with no preview
  and no file error. Deleting a broken scene works, and opening a scene
  dialog stops playback.
- **Escape didn't close New file or the scene dialogs** once a refused
  request had left focus on the page. The window handler now closes
  them, as it already did for Render order.
- **Home on the focused splitter also jumped the playhead to 0.** It now
  stops the key there, like the arrows.
- **The TARGET field kept invalid text** (`-3`, `abc`) after you left
  it, and Enter on unchanged text sent a no-op edit. Now:
  - bad input is marked red with a hint ("A length in seconds, more than
    0");
  - leaving the field, or Enter on bad or unchanged text, puts back the
    real value;
  - a refused edit does the same.

  Checked in the pane.

## 4. Friction from the F16 run (fixed here)

- **5. The undo toast's arrow read backwards.** It said what the undo
  restored as if it were a new edit. It now reads "undone: TARGET 8 → 9"
  (or "redone: …"), naming the step that was undone. Checked in the
  pane.
- **7. "# set a voice to narrate" stayed after a voice was set.**
  Setting the voice now also swaps the template's comment for "the house
  voice; None for a silent scene". Tests: `test_phase7`,
  `test_review_phase7`.
- **10. The `-qh` export warned "low quality first" after a server
  restart.** The dialog only knew about exports since the start. The
  new `export.drafts` request lists scenes whose `480p15` video is newer
  than the file. In the pane:
  - `odd_squares.py` (drafts from two days ago) shows no warning;
  - `review_odd.py` (no drafts) still does.

  Test: `test_review_phase7`.

## 5. Texts made more accurate

- **Render order:** the dialog now says reManim and Export render in the
  order of `SCENES` (made by the first move if missing). Plain
  `manim -a` ignores it and renders alphabetically.
- **Rename and Delete:** both now say "Other files that import it aren't
  checked." (from the server read-through).
- **README:** a note on the token covers:
  - it's never in the log;
  - the form post;
  - what a hand-written token must look like;
  - that one device can't be logged out alone.

## 6. Found fine

- Only the manifest, the favicon and the icons answer remotely without
  the token. The API, WebSocket, frames and assets return 403. Path
  tricks (`..`, encoded slashes, case, a trailing slash) are refused.
- The cookie is HttpOnly, Secure, SameSite=Strict. The Host allow-list,
  and the Origin and Sec-Fetch-Site checks, run before the token.
- Phase 6's security fixes hold:
  - proxy headers mean "not local";
  - the Claude panel stays off remotely;
  - Reveal in folder stays local-only.
- The speed fix's indexes (`statement_at`, `find_call`,
  `enclosing_call`) match the old linear scans exactly.
- `plan_target`, `plan_set_voice`, `_target_edit`, `_ripple_target`,
  undo frames from the cache (key, linking, cycle safety, FIFO worker
  lock), `_timing_locks`, `speech_warnings`, and `_scene_edit`'s checks.
- The reconnect backoff (1, 2, 4, 8, then 10 s; at once on focus,
  online and visible), PageUp and PageDown, and the server and UI field
  names.
- Undo is disabled while an edit is being verified.

## 7. Left as they are

- **Rotating the token.** It was readable through the Hub's log by
  anyone on the tailnet until today. The log is clean now, but the token
  is the same. Rotating it (delete the file, restart) logs out every
  device. Your decision.
- **Rename and delete don't look in other files** for imports of the
  scene. No file in the repo imports a scene class today. The dialog
  says so.
- **One device can't be logged out on its own** (persistent token, 400-day
  cookie). This is documented in the README. Per-device tokens would be
  a feature.
- **New file's placeholder class name** can differ from the one the
  server makes (`circle.py` → `CircleScene`). The toast shows the real
  name, so this is cosmetic.
- **Friction 1, 2, 6 and 8:**
  - a caption field for `+ line`;
  - showing TTS retries;
  - collapsing long Layers lists;
  - "line end + 0.5 s" in End at.

  These are features for a later phase.
- **The Tailscale Host header** still isn't tested against a real
  tailnet request. The proxy-header guard covers either case.

## Results

| Check | Before | Now |
|---|---|---|
| Unit tests (`pytest studio/tests/unit`) | 443 passed | 470 passed |
| Full suite (`pytest studio/tests`) | — | 516 passed (13 min) |
| Type check (`tsc --noEmit`) and UI build | clean | clean |
| Hands-on in the pane (deployed server) | — | scene menu, TARGET field, splitter cap, undo toast, export drafts, `manim.py` refused: all as above. The scratch file was byte-identical to `odd_squares.py` afterwards |

New tests:
- `unit/test_review_phase7.py` (19: docstring label, per-line lists,
  tuples, trailing comments, keywords, `ending_waits`, `shadows_module`,
  the voice comment, `export.drafts`);
- in `test_deploy` (BOM and empty token files, unusable token files, the
  token never printed, a non-ASCII token, the token page's form post);
- in `test_phase7` (keywords refused; the voice comment).

Behaviour changes to know about:
- The server's start line no longer shows the token link. Open
  `studio/data/access_token` for the token.
- A token file with fewer than 8 characters, spaces or non-ASCII stops
  the server instead of being replaced.
- Edits made while the connection is down are refused at once instead
  of being sent later.
- The scene dropdown holds only scenes. Rename, Delete and Render order
  are in the "⋯" menu next to it.
