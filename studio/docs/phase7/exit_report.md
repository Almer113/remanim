# Phase 7 exit report

Plan: `plan.md`. The exit video: `plans/odd_squares.md` (plan and
friction log), `odd_squares.py`. Checked on 2026-11-24.

## The exit criteria

| Criterion | Result |
|---|---|
| A second real video made with the code-only steps of the Euler log done in the studio: add the scenes, set each scene's length, narrate a silent scene, retime without leaving a fade over a spoken line | **Met.** "Odd numbers make squares", 5 scenes, 52.6 s, made by Claude driving reManim in the browser pane. Scenes, `TARGET`s, the first line (which set the voice), timing and one scale were done in the studio; code was written for the `Beat` base, the helpers and the `construct()` bodies (see "The video") |
| That run's friction log has no "blocks" entries | **Met**: 10 entries, 4 "slows", 5 cosmetic, 1 note; 2 fixed on the spot |
| Tests and the corpus run green | **Met**, after one fix found by the speed bench (below) |
| `preview_server.py` and the check tools untouched in behaviour | **Met**: no commit since Phase 6 (`4dc96d3`) touches `preview_server.py`, `tools/`, `manim_kit.py`, `style.py` or `edge_tts_service.py` |

## Steps

| Step | What it became |
|---|---|
| A1 scene arrows | ◀ ▶ and PageUp / PageDown go to the previous / next scene; "Render order…" in the dropdown |
| A2 New file dialog | name, class, voice on/off, `TARGET`; used for the exit video |
| B3 + scene | after this scene or at the end, same base and `TARGET`; used four times |
| B4 `TARGET` field | type, "fit", "+ target"; ripple moves a literal `TARGET` and the toast says so |
| B5 narrate a silent scene | `+ line` asks for the house voice and sets it on the class or the base, one undo step |
| C6 mid-sentence warning | badge on the clip and a line in the toast; fired on the deliberate test case |
| C7 snap to narration | line ends are snap points; "end of line" in the pause field |
| D8 read-only up front | computed fields greyed with the reason before any typing |
| D9 Inspector values | scale and turn from the code, now also from a later placement statement (fix 4 of the log); moves to 2 decimals |
| D10 splitter | canvas / timeline, remembered per browser |
| D11 timeline clicks | empty lane seeks, lane name selects |
| D12 small ones | Layers "loading…", accessible button names |
| E13 undo from the frame cache | content-aliased revisions; undo and redo ~1.5 s in the pane |
| E14 reconnect with backoff | 1, 2, 4 … 10 s; at once on focus, online, visible |
| E15 UI frame time in a visible pane | probe in `web/src/probe.ts` (`window.__frameProbe`); 8 runs: median 16.7 ms; 6 with no frame over 50 ms, 2 with one 200–216 ms frame on the first scrub after the window was shown (below) |
| F16 exit check | this report |

## The video

`odd_squares.py`: `Sums`, `Layers`, `WhyOdd`, `General`, `Takeaway`;
9 narration lines with captions. Exported from the studio at `-ql`
(53.0 s joined), then `-qh` (52.6 s, 1920×1080 at 60 fps).
`audio_check.py` passed on each scene and on the joined file.

Done in the studio: the file (voice off, `TARGET` 10), four scenes, the
first line (asked for the voice, set it on `Beat`), six timing edits (four
typed pauses, one "end of line", one deliberate mid-sentence fade then
undone), one `TARGET` fit, Undo/Redo three times, one Inspector scale, the
splitter, a lane-click seek, both exports with the narration check.

Done in code, because the studio can't express it: the `Beat` base and
its caption look, the helpers (dot layers, sums, the general equation),
the loops in each `construct()`, `caption=` on every line (friction 1),
and the sizes after the first contact sheets.

