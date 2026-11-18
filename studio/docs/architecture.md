# Studio architecture

Phase 1 design document. It turns PLAN.md section 4 and the Phase 0 results
(`docs/phase0/`) into the structure Phase 2 builds. The wire format is in
[protocol.md](protocol.md); what the studio may write into a `.py` file is in
[code_spec.md](code_spec.md).

## 1. The one rule

**The `.py` file is the only state.** The studio never holds an unsaved edit.
Every GUI action that changes the video is a write to the file, followed by a
reload, the same path a hand edit or a Claude edit takes. Everything else
(panel layout, track colours, collapsed groups) is UI state and lives in an
optional sidecar that the video never depends on.

So there is one loop, whoever makes the change:

```
 file changes ──> parse + trace ──> new scene model ──> UI updates
      ^                                                    │
      └──────── GUI edit = verified byte splice <──────────┘
```

## 2. Processes

```
 Browser (UI)
   │  HTTP: frames, id maps, files        WebSocket: events, edits
   ▼
 Studio server  (python -m studio.server, localhost:8770, one process)
   ├─ Project      open files, revisions, undo history, sidecar, watcher
   ├─ Code layer   parse, locate, plan edits, splice, write (pure Python, no Manim)
   ├─ Engine host  starts, feeds and restarts the engine workers
   └─ Export       full renders through plain `manim` (or the preview server)
        │ multiprocessing pipes (pickled requests, raw frame bytes back)
        ▼
 Engine workers (child processes, one set per open scene file)
   ├─ conductor   trace, identity, geometry, verify-by-replay, plain replay
   └─ cursors ×N  paused construct() runs parked along the timeline (S1)
```

Why this split:
- **Isolation.** Scene code is the user's arbitrary Python. A crash, a hang or
  a `SyntaxError` kills a worker, never the server. The UI keeps the last good
  model and shows the error.
- **No GIL contention.** S1 ran cursors as threads; the outliers came from
  threads fighting over the GIL. Workers are processes.
- **Clean reloads.** A changed file means a fresh module. Workers are
  discarded and restarted rather than reloading in place, so no stale class
  or global survives an edit.
- **The code layer never imports Manim.** It works on bytes and `ast`, so it
  stays fast and testable without rendering.

### Worker lifecycle

| Event | What happens |
|---|---|
| Scene opened | Start the conductor. It traces every scene in the file and replies with the model. Then start cursors for the active scene, filling the timeline in the background |
| Frame needed and no cursor is near | The conductor answers by plain replay (S1: 0.3–1.6 s in 2D) while cursors fill (4–25 s) |
| File changed (any source) | Bump the revision. Start a new conductor and cursor set on the new bytes; keep the old set answering until the new trace is ready, then swap and stop the old one |
| `style.py`, `manim_kit.py` or another imported local module changed | Same as a scene change, for every open scene (the watcher knows the import list from the trace) |
| Worker crash or timeout | Report the error with its traceback mapped to the source line. Mark the model "stale" and keep showing the last good frames |
| Idle for 10 min | Stop the cursors; keep the conductor |

Defaults: up to 12 cursors per scene, 1 s apart, capped by a memory budget
(S1: 50–130 MB per pool). One scene's pool at a time; switching scenes stops
the previous pool after a grace period.

Hang protection: every request has a deadline (5 s for a frame, 60 s for a
trace). A worker past it is killed and restarted, and the UI shows "the scene
took too long at line N" using the last line the worker reported.

## 3. Modules

