# S2: drag on screen, edit the code

**Question:** when the user drags an object in the viewer, can the studio
turn that into a small, readable edit of the `.py` file that moves exactly
that object by exactly that much, and nothing else?
**Bar (PLAN.md):** drag works in `test_scene.py` and `order_matters.py`;
the diff is minimal; a no-op save is byte-identical.
**Verdict: pass, with three pattern gaps to close in Phase 3.**

| File | Objects dragged | Moved exactly | Back-drag restores bytes | Failed |
|---|---:|---:|---:|---:|
| test_scene.py | 6 | 5 | 5 / 5 | 1 (correctly rejected) |
| order_matters.py | 149 | 137 (92%) | 137 / 137 | 12 (one pattern) |
| gradient_descent.py, 2D scenes | 181 | 177 (98%) | 177 / 177 | 4 (correctly rejected) |

- Every edit was checked by replaying the edited file to the same moment
  and measuring the object: it moved by (0.4, -0.25) within 0.01, or the
  edit was rejected. No unverified edit is counted.
- Diff size: median 33 bytes, largest 55.
- Dragging back by the opposite amount gave the original file byte for
  byte in every case (the zero term or the added `.shift()` is removed).
- A drag of zero makes no edit, so saving without a change leaves the file
  byte-identical. Scene files were checked unchanged (md5 and git) after
  all runs.

Code: `studio/spikes/code_edit.py` (recording and edit planning),
`studio/spikes/s2_bench.py` (the benchmark). Results in
`media/studio_spikes/s2/` (`<file>.json`, `<file>_run.txt`).

## How it works

1. **Record moves while replaying.** Every positioning call (`shift`,
   `move_to`, `next_to`, `to_edge`, `arrange`, `scale`, ...) is wrapped. Each
   call records which scene-file line made it and how:
   - *static*: an ordinary call;
   - *animate*: inside `mob.animate.<method>(...)`. Credited only when the
     object is the animation's own target, so moving a pupil inside a
     `Blob.animate` call isn't credited to the Blob;
   - *updater*: inside an updater;
   - *laid out*: placed by a group's `arrange()` / `next_to` chain. Every
     descendant is marked, with its index path from the group.
   `Transform(a, b)` also records `b` on `a`: what's drawn as `a` is now
   placed by `b`'s code too.
2. **Rank candidate edits** for the selected object, from its last move:
   - change the numbers in a literal `shift(...)` / `move_to(...)`;
   - merge into an existing chained `.shift(...)`;
   - chain a new `.shift(0.4 * RIGHT + 0.25 * DOWN)` on the creating call;
   - laid-out child: insert `row[0][1].shift(...)` on a new line after
     the layout statement (the object's own name if it's in scope there);
   - made in a helper: chain the shift on *this use* of the helper first
     (nearest call first); editing inside the helper comes last, because
     it moves every use.
3. **Verify by replay.** Apply the top candidate in memory, replay the
   edited file to the same time, measure. If it's wrong, try the next. If
   a later `scale()` scales the shift (the object moved by 0.8× the drag),
   correct the amount once and re-verify ("calibrate by replay").
4. **Write bytes, not ASTs.** Edits are byte splices into the original
   file. Formatting, comments and line endings (CRLF) are untouched outside
   the edited span. Numbers keep their style: `0.5` stays a decimal, `2`
   stays an integer when the result is whole.

Examples of real edits (order_matters):

```python
# literal shift: numbers changed
blob = Blob(BLOB_COLOR, height=2.0).to_corner(DL, buff=0.7).shift(UP * 0.5)
#                                                → .shift(UP * 0.25 + 0.4 * RIGHT)

# helper use: shift chained on this call only
title = get_title().shift(0.4 * RIGHT + 0.25 * DOWN)

# arranged child: a new line after the layout
row = VGroup(lhs, rhs).arrange(RIGHT, buff=0.3)
row[0][1].shift(0.4 * RIGHT + 0.25 * DOWN)
```

## Edit kinds that won

order_matters (137 moves): 51 shifts chained on the nearest helper call;
22 whole-group moves; 21 inserted lines after a layout; 15 edits inside a
helper; 13 chained shifts; 10 literal shift numbers changed; 3 literal
`move_to` numbers changed.

gradient_descent (177 moves): 62 won with the first candidate. 115 needed
the in-helper fallback (see gaps 2 and 3 below).

## Gaps (all found, none silent)

1. **Library objects placed by their own arguments.** All 12 order_matters
   failures are `ClippedGrid` parts: the grid places itself from its
   `("ellipse", centre, a, b)` argument, so chaining `.shift()` on it
   doesn't move what's drawn. Fix: a pattern rule per kit object ("move
   ClippedGrid = edit its centre argument"). Phase 3.
2. **Helpers that return tuples.** `dots, hops = get_map_path(path)`:
   chaining `.shift()` on the call crashes on the tuple (the replay caught
   it). The bench then fell back to editing inside the helper, which
   works but also moves the other use of the helper. Fix: shift the
   unpacked name on a new line (`dots.shift(...)`). Phase 3.
3. **In-helper edits move every use.** 115 gradient_descent moves and 15
   order_matters moves edited inside a helper (`get_map_path`, `get_fog`,
   captions). Correct for that object, but other uses move too. The GUI
   must say so before saving ("also moves 2 other uses of get_fog()") and
   offer "this one only" (gap 2's fix) where possible. For captions this
   is usually what the user wants: the house caption position.
4. **Axes driven by an updater.** The 4 gradient_descent failures are the
   fog, whose x follows a tracker every frame
   (`fog.add_updater(lambda m: m.move_to(RIGHT * x.get_value(), ...))`).
   Only its y can be dragged; every x edit was correctly rejected by
   verification. The GUI should lock the drag to y for such objects.
5. **Mid-morph moments.** test_scene's one failure is a drag during a
   `TransformMatchingTex`: the edit crashed on replay and was rejected.
   The GUI should only offer dragging at still moments, or at play ends.

Side effects to show the user: 21 step-label drags in order_matters moved
a sibling too (the fallback moves the whole group, because the layout sits
inside a `return`), and 5 panel-grid drags moved the whole panel. Other
"also moved" objects were genuine dependents (a speech bubble placed
`next_to` the Blob; a label and its background box).

## Implications for the plan

- Keep verify-by-replay in the product: it's what makes this safe. It
  costs one replay per candidate (S1: 0.1–0.3 s in 2D with live cursors).
- Phase 3 work list: pattern rules for kit objects, tuple returns, the
  "also moves N uses" warning, axis locks for updater-driven objects,
  and still-moment-only dragging.
- The edit vocabulary (`.shift()` chained, literal edits, inserted lines)
  reads like code a person would write. No IDs or markers in the source.