Friction log, open entries (details in `plans/odd_squares.md`):
1. `+ line` has no caption field (slows).
2. A TTS retry is invisible: ~45 s of "Verifying…" (slows).
5. The undo toast's arrow reads backwards (cosmetic).
6. Layers lists every dot expanded; captions are unnamed "Text" (slows).
7. The template comment "# set a voice to narrate" stays after the voice
   is set (cosmetic).
8. "End at" has no "line end + 0.5 s" (cosmetic).
10. The `-qh` export warned "low quality first" after a server restart
    (cosmetic, misleading).

Fixed on the spot: 3 ("end of line" offered on a computed pause) and 4
(Inspector scale after a chained later-statement scale). 9 (undo history
lost on restart) is by design.

## Tests

`python -m studio.tests --all`, run twice: before and after the speed fix
below. Both all green.

| Step | Phase 6 | Phase 7, run 1 | Phase 7, run 2 (with the fix) |
|---|---|---|---|
| Unit + engine (`pytest studio/tests`) | 426 passed, 11 min 32 s | 489 passed, 14 min 23 s | 489 passed, 14 min 54 s |
| Corpus run | 27 files, 93 scenes, all OK | 29 files, 104 scenes; the two expected errors only (`chapter0.py` is ManimGL, `broken_syntax.py` on purpose); no bad frames; no-op save byte-identical everywhere | same, except two gallery files timed out on load while other projects' jobs loaded the machine (corpus step 1475 s against 943 s); both re-run alone: clean |
| Census | 1686 statements; tier 1 64.7 %, tier 2 30.4 %, tier 3 4.9 % | identical | identical |

The two new files (`euler_identity.py`, `odd_squares.py`) are in the
corpus now, which is where the extra tests, files and scenes come from.

Gap noticed: the corpus run reports "ok" when a file's load times out and
the engine restarts. That's how it recovers, by design, but the summary
should count those so a slow file can't hide in a green run.

## Benches against Phase 6

**Drag** (`drag_run.py`): 193 tried, 179 moved (92.7 %), 178 back, 21
asked to confirm. Identical to Phase 6.

**Clip** (`clip_run.py`): on every file that both runs share, the counts
are identical (retimable, locked, refused), and 0 verify failures. The
totals read differently (848 clips against 1006) only because the Phase 6
report also counted five scratch copies (`review_*.py`, since deleted)
and this one adds the two new videos: 1006 − 279 + 57 + 64 = 848.
Retimable 77.8 %. New lock reason "padding to TARGET" (16 clips; step B4).
Total time 938 s against 1,494 s in run 1.

**Speed** (`speed_run.py`), medians:

| Measure | Phase 6 (10 files) | Phase 7 run 1 (12) | Phase 7 run 2 (12) | Target |
|---|---|---|---|---|
| Cold open, first scene shown | 6.3 s | 5.5 s | 5.5 s | no slower |
| Cold open, all traced | 8.7 s | 9.0 s | 8.3 s | no slower |
| Reopen, every scene shown | 1.2 s | 1.1 s (`eola_preview` **6.4 s**) | 1.0 s (`eola_preview` 1.15 s) | ≤ 3 s |
| Edit → new frame: retime, drag, colour | 1.9, 1.9, 1.9 s | 1.9, 2.3, 5.2 s | 1.6, 2.1, 2.2 s | ≤ 2 s in 2D |
| Undo: retime, drag, colour | 4.4, 2.7, 3.0 s | 1.6, 1.5, 1.3 s | 1.3, 1.2, 1.2 s | (E13) |
| Scrub | 0.03 s | 0.06 s | 0.06 s | ≤ 0.3 s |

On the 10 files both phases ran, run 2's edit medians are 1.6 / 1.8 /
2.2 s, against 1.9 / 1.9 / 1.9 s. The colour median above 2 s comes from
`gradient_descent`, `order_matters` and `pythagoras`, whose verify run is
the scene's own play time, as in Phase 6. Undo is 2–3× faster: that's E13.

