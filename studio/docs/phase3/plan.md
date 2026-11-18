# Phase 3 plan: direct manipulation

PLAN.md §5, Phase 3: drag, scale and rotate on the canvas, written back to
code; snapping and alignment guides; add objects and animations from the
library by drag and drop; delete, duplicate, group; undo and redo; tier-2
overrides.

**Exit:** a short scene can be built from a blank file without typing code,
and the result reads like hand-written Manim. Corpus target (corpus.md §4):
≥ 90% of on-screen objects drag-editable, verified.

Rules: code_spec.md §4.1, 4.2, 4.5, 4.6, §5 and §6. Evidence: the S2 spike
(`spikes/code_edit.py`), which this phase turns into product code.

## Steps

| # | Piece | Where | Checked by |
|---|---|---|---|
| 1 | **Move recording** in the engine: every positioning, scale and rotate call records its scene-file site and kind (static, animate, updater, laid out by `arrange`), per thread. `Transform(a, b)` records `b` on `a`. Objects report their recent moves, a reference point (for rotate/scale checks), their parent groups, and the frame size in units. | `engine/moves.py`, `runtime.py` | engine tests |
| 2 | **Move / scale / rotate planner**: ranked candidates per code_spec §4.1–4.2 (literal vector → merge into a chained shift → chain on the placing call → this use of a helper → new line after a layout or a tuple unpacking → animate vector → inside the helper, confirmed). Round trip: a term or call that returns to zero is removed. | `code/moves.py` | unit tests (vectors in every written order, zero removal, angles, scales) |
| 3 | **edit.move / edit.scale / edit.rotate**: try candidates in order, verify each by replay at the same frame (centre, size and reference point within 0.01), calibrate once for a scaled parent, report other objects that moved; edits inside a helper ask first. Refused while the object is mid-animation. | `project.py` | engine tests; corpus run measures the drag rate |
| 4 | **Tier-2 overrides**: an object made in a loop, a comprehension or a helper that returns a group gets `group[i].shift(...)` / `.set_color(...)` on a new line after the group's last placement; the preview offers "only this one" next to "every pass of the loop". | `code/moves.py`, `planner.py` | unit + engine tests |
| 5 | **Insert from the library** (edit.insert): a creation statement and an entrance at the playhead (code_spec §4.5); `place(..., region)` when dropped on a region; animation presets dropped on an object add a `play()`. **New scene file** from the §6 template. | `code/inserts.py` | unit tests; blank-file build test |
| 6 | **Delete, duplicate, group** (code_spec §4.6), delete a clip. | `code/inserts.py` | unit + engine tests |
| 7 | **UI**: selection box with move, corner-scale and rotate handles; the object's own pixels follow the mouse (cut out with the ID map) so a drag needs no engine; snapping to the frame centre, safe area, `grid_point` columns, regions and other objects, with guides; Shift locks an axis, Alt turns snapping off; Library tab; Delete / Ctrl+D / Ctrl+G / Ctrl+Y; Shift-click multi-select; Alt-click selects the parent group; Layers as a tree. | `web/src` | browser pane |
| 8 | **Exit check**: build a short scene from a blank file through the UI; corpus run with drags; exit report. | `docs/phase3/exit_report.md` | |

## Decisions taken here

- **Verification is the same as Phase 2**: replay the edited bytes, measure the
  object at the same frame. A move is right when the centre moved by the drag
  within 0.01; a scale or rotate when the centre stayed and a reference point
  on the object landed where the transform puts it.
- **Insertion time in a sequential scene**: the new statements go after the
  last statement that ends at or before the playhead. If a literal
  `self.wait(d)` covers the playhead, it is split around them, so later clips
  keep their times whenever the wait is long enough. In a `TimedScene` they go
  after the last statement before the playhead with `self.at(t)`.
- **Deleting an object** removes its creation statement and every statement that
  only uses it (`self.add(x)`, `x.shift(...)`, a `play()` of it alone; one
  animation out of a shared `play()`). Any other reader refuses with the lines.
  An `at()` left with nothing to time is removed with it.
- **Colours and sizes in inserted code** use `style.py` names when the file
  imports it, else Manim's own constants. Nothing is imported silently except
  `manim_kit` for kit parts (code_spec §4.5).