```
studio/
  server/
    __main__.py        start the aiohttp app, open the browser
    app.py             HTTP routes and the WebSocket hub (protocol.md)
    project.py         Document, revisions, undo/redo, watcher, sidecar
    code/
      source.py        bytes, line table, AST index, spans (from code_edit.Source)
      patterns.py      the tier-1 / tier-2 pattern library (code_spec.md)
      planner.py       GUI intent -> ranked candidate edits
      splice.py        apply edits, format numbers and vectors, atomic write
      census.py        tier of every statement (from s5_census.py)
    engine/
      adapter.py       EVERY patch of Manim internals, version check (pinned 0.22.x)
      worker.py        process entry point, request loop
      replay.py        replay-to-t, trace, real-render clock (from frame_engine.py)
      cursors.py       cursor pool (from cursor_engine.py)
      identity.py      origins, resolve, id buffer (from identity.py)
      moves.py         MoveRecorder, MorphRecorder (from code_edit.py)
      geometry.py      boxes, anchors, projected handles for 3D
      framecache.py    LRU of encoded frames
    export.py          full renders, joined videos (wraps tools/ via subprocess)
  web/                 TypeScript + React + Vite (npm install needs the user's OK)
  tests/               see testing.md
```

The spikes stay in `studio/spikes/` as reference. Phase 2 ports their logic
into `server/`, with tests, rather than importing them.

`adapter.py` is the only file allowed to touch Manim internals. Today that is:
`CairoRenderer.play` (real-render clock mirror), `Mobject.__init__` (origins),
the positioning methods (moves), `Transform.begin` (morphs), `Mobject.copy`
(re-stamping), Text's SVG cache flag and an audio-length memo. On import it
checks `manim.__version__` and refuses to start on anything but 0.22.x with a
clear message. A Manim upgrade means re-running the Phase 0 benches through
this one file.

## 4. The scene model

What the engine sends the UI after a trace. All times are seconds on the
scene's own clock; all positions are Manim frame units (14.22 × 8, origin at
the centre, y up).

**Scene**: name, class bases (Scene, TimedScene, ThreeDScene...), duration,
fps, resolution, `TARGET` if set, narration lines, errors.

**Clip**: one `play()` or `wait()`, or one animation inside a `play()`.
- `id`: stable key (section 5)
- `kind`: play | wait | anim | voice | caption
- `start`, `duration` as rendered (from the real-render clock, so the
  one-frame quirks in S4 are already applied)
- `span`: the source range of the call (file, line, col, end line, end col)
- `anchor`: the `at(t)` or `wait()` that positions it, if any
- `edits`: which timing edits are available, with the literal each one
  changes (`run_time`, `start`, `rate_func`), or why none is (tier 3)

**Object**: one selectable mobject.
- `id`, `class`, `name` (variable name if known), `site` span, `chain`
  (helper calls), `occurrence` (loop index), `tier`
- `parent` / `children` (the layer tree)
- `alive`: time ranges it is on screen
- `moves`: available move edits are computed on demand, not up front

Geometry (boxes, anchors, rotation handle position) is sent per frame, not
per model, because it changes with time.

## 5. Identity across edits

An object's key is `(class, site file, site span, occurrence, primary)`, as in
S3. After an edit, spans shift. The planner knows exactly where its own edit
landed, so it maps old keys to new ones by the splice offsets (S2's
`line_shift`, generalised to byte offsets). For external edits, the server
diffs old and new bytes (difflib on lines) and maps unchanged lines; a
selection whose line changed falls back to the same class and occurrence
nearest the old position, and is dropped if nothing matches.

Selection, playhead and scroll position survive any edit that keeps the
selected object's line.

## 6. Main flows

**Open.** Client asks for a file. Server reads bytes (keeps the exact bytes:
encoding, CRLF), parses, runs the census, starts the conductor. The conductor
traces all scenes and sends the model. The canvas asks for the frame at the
playhead.

**Scrub / play.** The client requests frames by `(scene, revision, frame
index)`. The server answers from the frame cache, else from the nearest cursor
at or before the frame, else by plain replay. While scrubbing, JPEG at reduced
size; at rest, PNG at full size plus an ID map and geometry. Requests carry a
sequence number; newer requests cancel older ones still queued. Playback of
the whole scene uses the frame cache; once a pass has filled it, playback is
real-time. (A rendered video from the export path is used when it matches the
revision.)

