# Phase 0: go / no-go

**Recommendation: go.** Every spike met its bar. The two that could have
stopped the project (S1 speed, S2 round-trip) passed on real scenes, with
known, bounded gaps. No change to the plan's direction; a handful of
changes to its details, listed below.

| Spike | Bar | Result | Verdict |
|---|---|---|---|
| S1 frame at time | median < 0.5 s (2D), < 2 s (3D) | Live cursors: 2D 0.10–0.29 s random access, 20–120 ms scrubbing; 3D 0.8–1.45 s. Frames match the real render | Pass ([S1](S1_frame_at_time.md)) |
| S2 round-trip edit | drag works in test_scene and order_matters; minimal diff; no-op byte-identical | 319 of 336 drags (95%) verified exact across three files; median diff 33 bytes; back-drag restores the file byte for byte every time; no-op makes no edit | Pass ([S2](S2_round_trip.md)) |
| S3 identity | ≥ 95% correct | 100% of 7,000+ clicks in 16 scenes, stable across replays | Pass ([S3](S3_identity.md)) |
| S4 timing model | written recommendation with code samples | `at(t)` anchors + one `play()` per overlap group + a 3-line `clip()` helper; every timeline edit mapped to a literal edit | Done ([S4](S4_timing.md)) |
| S5 census | tier breakdown | 65% tier 1, 29.5% tier 2, 5.4% tier 3 over 1,198 statements; timeline code 99.4% tier 1–2 | Done ([S5](S5_census.md)) |

## Why it works

Three ideas carried the spikes, and all three go into the product:
1. **Replay is the engine.** Running `construct()` with plays skipped, and
   keeping paused runs ("cursors") along the timeline, gives exact frames
   without rendering video.
2. **Every object knows its line.** Wrapping `Mobject.__init__` and the
   positioning methods records where each object was made and moved, with
   exact column spans. No markers in the user's code.
3. **Verify by replay.** Every code edit is tried in memory and replayed
   before it's offered. A wrong edit is never written; it falls through to
   the next candidate or is refused.

## What changes in the plan

- **Phase 1 engine:** the cursor pool runs cursors in worker processes,
  not threads (removes GIL outliers), plus an LRU frame cache keyed by
  scene, frame and code hash. 3D draws at lower resolution while
  dragging.
- **Phase 3 work list** (from S2's gaps): pattern rules for kit objects
  placed by their own arguments (`ClippedGrid`); helpers that return
  tuples; an "also moves N other uses" warning for in-helper edits; drag
  locked to one axis when the other is driven by an updater; dragging only
  at still moments and play ends.
- **Timing (S4):** answers the two open questions. Overlaps are plain
  Manim (`Succession(Wait(d), anim)` behind `clip()` in `manim_kit.py`).
  GUI-made scenes default to `TimedScene` with `at(t)` anchors; sequential
  scenes stay editable.
- **Inspector (S5):** needs a literal editor for tier-2 expressions (edit
  the `1.4` in `blob.get_top() + UP * 1.4`). Tier 3 shows as read-only
  code.

## Risks still open

- **One long motion across several groups** (S4): needs its own spike in
  Phase 4.
- **Manim internals.** The spikes patch `CairoRenderer.play`,
  `Mobject.__init__`, the positioning methods and `Transform.begin`. All
  go behind one adapter module, pinned to 0.22.1.
- **Warm-up:** a cursor pool takes 4–25 s to fill after a code change.
  The first frames come from plain replay meanwhile (0.3–1.6 s in 2D).
  Acceptable; worth showing a progress hint.
- **Shared renders with the preview server** (Windows LaTeX lock): the
  spikes used their own `media/Tex_studio` folder and never collided.
  Keep that.

## Found along the way (fixed outside the studio)

- manim-voiceover 0.4.0 appends a cache entry on every line, hits
  included. `media/voiceovers/cache.json` had grown to 934 entries and
  then broke (`JSONDecodeError`). `edge_tts_service.py` now skips the
  write on a hit; the file was rebuilt with 95 entries (backup in
  `media/backups/`). Renders checked: cache unchanged, narration present.
- Parallel Text creation in threads left empty SVGs in `media/texts/`.
  The spike engine serialises file-backed mobject creation; the empty
  files were deleted.
- A cached `play()` advances the clock by exactly its duration, while a
  real one adds a frame at a time. A partly cached render can be a frame
  off. Documented in S1 and S4.

## Next

Phase 1 (design): architecture and the engine↔UI protocol, the editable
code specification (from S2, S4, S5), UX wireframes, the compatibility
corpus and test strategy. Its exit is your OK on the wireframes and the
code specification.
