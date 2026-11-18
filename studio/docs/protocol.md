# Engine ↔ UI protocol

Between the browser and the studio server. (Server ↔ engine workers is an
internal pipe protocol with the same request shapes; it isn't specified
separately.) Architecture: [architecture.md](architecture.md).

- **HTTP** for anything binary or cacheable: frames, ID maps, files.
- **One WebSocket** (`/ws`) for everything else: JSON messages, both ways.
- All coordinates are Manim frame units unless a field says `px`.
- Every message about a scene carries `rev`, the file revision it refers to.
  The server ignores edits sent against an old revision and replies
  `error {code: "stale"}`; the client then has the new model already.

## As built in Phase 2 (differences from the design below)

The design below is the target; Phase 2 built a subset, and in places a
simpler shape. Where they differ, this list is what the code does.

- **Frames go over HTTP only.** No `seek` / `frame.ready` messages: the
  client asks `GET /frame?...&f=` directly (browser cache + server LRU), and
  `GET /objects?file&scene&rev&f` → `{objects, rev, f}` when the playhead
  rests. The server drops nothing; a newer request simply finishes later.
  Playback uses `size=half&fmt=jpeg`, prefetched while the worker is idle.
- **`/api/status?file`** (polled, no `status` message):
  `{cursors, of, cached, frames, restarts}`. `cursors` counts timeline spots
  with a parked cursor, not live cursor threads (the pool refills a spot
  after its cursor moves on, so threads can outnumber spots).
- **Object ids have no end position:** `"Text@43:15#0"` (class, line:col of
  the creating call, occurrence; `~` prefix when made inside library code).
  An edit later on the same line keeps the id. No `remap` yet: the client
  re-picks the selection by id after a reload.
- **Clips are numbered** (`clip: <index>` in `edit.timing`), not ids.
  `field` is `duration` or `rate_func`; an `anim` index targets one
  animation inside a `play()`. A clip's `duration` is the code's number
  (`wait(0.5)` → 0.5); `played` is that rounded to whole frames.
- **`edit.prop`** sends the whole object (as `/objects` returned it) plus
  `f`, and `value` is one of `{"number"}`, `{"name"}`, `{"string"}`,
  `{"default": true}` (remove the keyword).
- **Requests with `seq`** get the reply with the same `seq`; that is how the
  client pairs `edit.*` replies. `model` and `file.changed` are pushed.
- **Local only** (review after Phase 2): every request needs a local `Host`
  (`127.0.0.1`, `localhost`, `[::1]`), and a browser `Origin` must be this
  server under either local name, or the Vite dev server on 5173. Values
  written as code (`rate_func`, `{"name"}`) must be Python names; property
  names must be identifiers.
- **`session`** in every `model` changes with each server run; the client
  adds it to frame, ID-map and objects URLs as `s=` so the browser never
  shows a frame cached from an earlier run (revisions restart at 1).
- **`edit.done`** comes once the active scene is traced again; the other
  scenes follow in later `model` pushes. A preview (`edit.preview`) is
  refused on confirm if the file changed after it was planned. After every
  reconnect the client sends `open` (and `scene`) again.
- `/api/status` also reports `threads` (worker threads, for leak checks).
- **Cursors are threads inside each file's worker process** (one process per
  open file), not separate processes. Not built yet: `/audio`, `/source`
  (the model carries `source`) and `render`.

## Added in Phase 3 (direct manipulation)

Every edit below sends `file`, `scene`, `rev` and a `seq`, and gets the same
replies as `edit.prop`: `edit.done`, `edit.refused {reason}` or
`edit.preview {token, summary, why, diff}` (confirm with `edit.confirm`).
Objects are sent whole, as `/objects` returned them; `f` is the frame the
user looked at.

```jsonc
{"type": "edit.move",   "object": {...}, "f": 30, "dx": 1.5, "dy": -0.5}   // scene units
{"type": "edit.scale",  "object": {...}, "f": 30, "k": 1.5, "about": null}  // about: optional edge name
{"type": "edit.rotate", "object": {...}, "f": 30, "deg": 30}                // anticlockwise
{"type": "edit.insert", "class": "Square", "x": -2, "y": 0, "f": 15,
                        "entrance": "Create", "region": "title"}            // entrance, region optional
{"type": "edit.preset", "object": {...}, "preset": "Indicate", "f": 45}
{"type": "edit.duplicate", "object": {...}, "f": 60}
{"type": "edit.group",  "objects": [{...}, {...}], "f": 60}
{"type": "edit.delete", "object": {...}, "f": 60}
{"type": "edit.delete_clip", "clip": 3, "anim": null}                       // anim: one animation of a play()
{"type": "file.new", "name": "my_scene.py", "scene": "MyScene"}            // scene optional; no open file needed
```

- `edit.move` / `scale` / `rotate` are refused while the object (or a group
  it is in) is animating at `f`. Every candidate edit is replayed and
  measured (centre within 0.011, reference point within 0.022, size for
  scale); the first that lands is written. `edit.preview` for these also
  carries `also_moves` (names of other objects the edit moves).
- `edit.insert` classes: Circle, Square, Rectangle, Triangle,
  RegularPolygon, Star, Dot, Line, Arrow, Text, MathTex, Blob (adds
  `from manim_kit import *`). Presets: Indicate, Circumscribe, Wiggle,
  Flash, ApplyWave, FocusOn, FadeOut, Uncreate, ShrinkToCenter. A drop during
  a `play()` starts after it; in a sequential scene a literal `wait()` is
  split so later clips keep their times.