### The slowdown run 1 found, and its fix

Run 1 had every `eola_preview.py` edit at ~6.5 s (Phase 6: 1.7 s) and
its reopen at 6.4 s (1.3 s). The re-run reproduced it. A profile showed
90 % of the time in `ast.walk`: Phase 7's scene model (read-only fields,
the mid-sentence check, scale and turn) asks `Source.find_call` about
15,000 times per model of that file, and `statement_at` about 3,500
times, and each call walked the whole tree.

Fix (`server/code/source.py`): three lookup indexes, built on first use
per parsed `Source` (the tree never changes after parsing): calls by end
position, simple statements by line, and each call's enclosing call
(`splice._enclosing_call` now uses it). Results are the same, picked in
the same `ast.walk` order. 443 unit tests passed, then run 2 above.
`eola_preview`: reopen 6.4 → 1.15 s, edits 6.5 → 1.6–2.2 s; the clip
bench on it went from 736 s to 277 s.

## UI frame time (E15)

Measured on 2026-11-25 in the visible pane (1284×905), deployed server
with the speed fix, `eola_preview.py` → `S16_ExampleMatrixMultiplication`.
The probe (`window.__frameProbe`) times every animation frame, so render,
layout and paint are all in it. The scrub: mouse down on the ruler, then
a mouse move every 16 ms for 6 s, start → end → start, through the
page's own handlers.

| Run | Scene | Frames | Median | p95 | Max | Over 50 ms |
|---|---|---|---|---|---|---|
| 1 (11-24, first after the pane was shown) | S16 | 378 | 16.7 ms | 17.0 ms | 216 ms | 1 |
| 2 (11-25, first after the window came to the front) | S16 | 379 | 16.7 ms | 17.0 ms | 200 ms (391 ms in) | 1 |
| 3 | S16 | 391 | 16.7 ms | 16.9 ms | 18.0 ms | 0 |
| 4 | S16 | 390 | 16.7 ms | 16.9 ms | 19.6 ms | 0 |
| 5, after 30 s idle | S16 | 390 | 16.7 ms | 16.9 ms | 19.5 ms | 0 |
| 6, frames never shown before | S15 | 388 | 16.7 ms | 16.9 ms | 50.0 ms | 0 |
| 7, frames never shown before | S17 | 390 | 16.7 ms | 16.8 ms | 19.5 ms | 0 |
| 8 | S17 | 391 | 16.7 ms | 16.8 ms | 19.1 ms | 0 |

The frames are paced by the display (16.7 ms = 60 Hz). **The target (no
frame over 50 ms) is met in 6 of 8 runs**, including on scenes whose
frames hadn't been shown yet; S15's worst frame sat exactly on 50 ms.
The two misses are each a single frame of 200–216 ms in the first scrub
after the page or window became visible. Idle time doesn't bring it
back (run 5), nor do cold frames (runs 6–7), and no long task was
recorded on runs 6–8. So it looks like a one-off cost of showing the
page (compositor or GPU warm-up) rather than the studio's work. It isn't
proven: the probe can't see inside the browser's paint.

Runs between 1 and 2 gave no data: the page's `visibilityState` was
"hidden" except for 20 ms every 2 s (the probe flags it,
`hidden: true`), throttling frames to one per 2 s, while the app window
was behind another one.

Phase 6, for comparison (pane hidden, render + layout only, no paint):
median 9.6 ms, p95 18.3 ms, max 34.9 ms.

## Open after Phase 7

- E15: the 200 ms frame on the first scrub after the window is shown;
  probably the browser, not proven.
- Friction entries 1, 2, 6 and 8 (above). 5, 7 and 10 were fixed in the
  review after Phase 7 (`docs/review_phase7.md`).
- The corpus summary should count load timeouts.
- Carried: z moves in 3D, an out-of-camera view in 2D.
- Name and licence (waiting for a decision).
