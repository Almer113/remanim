# Test strategy

How the studio proves its promises (PLAN.md section 3) on every change.
The corpus is in [corpus.md](corpus.md).

Test runner: `pytest` is **not** installed in the venv. Two options, decided
at the start of Phase 2:
- **Recommended:** install `pytest` into `.venv` (needs your OK). Standard,
  good failure output, parametrises over corpus files.
- Without it: the standard library's `unittest`, which works but is wordier.

Layout:

```
studio/tests/
  corpus/            awkward files (+ gallery in Phase 2)
  unit/              code layer: spans, formatting, splices, patterns (no Manim)
  engine/            replay, clock, identity, moves (Manim, dry_run, no video)
  roundtrip/         the guarantee suite below, over the whole corpus
  ui/                browser checks through the preview pane
```

## 1. The guarantee suite (runs on every commit)

Each guarantee is a parametrised test over every corpus file. Scene files
are copied to a temp folder first; the originals are never written.

| Guarantee | Test |
|---|---|
| 1. No-op safety | open → model → save → bytes identical (sha256) |
| 2. Minimal edits | for each edit kind on sampled objects/clips: the diff touches only the planned spans; parse the result; everything outside the spans is identical |
| 3. GUI code is tier 1 | every statement the studio inserts classifies as tier 1 in the census |
| 4. No hidden state | delete the sidecar → the model is identical; a frame from the studio engine equals a frame from a plain `manim -s` render of the same scene and time (mean pixel diff ≤ 2, as in S1) |
| 5. Undo is exact | edit → undo → bytes identical; edit → undo → redo → bytes identical to the edited file |
| Round trip | drag by d then by −d → bytes identical (S2's back check); timing edit and back → identical |

## 2. Unit tests (code layer, fast, no Manim)

- Spans: every call in the corpus maps to the exact bytes `ast` reports, on
  CRLF and LF files, with unicode before the call.
- Number formatting: `fmt()` round-trips; style preservation (`0.5`, `2`,
  `.5`, `2.`).
- Vector edits: add a term, change a term, remove a term that becomes zero,
  with every written order (`UP * 0.5`, `0.5 * UP`, `-UP`, `UP / 2`).
- Inserted statements: indentation, line ending, never after a `return`.
- Census: tier of each statement in the awkward files matches an expected
  table checked into the test.

## 3. Engine tests (Manim, dry_run)

- **Clock:** traced start/duration of every clip equals the timeline JSON
  that `tools/timeline_render.py` writes for a real render, to the frame.
- **Frames:** studio frame vs `manim -s` render at 10 times per scene
  (sampled corpus; full corpus nightly).
- **Identity (S3 bench as a test):** ≥ 99% of clicks resolve to the right
  line, and the same line on a second replay.
- **Moves (S2 bench as a test):** verified-move rate per file, compared with
  the targets in corpus.md; a drop of more than 2 points fails.
- **Isolation:** `broken_syntax.py` and `broken_runtime.py` report the right
  error and line; a scene with `while True: pass` is killed at the deadline
  and the server keeps answering.
- **Determinism:** `Unseeded` is flagged; `Seeded` gives identical frames on
  two runs.

## 4. Edit fuzzing (nightly, and before each phase exit)

Random sequences of 20 GUI edits (move, retime, property, undo, redo) on
copies of corpus files, with a fixed seed per run. After each step: the file
parses, every scene traces, and undoing everything restores the original
bytes. Failures are saved with the seed and the edit list, so they replay.

## 5. UI checks

Through the browser pane, as with the preview server: open each corpus file,
scrub, select, drag one object, retime one clip, undo both; check the
console has no errors and take a screenshot for the phase-exit report.

## 6. Repo tools still work

On any scene the studio has edited: `tools/check_layout.py` passes as
before, `tools/frames.py` renders, and narrated scenes pass
`tools/audio_check.py`. The preview server keeps working while the studio
runs (both watching the same folder).

## 7. Phase exits

Each phase ends with a short written report in `studio/docs/phaseN/`:
the guarantee suite green, the corpus targets met (corpus.md section 4),
and the UI screenshots. Same format as the Phase 0 go/no-go note.