- `edit.delete` removes the creating statement and the statements that only
  use the object; it is refused (naming the line) when other code reads it.
- `file.new` → `{"type": "file.created", "file", "scene"}`, or `error`. It
  never overwrites, and only writes where the file list would show the file.
- `/objects` entries gain `center`, `size`, `p0` (scene units),
  `placement` (what the planner needs), and for groups the user made
  (`VGroup(a, b)`) a `virtual: true` entry after the drawn ones; drawn
  objects inside it carry `parent` (an index into the same list). The
  model gains `frame_width` / `frame_height` (scene units).
- Files under `studio/tests/tmp/` (test copies) open by name but are not
  in `/api/files`.

## HTTP

| Method & path | Returns |
|---|---|
| `GET /` | The web app |
| `GET /api/files` | Scene files in the project: `[{path, scenes: [name], mtime}]` |
| `GET /frame?file&scene&rev&f&size=full\|half&fmt=png\|jpeg` | One frame (`f` = frame index). `Cache-Control: immutable`, since `(rev, f)` never changes |
| `GET /idmap?file&scene&rev&f` | PNG, same size as the full frame. Pixel colour = selectable index + 1 (0 = background). The index list comes with `frame.ready` |
| `GET /audio?file&scene&rev` | The scene's narration mixed to one WAV, for the timeline waveform and playback |
| `GET /source?file` | Raw bytes of the file, for the code peek |

## WebSocket: client → server

```jsonc
{"type": "open", "file": "order_matters.py"}
{"type": "scene", "file": "...", "scene": "Question"}            // make active, start cursors
{"type": "seek", "file": "...", "scene": "...", "rev": 7, "f": 112, "seq": 41, "rest": true}
     // rest=false while scrubbing (jpeg, no idmap); true when the playhead stops
{"type": "edit.move",   "rev": 7, "scene": "...", "object": "<id>", "f": 112, "dx": 0.4, "dy": -0.25}
{"type": "edit.timing", "rev": 7, "scene": "...", "clip": "<id>", "field": "run_time|start|anchor|rate_func", "value": 1.2}
{"type": "edit.prop",   "rev": 7, "scene": "...", "object": "<id>", "prop": "color", "value": "B_COLOR"}
{"type": "edit.confirm", "token": "<from edit.preview>"}           // accept side effects
{"type": "edit.cancel",  "token": "..."}
{"type": "undo", "file": "..."}   {"type": "redo", "file": "..."}
{"type": "render", "file": "...", "scenes": ["..."], "quality": "l"}
```

Later phases add `edit.scale`, `edit.rotate`, `edit.insert` (library drop),
`edit.delete`, `edit.reorder`, `edit.group`, `edit.text`, `edit.voice`, all
following the same shape: an intent, never code.

## WebSocket: server → client

```jsonc
{"type": "model", "file": "...", "rev": 7, "scenes": [Scene...], "census": {"1": 87, "2": 33, "3": 7}}
{"type": "frame.ready", "scene": "...", "rev": 7, "f": 112, "seq": 41,
 "objects": [{"i": 0, "id": "<id>", "box": [x0, y0, x1, y1], "angle": 0.0}]}
     // the browser then GETs /frame and (at rest) /idmap
{"type": "edit.preview", "token": "...", "summary": "shift() chained on get_title() (line 86)",
 "diff": [{"line": 86, "before": "...", "after": "..."}],
 "also_moves": [{"id": "...", "why": "other use of get_fog() (line 182)"}]}
     // only when the edit has side effects to confirm; otherwise straight to edit.done
{"type": "edit.done", "rev": 8, "summary": "...", "diff": [...], "undo": true}
{"type": "edit.refused", "reason": "x is set every frame by an updater (line 210)",
 "tried": ["shift() chained on get_fog() (line 209): moved (0, -0.25)"]}
{"type": "file.changed", "file": "...", "rev": 8, "by": "studio|external"}
{"type": "status", "file": "...", "engine": "tracing|ready|warming|error", "cursors": 9, "of": 12}
{"type": "error", "code": "parse|crash|timeout|stale|version", "message": "...",
 "where": {"file": "...", "line": 131}, "traceback": "..."}
{"type": "render.progress", "scene": "...", "done": 40, "of": 220}
{"type": "render.done", "scene": "...", "video": "media/videos/..."}
```

### Scene, Clip, Object

As in architecture.md section 4, serialised as JSON. Ids are strings built
from the identity key, e.g. `"Text@order_matters.py:43:15-43:61#0"` (class,
file, line:col-line:col of the creating call, occurrence). They change when
the code moves, and the server sends the old → new map with every `model`
after an edit (`"remap": {"old": "new"}`).

## Ordering and cancellation

- `seek` messages carry `seq`. The server drops a queued seek when a newer
  one arrives for the same scene; replies carry the `seq` they answer, and
  the client ignores anything older than the last one it showed.
- Edits are serialised per file: one at a time, in arrival order. While an
  edit is verifying, new edits wait (the UI shows a spinner on the object).
- After `edit.done` the client keeps showing the old frame until the
  `frame.ready` for the new revision arrives, so nothing flashes.
