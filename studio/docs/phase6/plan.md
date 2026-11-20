# Phase 6 plan: polish and release readiness

PLAN.md §5, Phase 6: export dialog (quality, format, joined video).
Keyboard shortcuts. Performance passes. Error and recovery UX. Docs.
Optional: desktop wrapper, a Claude panel, a real name and licence for
open-sourcing.

**Exit:**
- a whole video can be made start to finish in the studio, without a
  terminal: open, edit, export the joined, narrated video, and pass
  `audio_check.py`;
- the speed targets in step 1 are met;
- every failure in the error catalogue (step 7) shows a clear message and
  recovers without a restart;
- a fresh clone starts from the README alone.

Rules as before: code_spec.md §1 (byte splices, verify by replay, round
trips close). Nothing may break `preview_server.py` or the check tools.
Each milestone ends with tests green, a hands-on pass in the browser pane
and a note in the exit report, and is a natural point to commit.

## What exists today

- **Export:** none. The studio never renders video (dry run, own Tex
  folder). architecture.md §9 says how it should: through the preview
  server's `POST /api/render` when that is running, otherwise the studio
  renders itself and holds `media/.render-<stem>.lock`. The lock half was
  never built, and `preview_server.py` doesn't check for one.
  `tools/concat.py` joins scenes and `tools/audio_check.py` checks the
  narration, both from the command line only.
- **Shortcuts:** in one `keydown` handler in `App.tsx`:
  - Space: play;
  - ← →: step the playhead;
  - Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z: undo and redo;
  - Ctrl+D: duplicate;
  - Ctrl+G: group;
  - Delete: delete;
  - Escape: clear.

  Overlays have their own keys (made consistent in the Phase 5 review).
  Shortcuts appear only as button tooltips. There is no list of them and
  no way to nudge a selected object from the keyboard.
- **Speed** (corpus run, 2026-11-20): opening a file traces every scene
  first.
  - `eola_preview.py` takes 42 s, `gradient_descent.py` 31 s,
    `pythagoras.py` 22 s and `order_matters.py` 20 s.
  - Every reopen costs the same: nothing is cached across server restarts
    or across saves that don't change the scene.
  - Frames at time: median 0.1–0.3 s in 2D and 0.8–1.5 s in 3D (S1).
  - The time from an edit to its new frame (plan, replay, verify, retrace)
    has never been measured as a share.
- **Errors:**
  - a file that doesn't run shows "The file doesn't run — see the error";
  - a worker crash or timeout restarts the worker (`host.py`) and says so;
  - a stale revision gives a 410;
  - a refusal gives a toast.

  There is no catalogue of what can fail, and some cases have never been
  tried in the UI. Examples: LaTeX missing, a syntax error introduced by an
  outside edit while a preview is open, the server going away and coming
  back, the disk full or the file read-only, the file deleted while open.
- **Docs:** design documents in `studio/docs/` and one line in the top
  README. There is no user guide, no install guide and no troubleshooting
  page. There is no requirements file or `pyproject.toml`; the venv is
  set up by hand.
- **Carried from Phase 5:** moving along z in 3D, the plane facing the
  camera, and an out-of-camera view for 2D cameras. These are features,
  not polish (question 1).

## Steps

### 6a. Measure and speed up

