# Error catalogue

Phase 6 step 7. Every way the studio can fail that we know of: what the
user sees, what still works, and how it recovers. "Checked by" says how
each row was proven: a test (`tests/...`), the browser pane (UI), or by
reading the code (code). Rows marked **new** changed in Phase 6.

## The file

| Case | What the user sees | What still works | Recovery | Checked by |
|---|---|---|---|---|
| Syntax error (saved from an editor) | Error bar: "The file doesn't run at line N", the message, the line with one line either side. **New:** the canvas and timeline keep the last version that ran, marked read-only. | Scrubbing, playing and selecting the last good version. **New:** its objects keep their names from that version (they were labelled from the broken file: "title" showed as "Text", tier 3) | Fix and save: reloads by itself | `engine/test_phase6.py::test_broken_file…`; UI |
| Crash while the module runs (`1 / 0` at the top, a missing import) | The same bar, with the traceback folded under it. **New:** the last good version is still shown. The "loading the file…" pill ends with the load (it kept counting after a failed load; found in the UI check) | As above | As above | `engine/test_phase6.py::test_broken_file…`; UI |
| A scene crashes part-way | "This scene stops with an error at line N". The clips before it play. | Every other scene; this scene up to the crash | Fix and save | `corpus_run.py` (`late_error.py`) |
| The file loops forever while loading or in a scene | **New:** after 4 s a "tracing X… 12 s [Stop]" pill. Stop ends the engine run; that scene (or the load) is marked "stopped" and skipped for these bytes. The other scenes are traced. Scenes with a cached trace show at once, before any scene is traced, so a looping scene never hides them. The stopped scene's frames are refused ("this frame didn't render: stopped …"), never run: a frame used to run the loop again until the deadline (found in the UI check). The skip list is kept in memory: after a server restart, Stop again. Before: up to 180 s, then restarts that looped again, three times. | The other scenes | Fix and save (new bytes are tried again) | `engine/test_phase6.py::test_stop_a_runaway_scene`; UI |
| The file is deleted or renamed while open | **New:** a toast, and the bar says "The file is gone". The studio keeps showing what it had. Edits are refused. Before: nothing happened, and the next edit failed with "can't read the file". | Looking around | Restore it (same name): picked up by itself | `engine/test_phase6.py::test_deleted_then_restored_file`; UI |
| The file is read-only | **New:** "the file is read-only; make it writable …". Before: "is it locked by another program?". Checked before writing, because an atomic replace would get round the flag on Linux and macOS. | Everything but writing | Make it writable | `engine/test_phase6.py::test_read_only_file_is_named` |
| The file is locked by another program (Windows) | "can't write the file (…); is it open and locked in another program?" | Everything but writing | Close the other program | code |
| A module it imports changes (`style.py`, `manim_kit.py`) | **New:** a toast, "a module … imports changed; restarting its engine". The engine restarts and the file is traced again. Before: the old module stayed loaded until a restart. | All of it, after a moment | Automatic | `engine/test_phase6.py::test_changed_local_module…` |

## The environment

| Case | What the user sees | What still works | Recovery | Checked by |
|---|---|---|---|---|
| LaTeX error in a formula | The TeX error in LaTeX's own words. The edit that caused it is refused and the file is left unchanged. | Everything | Fix the formula | `engine/test_phase5.py` |
| LaTeX not installed or not on PATH | **New:** "LaTeX isn't installed or isn't on PATH (MiKTeX or TeX Live); Text() works without it". Before: "see the LaTeX log", a log that never existed. | Scenes without TeX | Install MiKTeX or TeX Live | `unit/test_review_phase5_server.py::test_latex_missing_is_named` |
| Edge TTS offline or stalled | The scene plays without the line's sound. The narration lane says why. | Everything else | Automatic on the next run; the service has a 45 s timeout | Phase 4 |
| The disk is full | **New:** "the disk is full; nothing was written". | Reading | Free space | code |
| Port 8770 already in use | See the start-up row under "The connection" | | | |

## The engine

| Case | What the user sees | What still works | Recovery | Checked by |
|---|---|---|---|---|
| Worker crash (segfault, killed) | "the engine was restarted". The file reloads. | Everything, after the reload | Automatic | `engine/test_engine.py` |
| Worker too slow (past a deadline) | The same. After 3 restarts for the same bytes: "fix the code, then save". **New:** while the file doesn't run, the last good version is reloaded into the new engine so it can still be shown. | As above | Automatic, or Stop | `engine/test_engine.py`; code |
| Out of memory | A `MemoryError` comes back as a crash, or the process dies (see the first row). | As above | Simplify the scene | code |

## The connection

| Case | What the user sees | What still works | Recovery | Checked by |
|---|---|---|---|---|
| Server stopped | The red dot in the header. Edits can't be sent. | Nothing new | Start it: the page reconnects by itself and reopens the file and scene | UI |
| Server restarted | A new session: the frame caches are dropped. Undo history is gone (it isn't saved; see the plan). | Everything | Automatic | UI |
| Two tabs on one file | Both get every model. An edit planned in one tab against an older revision is refused with "the file changed; try again". | Both | Automatic | code (`rev`) |
| Port in use at start-up | See step 10 (a clear message instead of a traceback) | | | step 10 |

## Edits

| Case | What the user sees | Recovery | Checked by |
|---|---|---|---|
| Stale revision | "the file changed; try again" | Repeat the edit | `unit` |
| The file changed while an edit was checked | "the file changed on disk while the edit was checked; nothing was written" | Repeat | `unit` |
| A confirm after an outside change | "the file changed since this edit was planned; make the edit again" | Repeat | `unit` |
| The replay disagrees (verify failed) | The reason ("something later sets it again", …). Nothing is written. | Edit the code | the benches |
| Edit while the file doesn't run | **New:** "the file doesn't run; fix it first (the studio is showing the last version that ran)" | Fix the file | `engine/test_phase6.py` |
| A narration line in a scene with `VOICE = None` (the new-file template) | **New:** the edit is refused with "UiHandson.VOICE is None; set a voice (e.g. VOICE = "en-US-AndrewNeural") to narrate". Before: "object has no attribute 'speech_service'" (found in the hands-on run). The message comes from `TimedScene.say()` in `manim_kit.py`, so a command-line render says the same | Set `VOICE`, add the line again | UI |

## Export and the Claude panel

| Case | What the user sees | Recovery | Checked by |
|---|---|---|---|
| The preview server is rendering the same file | The export waits: "waiting for preview server". The preview server waits for an export the same way | Automatic | `engine/test_phase6.py::test_export_waits…` |
| A scene fails to render | That scene is marked failed, later ones skipped, nothing joined; the log is in the dialog | Fix, export again | code (`export.py`) |
| Cancel | The render process is killed; the lock is released; nothing joined | | `engine/test_phase6.py::test_export_waits…` |
| Narration missing from a render | "rendered, but the narration check found problems", with `audio_check.py`'s report | Re-render | UI (a passing check); `tools/audio_check.py` |
| Claude Code not installed | The panel says so; asking is off | Install Claude Code | `unit/test_claude_panel.py` |
| Claude Code fails or is stopped | "didn't finish" with its error, or "stopped" | Ask again | `unit/test_claude_panel.py` |
| Page opened from another machine | The panel is off unless `--allow-claude-remote` | Start with the flag | `unit/test_claude_panel.py` |
