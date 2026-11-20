# Review after Phase 6

Date: 2026-11-20. Scope: everything changed since the last review
(`5a13157`), that is Phase 6 (`f3e9d77`): the trace cache and spare
engine, the edit's verify run drawing the next frame, export, the render
lock, the keymap and nudges, the error catalogue fixes, the Claude panel,
the app window, docs and install.

Method:
- three independent read-throughs: engine and server (`project.py`,
  `tracecache.py`, `engine/`, `host.py`, the hub in `app.py`); export, the
  lock and the Claude panel (`export.py`, `tools/render_lock.py`,
  `preview_server.py`, `claude_panel.py`, `__main__.py`); and the web UI;
- each finding checked against the code before it was fixed, with a
  regression test where one can be written without a browser;
- a hands-on pass in the browser pane on scratch copies of
  `pythagoras.py` and `gradient_descent.py` (shortcuts, nudges, undo,
  export with chosen scenes, the high-quality warning, cancel, the Claude
  panel next to dialogs, a narrow window);
- two real runs of the Claude panel's CLI to check its new arguments.

Baseline before the fixes: 426 tests passing.

## 1. Security

- **The Claude panel's session id could inject a CLI flag.** The id was
  checked only for letters, digits and `-`, so `--some-flag` passed and
  landed after `--resume`, where the CLI reads it as a flag. Session ids
  must now be UUIDs; anything else is dropped. Test: `test_claude_panel`.
- **The panel's Claude had more than files.** `--allowedTools` only
  pre-approves tools; it doesn't limit them. A real run listed the five
  file tools plus the user's claude.ai connectors (Google Docs and
  others). The panel now runs with `--tools Read,Edit,Write,Glob,Grep`,
  `--disallowedTools Bash`, `--restricted` (no code-running tools, file
  tools kept to the project, settings files ignored) and
  `--strict-mcp-config` (no MCP servers or connectors). Second real run:
  exactly the five tools, `echo hi` refused, and $0.03 instead of $0.69
  (settings and connectors are no longer loaded). Side effect: the user's
  Claude Code settings (their model choice) don't apply in the panel; the
  README says so.
- **A proxied request could pass as local.** "Local" was decided by the
  Host header alone. Through `tailscale serve`, a peer could send
  `Host: localhost` and skip the token, and the panel and "show in
  folder" gates. Requests carrying proxy headers (`X-Forwarded-For`,
  `X-Forwarded-Host`, `Forwarded`, `Tailscale-User-Login`) now always
  count as another machine. I didn't confirm that Tailscale passes the
  Host through; the guard costs nothing either way. Test:
  `test_review_phase5_server::test_a_proxied_request_is_never_local`.

## 2. The render lock (export and preview server)