| # | Piece | Where | Checked by |
|---|---|---|---|
| 1 | **Speed baseline and targets.** A bench (`tests/speed_run.py`) over the repo videos and the gallery. It measures: cold open (server just started), warm open (file unchanged), first frame, scrub (20 random times), edit → new frame (a retime, a drag and a colour change per file), and UI frame time with the biggest timeline (`eola_preview.py`, 262 clips). Proposed targets: warm open ≤ 3 s; cold open ≤ the current time; edit → new frame, median ≤ 2 s in 2D and ≤ 5 s in 3D; scrub median ≤ 0.3 s in 2D; no UI frame over 50 ms while scrubbing. | `tests/speed_run.py` (new), `docs/phase6/baseline.md` | the report |
| 2 | **Trace cache.** Keep each scene's trace, keyed by a hash of the file, `style.py`, `manim_kit.py` and the other local imports, plus the Manim version. Store it under `media/studio_cache/` (outside the project's source, safe to delete). A reopen with nothing changed loads it and skips the trace. An edit retraces only the scene it touched; other scenes in the file keep their trace if their code is untouched (the scene's own source span + module-level code hash). | `server/project.py`, `engine/worker.py` | unit tests (hash rules, stale cache refused); speed bench |
| 3 | **Whatever the baseline shows next**, in order of cost. Likely candidates: replay from the nearest snapshot for the verify run instead of from the start, tracing scenes of one file in parallel workers (memory permitting), virtualising long timelines in the UI, smaller frames while scrubbing. Each change is kept only if the bench improves and every other test still passes. | as found | speed bench, full tests |

### 6b. Export

| # | Piece | Where | Checked by |
|---|---|---|---|
| 4 | **Render lock, both sides.** The studio's own renders hold `media/.render-<stem>.lock` (pid + start time; a stale lock from a dead pid is cleared). `preview_server.py` gains the matching check: it skips a file whose lock is held and says so on its page. A few lines in the preview server. Its own renders are unchanged. | `server/export.py` (new), `preview_server.py` | unit tests; a render from each side while the other is busy |
| 5 | **Export dialog.** Choose: scenes (one, a range, or all in `SCENES` order), quality (`-ql/-qm/-qh/-qk`), format (mp4, webm, gif, png sequence, mov with transparency). Optionally join into one video (`tools/concat.py`, audio rebuilt as one track) and check the narration (`tools/audio_check.py` on the scenes and the joined file). Each render is plain `manim` through `tools/timeline_render.py`, through the preview server when it answers, otherwise directly under the lock. A progress line per scene, comes from Manim's own progress output. Cancel kills the render; partial files are left as Manim leaves them. A failed scene stops the join (CLAUDE.md: no concat over stale clips). When it finishes: the output path, a play button in the studio, and "show in folder". Rule: high quality only after a low-quality export of the same scenes has passed (CLAUDE.md); the dialog warns and asks, it doesn't block. | `server/export.py`, `server/app.py` (routes), `web/src` (new `ExportDialog.tsx`) | engine test: export two corpus scenes at `-ql`, join, `audio_check` passes; browser pane: a full export of a `order_matters.py` copy |

### 6c. Keyboard and the small things

| # | Piece | Where | Checked by |
|---|---|---|---|
| 6 | **Shortcuts in one table.** A single keymap module that the handler, the tooltips and a "?" help sheet all read from, so they can't drift. Added: arrow keys nudge a selected object (one safe-area grid step; Shift for ten; Alt for fine), and the playhead moves with ← → only when nothing is selected or with `,` `.`. Also: Home/End, J/K/L (back, stop, forward), `[` `]` to jump to the previous or next clip, Ctrl+E to export, Ctrl+F to focus the layer filter, `?` for the help sheet. A nudge is one edit, verified like a drag. Repeated nudges on the same object merge into one undo step while the key is held. Shortcuts stay off while an overlay or a text field has focus, as now. | `web/src/keymap.ts` (new), `App.tsx`, `Canvas.tsx` | unit test: keymap has no duplicate key; browser pane |

### 6d. Errors and recovery

| # | Piece | Where | Checked by |
|---|---|---|---|
| 7 | **Error catalogue.** Every way the studio can fail, each with the message the user sees, what still works and how it recovers. Grouped: the file (syntax error, crash at line N, crash late in a scene, infinite loop, missing import, file deleted, renamed, read-only), the environment (LaTeX missing, LaTeX error, Edge TTS offline or stalled, disk full, `media/` not writable), the engine (worker crash, timeout, out of memory), the connection (server stopped, restarted, second tab open on the same file), and edits (stale revision, outside edit during a preview, verify failure). Each gets a fixture or a test where it can be made to happen, and a hands-on try in the browser pane. | `docs/phase6/errors.md` (new), `tests/fixtures`, `tests/engine` | the catalogue's own table, one row per case, marked tried |
| 8 | **Fixes from the catalogue.** Known gaps to close: a syntax or runtime error shows its line in the code peek, with the error in place; scenes and clips before a late crash stay playable (the trace up to the crash is kept); the UI reconnects after a server restart and reloads the model without losing the selection or the playhead; a second tab on the same file is told it is read-only, or both stay in step through the rev number; a read-only or vanished file refuses edits with that reason, not a server error; environment problems (LaTeX, TTS) say what to install or check, once, not on every frame. | `server/`, `web/src` | the catalogue rows go green |

### 6e. Docs and release readiness

| # | Piece | Where | Checked by |
|---|---|---|---|
| 9 | **User guide** (`studio/README.md`): what the studio is, starting it (local and tailnet with the token link), a tour of the five areas with screenshots, what can be edited and why some things are locked (the tiers, in plain words), shortcuts (generated from the keymap), export, troubleshooting (from the error catalogue), and how the studio and Claude Code share a file. | `studio/README.md`, `studio/docs/img/` | read-through; every command in it is run once |
| 10 | **Install from a fresh clone.** A `requirements.txt` with the pinned versions in use today (no installs: it records `.venv` as it is). A `studio/web/dist` check at start-up: if the built UI is missing or older than `web/src`, the server says to run `npm run build`, instead of serving a blank page. A one-command test entry (`python -m studio.tests`) for the unit, engine and corpus runs. Then a dry run: clone to a scratch folder, follow the README, open a file. | `requirements.txt`, `server/__main__.py`, `studio/tests/__main__.py` | the dry run, done once on this machine |
| 11 | **Exit check:** the speed bench against step 1's targets, every catalogue row, the full test suite and corpus run, and a hands-on run: make a short narrated video from a blank file, export it joined at `-ql`, `audio_check.py` passes, then `-qh`. Exit report. | `docs/phase6/exit_report.md` | |

Rough sizes: 6a M, 6b M, 6c S, 6d M, 6e S–M. Together that is more
than the M in PLAN.md, mostly because of the error catalogue and the
speed work. 6a can be cut to steps 1–2 if the baseline is good.

## Optional items (your call, question 2)

- **Desktop wrapper.** Tauri needs the Rust toolchain (an install). The
  lighter path is a shortcut that starts the server and opens the page in
  an app window (Edge or Chrome `--app=`), which installs nothing. I'd do
  the shortcut and leave Tauri until there is a reason for it.
- **A Claude panel.** A side panel where you ask for a change ("make the
  circle blue and slower"), and Claude edits the `.py`, which the studio
  already picks up live. Two ways to do it:
  - Run Claude Code headless (`claude -p`) in the project. This needs no
    key in the studio and uses your existing login and CLAUDE.md rules.
  - Call the API directly. This needs an API key stored somewhere, and
    the studio would have to rebuild the project rules itself.

  I'd do the first, as a small panel: it sends the prompt and the current
  selection, shows the reply, and the diff lands as a normal outside edit
  with undo. Size S–M. Note that it gives the panel's text the power to
  edit files, so it is off on tailnet hosts unless you turn it on.
- **Name and licence.** These are decisions, not work. The licence must be
  chosen with one rule in mind: the studio imports nothing from
  `eola_common.py` (CC BY-NC-SA) and must keep it that way, so any licence
  is open to it. MIT or Apache-2.0 are the usual choices for a tool like
  this. I'll prepare a short list of free names (checked against PyPI, npm
  and GitHub) if you want one.

## Decisions taken here (unless you say otherwise)

- **Export uses the real render path only:** plain `manim` through
  `timeline_render.py`, never the studio's engine. That is the "no hidden
  state" guarantee: the export is exactly what a command line gives.
- **The trace cache lives under `media/`**, which is already ignored and
  already "safe to lose". A wrong cache costs at worst a retrace: any
  mismatch in the key throws it away.
- **Undo history stays in memory.** It isn't saved across a server
  restart. Saving it would be hidden state that can disagree with a file
  edited while the studio was down. After a restart, git is the history.
- **No new packages**, Python or npm. The help sheet, dialog and keymap are
  plain React. Screenshots for the guide come from the browser pane.
- **Speed work only behind the bench.** Nothing is "optimised" without a
  before and after number, and a change that makes a test flaky is
  dropped.

## Decided (2026-11-20)

All three as recommended: the Phase 5 carry-overs wait for a later
phase; the optional items are the app-window shortcut and the Claude
panel (through Claude Code, off on tailnet hosts unless turned on), done
after 6e; name and licence wait; milestones run 6a → 6e.

## Changed while building

- **Export never goes through the preview server.** Its `POST
  /api/render` renders every scene of a file at one quality, as mp4, and
  can't choose scenes, a format or transparency. So the studio always
  renders itself, through `tools/timeline_render.py`, under the shared
  lock (`tools/render_lock.py`). The preview server waits for that lock
  too (its page says "waiting for studio export…"), so the two still
  never render one file at once.
- **The joined video is checked only when a scene has narration.** Joined
  silent scenes have a silent track, which `audio_check.py` rightly fails;
  each silent scene passes on its own.
- **The Claude panel** runs `claude -p` with read, edit and search tools
  only (no shell), permission mode `acceptEdits`, in the project root.
  A follow-up resumes the same Claude Code session. Each answer shows its
  cost; a one-word answer measured $0.39, because Claude Code reads the
  project's instructions every time.
- **Ctrl+F was dropped:** the layers panel has no filter to focus.
  **"Show in folder"** was added to the export dialog (local pages only).
- **The app window** is `--app` on the server (and `studio/Manim
  Studio.cmd` to double-click): Edge or Chrome with `--app=`, the user's
  normal browser profile, nothing installed.

## The questions as asked

1. **The Phase 5 carry-overs** (z moves in 3D, the plane facing the
   camera, an out-of-camera view for 2D cameras): put them in Phase 6 as
   a milestone 6f, or keep them for a later phase? I'd keep them for
   later: Phase 6 is about finishing what exists, and both are only needed
   by 3D or camera-heavy scenes.
2. **Optional items:** which, if any? I'd suggest the app-window shortcut
   and the Claude panel (via Claude Code). Name and licence can wait until
   you want to publish.
3. **Order:** planned 6a → 6e. If you want to export videos soonest, 6b
   can go first. It doesn't depend on 6a.
