# S3: from the thing on screen to the line of code

**Question:** when the user clicks something in the viewer, can the engine
say which line of code made it, and keep saying the same thing on every
replay?
**Bar (PLAN.md):** at least 95% correct.
**Verdict: pass.** Every one of 7,000+ clicks across 16 scenes resolved to
the right line, and the result was identical on a second replay.

Code: `studio/spikes/identity.py`; benchmark `studio/spikes/s3_bench.py`.
Results are saved as JSON in `media/studio_spikes/s3/`.

## How it works

1. **Every mobject records where it came from.** `Mobject.__init__` is
   wrapped. When an object is made, the engine walks up the call stack past
   the object's own construction chain (super() calls, wrappers) to the code
   that asked for it. If that code is in the scene file, the object is
   *primary*, and its **site** is the exact call: file, line, end line and
   columns, taken from `co_positions()`. So in
   `Text("Order matters", font_size=...)` the whole call expression is
   located, not just the line. The engine also records:
   - **user_site:** the innermost scene-file frame. A curve made inside
     `axes.plot(...)` gets the `axes.plot(...)` line.
   - **chain:** every scene-file frame on the stack. A Text made inside
     `get_heading()` also knows which construct() line called the helper.
   - **occurrence:** a counter per site, so objects made in a loop stay
     distinct.
2. **Copies.** A `.copy()` in the scene file gives the copy its own site
   (the copy line) and remembers the original. A copy made inside a library
   is re-stamped with the user line running at the time. Without that, Text's
   SVG cache hands out glyphs that point at the line that *first* made that
   text.
3. **Updater-built objects** (always_redraw, ClippedGrid's lines, rebuilt
   every frame) are marked *regenerated*. They belong to the object that
   holds them, not to whichever `self.play(...)` happened to be running.
4. **A click resolves upward** from the drawn leaf (one glyph, one surface
   face):
   - **Made by a scene-file call:** select it.
   - **Made inside a scene-file call:** walk up while ancestors came from
     that same call. If one of them *is* that call's result, select it (a
     glyph selects its Text). Otherwise select the biggest group the call
     made (the whole grid of `ClippedGrid(...)`, a `thought_cloud_for(...)`
     cloud).
   - **Regenerated:** resolve the holder instead.
5. **Hit-testing (benchmark only):** the frame is redrawn with every leaf in
   a unique flat colour (an ID buffer), so each pixel names the leaf drawn
   there. The real UI can use the same ID buffer.

## Results

At 4–6 sampled times per scene, every drawn leaf with at least one clickable
pixel was clicked once.

| File | Scenes | Leaves drawn | Clicked | Primary | Factory | Unknown | Right | Stable |
|---|---|---|---|---|---|---|---|---|
| order_matters | 5 | 2,754 | 1,970 | 1,764 | 206 | 0 | 100% | 100% |
| gradient_descent 2D | 7 | 1,984 | 1,717 | 1,695 | 22 | 0 | 100% | 100% |
| gradient_descent 3D | 4 | 22,435 | 15,742 | 15,742 | 0 | 0 | 100% | 100% |

- **What "right" means.** Automatically: the source text of the resolved
  call contains the selected object's class name (or a base class), or is a
  `.copy(`. Factory picks were listed and checked by hand. I also read
  through every distinct selection in several scenes. Examples:
  - a 3D surface face → the `Surface` in `get_landscape()`;
  - a trail segment → `get_trail_piece()`;
  - the heightmap → its `ImageMobject`;
  - η labels → `get_eta_label()`;
  - caption glyphs → the scene's `caption_mobject()`;
  - grid lines → `ClippedGrid(...)`;
  - a label's backing box → `lbl.add_background_rectangle(...)`.

  None was wrong.
- **Unclicked leaves** (about 30% of drawn ones) were fully covered by
  something in front, or invisible at that moment. Thin lines do count: a
  pixel needs only 2 same-coloured neighbours. The UI needs a layers list and
  "select what's underneath" (Alt-click cycling) for covered objects.
- **Cost:** tracking adds 13–30% to replay time (ShearThenRotate 1.32 →
  1.71 s, Descent3D 1.62 → 2.14 s). The first version cost 5×. It resolved
  file paths and rebuilt position tables on every object.

## What the studio gets from this

- **Click → code:** the exact call span to highlight in the code panel, with
  "made in `get_heading()`, called from line 157" from the chain.
- **Stable identity:** `(site, occurrence)` is reproducible between
  replays. That is the key for keeping a selection alive across edits. When
  an edit moves lines, the sites move with it; that mapping is S2's job.
- **Library boundary:** `manim_kit.py` and Manim are not editable
  "sources". Their parts resolve to the scene-file call that used them, so
  dragging Blob's eye selects the Blob.

## Limits found

- **Selection is by creation, not by last change.** A `.next_to(...)` or
  `place(...)` that moves an object after creation is not part of its
  identity. S2 needs to find those calls in order to edit a position.
- **One shared factory call, many objects.** A helper like
  `get_eta_label()` used at three call sites has one site and three chains.
  An edit inside the helper changes all three. The UI must say so, and
  offer to edit the call site instead.
- **Objects made outside any scene-file frame** (at module level, or by a
  library with no user caller) would resolve to their nearest primary
  ancestor or to "unknown". None appeared in these 16 scenes.