The pid-file lock had three failure modes, all fixed by making it an OS
file lock (`msvcrt.locking` / `flock` on a byte past the file's text, held
through an open handle; the OS drops it when the process ends):
- on Windows, deleting the lock file fails while another process is
  reading it, and the failure was ignored. The lock then stayed with a live
  pid (the preview server's own), and both sides waited forever;
- two processes could both take a stale lock (check and delete weren't
  atomic);
- a reused pid kept a dead holder's lock alive.

The file still says who holds it, for "waiting for …". Test:
`unit/test_render_lock.py` (a holder in another process, killed: the lock
is free at once).

## 3. Export

- **Cancel left renders running.** `proc.kill()` ends only the top process
  on Windows; the venv launcher's child python (and LaTeX) went on, with
  the lock already released. Cancel now ends the process tree
  (`taskkill /T /F`; a process group elsewhere). Checked in the UI: no
  render process left after Cancel. Stopping the studio now ends running
  exports too.
- **The joined video's narration check could pass falsely.** With no
  `.srt` next to the joined file, `audio_check.py` only asked whether any
  sound was there. `tools/concat.py` now writes the joined `.srt` (each
  scene's cues shifted to its start), so every cue is checked. Checked on
  three `pythagoras` scenes: 12 cues, all with sound.
- After Cancel, the list said "failed" (in red) for the scene being
  rendered and "queued" for the rest; now "cancelled" and "skipped" (found
  in the hands-on pass).
- An export could take another render's file as its own (it looked in
  every resolution folder); it looks in its quality's folder first.
- A newer export of the same file and quality overwrote the joined file an
  older job still offered; the older job no longer offers it.
- The progress line showed Manim's per-animation percentage as if it were
  the scene's. It now says which animation is rendering; the bar counts
  scenes.

## 4. Engine and cache

- **An edit or undo could be refused at random on Windows** (found by the
  corpus run after the fixes). Writing replaces the file in one step, and
  Windows refuses that while any process has the file open for reading.
  The engine reloading after the previous edit is one such process. The
  write gave up at once with "can't write the file (Access is denied); is
  it open and locked in another program?". In the corpus run, this hit
  the undo after a timing edit in `gradient_descent.py` and after a
  number edit in `late_error.py`, which left the edit on disk. A
  `late_error` loop failed 1 run in 3. Phase 6 added more readers of the
  file (the trace cache key, the dependency digest, the spare engine),
  which made the race more likely. An editor or a virus scanner reading
  the file has the same effect. The write now retries for up to about
  2 s. After the fix: 10 of 10 `late_error` runs and the
  `gradient_descent` run are byte-identical. Test:
  `test_code_layer::test_write_waits_for_a_reader_to_let_go`.
- **A broken module could leave the file stuck.**
  - A module saved with a typo, then put back exactly as it was, didn't
    reload: the "has it changed" digest was only updated by a successful
    load.
  - A file whose module was broken from the first open never reloaded
    when the module was fixed: its imports were known only from a
    successful load.
  - Its frames said "nothing is loaded in the engine".

  Now the imports are also read from the file itself (`ast`, anywhere in
  it, so an import inside `construct()` counts too), a "seen" digest is
  kept apart from the cache key, and frames that can't be drawn say why
  (the last good version imports the broken module too). Test:
  `test_phase6::test_changed_local_module…`, extended with both cases.
- **A module saved during a load could be cached as the old version.**
  The digest was read after the load. It's now compared before and after;
  if it changed, nothing is cached and the engine restarts.
- **An old trace could be filed under new bytes.** `_load` read
  `self.data` after its awaits, and a save between the new bytes and the
  new load could slip in. `_load` now uses the bytes it started with.
- **Stop could mark the wrong version "stopped".** It used the newest
  bytes rather than the ones being traced; it now keys on the bytes being
  traced.
- **Another open file importing the changed one wasn't restarted**, and
  `manim.cfg` wasn't watched. Both now restart dependent engines.
- Scenes the last good version never traced (the file changed while it was
  tracing) stayed "pending" forever while the file was broken; they now
  say "not traced".
- The frame the edit's verify run draws had no transform ghost outlines
  (the cursor pool's frames do), so it differed from a real frame
  mid-transform. Both draw them now.
- The trace cache only trimmed itself every 50th write per run, so short
  sessions never trimmed. It now trims on the first write too, removes
  leftover temp files, and refreshes a file's time on a hit (least
  recently used goes first).
- A scene that calls another scene class (`Other.helper(self)`) or reads
  its constants kept a stale trace when that class changed; any class of
  the file a scene names is now part of its key. Tests: `test_tracecache`.

## 5. Web UI

- **Nudges** (the worst UI findings):
  - The 450 ms timer sent the move through an old copy of `sendEdit`. That
    copy skipped the busy check, used an old revision, and could go to a
    file or scene you had already left. Ctrl+Z within the window undid the
    previous edit, and the nudge was then refused as stale.
  - Holding a key made several undo steps, because Windows' repeat delay
    (about 500 ms) is longer than the timer. Presses during the first
    edit's verify were also dropped silently.

  Now:
  - the send goes through the current state;
  - presses add up while an edit verifies;
  - releasing the key sends at once, with an 800 ms fallback;
  - undo drops an unsent nudge;
  - a file or scene change discards it.

  Checked in the browser: 21 presses (one plus 20 repeats after a 550 ms
  pause) gave one edit of `+2.1`, a quick Ctrl+Z dropped only the unsent
  nudge, and one more undo restored the file byte for byte.
- No two edits in flight from one render: a flag set at once guards
  edits, undo/redo and preview confirms.
- Auto-repeat no longer repeats play, duplicate, delete or undo; Alt+arrow
  can no longer take the page Back; Esc closes the export dialog wherever
  the focus is.
- **Claude panel:**
  - it sat above dialogs and could cover their main button; it's now
    below them;
  - it starts below the header, however tall the header is;
  - it asks for the status again after a reconnect, so it no longer
    stays "thinking…" when the last event was missed;
  - it shows only its own tab's answers and never takes over another
    tab's session.
- Header: pills now give up width in order (the tier summary first; `rev`
  and the nudge never). The tracing pill had squeezed `rev` to "r…".
  Found in the hands-on pass.
- The timeline's R / M keys stayed on while picking glyphs or in camera
  mode; the Delete tooltips come from the keymap.
- `--app` with the port taken by another program opened a window onto that
  program; it now checks the page is the studio first.

## 6. Found fine

- No XSS: server and Claude text are rendered as text.
- Export scenes, quality and format are checked against lists, and every
  subprocess gets an argument list (no shell).
- Only files an export made can be served.
- Stop/restart generations, the busy pill, and the seeded frame's checks
  (bytes, revision, scene, range).
- Shortcuts: J/K/L, `[` `]`, Home/End, `,` `.` behave as the keymap says.
- Undo after a nudge is byte-exact. The high-quality warning shows.
  Chosen scenes export in render order.
- The 3D copy opened and traced.

## 7. Left as they are

- K toggles play rather than only pausing, and J/L step a second rather
  than shuttling. This is documented (plan "changed while building",
  README, help sheet).
- The page retries a lost connection every second, without backing off.
- Undo's frame isn't seeded from the frame cache (from the exit report).
- I didn't test the Tailscale Host header behaviour against a real
  tailnet.

## Results

| Check | Before (Phase 6) | Now |
|---|---|---|
| Tests (`pytest studio/tests`) | 426 passed | 432 passed (431 in the full run, plus the write-retry test; unit and Phase 6 engine tests re-run after it: 402 passed) |
| Corpus run (27 files) | all byte-identical | all byte-identical after the write fix. The only bad frame is the deliberate one in `late_error.py`. The only refusal is the known colour edit on `eq` in `order_matters.py` (the code recolours it straight after). Expected errors: `chapter0.py` (ManimGL) and `broken_syntax.py` |
| Real Claude CLI runs | — | 2 ($0.69 before `--restricted`, $0.03 after) |

New tests: `unit/test_render_lock.py`; in `test_claude_panel` (UUID-only
sessions, the tool set, Stop while starting); in
`test_review_phase5_server` (a proxied request is never local); in
`test_tracecache` (another class named in a scene, trimming); in
`engine/test_phase6` (a broken module going back to the same bytes, and
a file whose module was broken from the start); in `test_code_layer`
(the write waits for a reader).

Behaviour changes to know about:
- The Claude panel no longer uses your Claude Code settings (model,
  permissions) or connectors. It has the five file tools and nothing
  else.
- A joined export now has a `.srt` next to it. `tools/concat.py` writes it
  for command-line joins too.
- Old `.render-*.lock` files are simply reused. Nothing needs cleaning
  up.