**Select.** At rest the client has the ID map (one colour per selectable,
S3) for the current frame, so hover and click are resolved in the browser with
no round trip. Click → object id → layers panel, inspector and code peek
follow. Alt-click cycles through ancestors (glyph → word → group).

**Drag.** During the drag the client moves a mask of the object (cut from the
frame by the ID map) on top of the frame: instant, no engine. On release:
1. client sends `edit.move {object, dx, dy, t}`;
2. planner ranks candidates (S2); the conductor applies the first in memory,
   replays to `t`, measures; next candidate if wrong; calibrates once for a
   later `scale()`;
3. a verified edit is written (atomic), recorded in undo, and the model is
   rebuilt from the new revision;
4. if no candidate verifies, nothing is written and the object snaps back,
   with the reason ("x is set by an updater at line 210").
Side effects found by the replay (other objects that moved) are shown before
the write when they are not dependents of the dragged object; the user can
cancel.

**Retime.** Same path: `edit.timing {clip, field, value}` → literal edit →
verify by trace (the clip's new start/duration match within one frame) →
write.

**External edit.** The watcher sees the file change. If the bytes equal the
studio's own last write, ignore. Otherwise: new revision, re-trace, remap the
selection (section 5), and mark the undo history (section 7).

**Errors.** A file that doesn't parse or crashes in `construct()` keeps the
last good model on screen, greyed, with the error and its line in the code
peek. The timeline shows how far the trace got. The studio never writes to a
file it cannot parse.

## 7. Undo

Undo is per file, a stack of `(before_sha, edits, after_sha)`. Undo applies the
inverse splices to the current bytes, but only if the current bytes hash to
`after_sha`; if someone else changed the file since, the server tries the
inverse splices anyway and checks that each span still holds the text the edit
wrote. If yes, undo is applied (the other change was elsewhere); if not,
undo is refused with "the code here has changed since". Redo is symmetric.
This keeps guarantee 5 (undo is exact) without ever guessing.

Git is the long-term history; the studio doesn't commit.

## 8. Writing files

- Atomic: write `<file>.studio-tmp` in the same folder, then `os.replace`.
- Exact bytes: keep the encoding, BOM if any, and line endings (CRLF in this
  repo). Inserted lines use the file's line ending and the indentation of the
  statement they follow.
- Never write while the parse is broken, and never write a result that
  doesn't parse (checked before the replace).
- The preview server watches this folder and re-renders on save. That's
  fine: the studio engine uses `dry_run` and its own `media/Tex_studio`, so
  the two never share LaTeX temp files (S1).

## 9. Export and the preview server

Rendering a real video (Phase 6 export, or "render this scene" in Phase 2)
uses plain `manim` through `tools/timeline_render.py`, so the result is exactly
what a command-line render gives (guarantee 4). The repo rule "never two
renders of the same file at once" applies:
- if the preview server answers on its port, the studio asks it to render
  (`POST /api/render?file=...&quality=...`) and watches `/api/state`;
- otherwise the studio renders itself, holding a lock file
  `media/.render-<stem>.lock` while it runs. The preview server gains the
  same check in Phase 2 (a few lines; it skips a file whose lock is held).

This answers PLAN.md's open question on render collisions.

## 10. Security and scope

- The server binds to 127.0.0.1 only. It runs the user's own scene code,
  like `manim` does; it does not sandbox it.
- Only files under the project folder can be opened or written.
- No network access from the studio itself. (Narration TTS goes through
  `edge_tts_service.py` as today, when a scene uses it.)

## 11. Performance budget (from S1)

| Action | Target | Path |
|---|---|---|
| Scrub, 2D | ≤ 120 ms per frame | cursor, JPEG at half size |
| Random jump, 2D | ≤ 300 ms | nearest cursor |
| Random jump, 3D | ≤ 1.5 s, then cached | cursor; 240p proxy while dragging |
| Drag feedback | next animation frame | client-side mask, no engine |
| Drag commit | ≤ 1 s for 2D | 1–3 verify replays |
| Re-trace after an edit | ≤ 2 s typical | conductor; cursors refill in background |
