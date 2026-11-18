# Rolling downhill: gradient descent

**Purpose:** a second, harder test of our workflow (after `order_matters.py`).
It covers what we haven't tested yet: 3D scenes, camera moves, surfaces,
drawing contour lines ourselves, a mix of 2D and 3D beats in one video, and a
longer narrated piece (~2.5 min, 11 beats).

**Audience:** someone who knows what a slope is, has maybe heard "AI learns
by gradient descent", and has never seen why it works or how it goes wrong.

## Feasibility probe (done before planning)

A throwaway scene (`scratchpad/probe3d`) combined our `TimedScene` with Manim's
`ThreeDScene`, drew a 32×32 surface, rolled a ball across it while the camera
circled, then swung the camera to look straight down.

- **Works:** the two scene classes combine cleanly
  (`class Beat3D(TimedScene, ThreeDScene)`). Text pinned to the screen with
  `add_fixed_in_frame_mobjects` stays put while the camera moves, so captions
  will work.
- **Gotcha:** `Surface(checkerboard_colors=None)` crashes; it has to be `False`.
- **Problems to design around:**
  1. **Tall walls left the frame.** The surface's height has to be scaled down,
     and the domain kept to about ±1.8.
  2. **Faces drew over the ball.** With a see-through surface, Manim's 3D
     drawing order put far faces over the ball. Make the surface opaque, and
     float the ball slightly above it.
  3. **The top-down view was warped.** Looking straight down through the 3D
     camera gave a pinched, perspective view. The top-down view will be a
     separate flat 2D scene (a contour map), not a camera move.
- **Speed:** 56 s to render 6.5 s at 480p, and 245 s at 1080p60. See
  "Render cost" below.

## Maths (checked numerically)

Landscape: f(x, y) = 0.35·(x² − 1)² + 0.25·y² + 0.12·x, on −1.8 ≤ x, y ≤ 1.8.

- Two valleys along y = 0:
  - deep valley at x ≈ −1.04, f ≈ −0.12;
  - shallow valley at x ≈ 0.95, f ≈ 0.12;
  - ridge (saddle) between them at x ≈ 0.09, f ≈ 0.36.
- Gradient: ∇f = (1.4·x·(x² − 1) + 0.12, 0.5·y).
- Update rule: p ← p − η·∇f(p), with η the step size.
- Paths (all checked):

| Start | η | Result |
|---|---|---|
| (−1.6, 1.5) | 0.15 | slow, steady slide into the deep valley |
| (−1.6, 1.5) | 0.3 | first step overshoots a little, then settles in the deep valley within ~5 steps |
| (−1.6, 1.5) | 0.55 | the first step jumps over the ridge and lands in the **shallow** valley. "Too big a step lands you somewhere worse." |
| (1.6, 1.5) | 0.3 | ends in the shallow valley, f ≈ 0.12: a **local minimum**, not the lowest point |

- 1-D warm-up on f(x) = x², starting at x = 1.6:

| η | Behaviour |
|---|---|
| 0.1 | crawls: 1.28, 1.02, 0.82, … |
| 0.45 | nearly there in two steps |
| 0.9 | bounces from side to side: −1.28, 1.02, −0.82, … |
| 1.05 | blows up: −1.76, 1.94, −2.13, … |

## Colour ledger

| Thing | Colour |
|---|---|
| Landscape, low to high | `BLUE_E` → `TEAL` → `YELLOW` (by height) |
| The walker (ball/dot) and its path | `ACCENT_2` (orange) |
| Gradient arrow ∇f (uphill) | `BAD` (red) |
| Step arrow −η∇f (downhill) | `GOOD` (green) |
| Step size η, its slider/number | `ACCENT` (blue) |
| Contour lines | `MUTED`; the lowest contours slightly brighter |
| Text | `FG`; captions in the footer, as in `order_matters.py` |

## Beats

`Beat` = `TimedScene` with captions (2D). `Beat3D` = `TimedScene` + `ThreeDScene`,
with captions and headings pinned to the screen.

| # | Scene | Kind | ~s | On screen (region) and motion | Narration (spoken) |
|---|---|---|---|---|---|
| 1 | `Foggy` | 2D | 12 | Side view of a hilly curve (main). Blob stands on it; a grey fog band hides all but a short stretch around Blob. | "You're on a hillside in thick fog, and you want to reach the bottom. You can't see the valley. You can only feel the ground under your feet." |
| 2 | `FeelTheSlope` | 2D | 14 | The fog stays. Tangent line at Blob's feet (ACCENT_2). Slope number shown live (`DecimalNumber`) as Blob shuffles a little. | "But that's enough. Feel which way the ground tilts, and take a step downhill." |
| 3 | `OneDimension` | 2D | 16 | Fog gone. Parabola y = x² with axes (main). The dot takes 6 steps with η = 0.45; each step shows a short tangent, then a jump. The rule x ← x − η·f′(x) is written top-right. | "In maths: the slope is the derivative. Step against it, by a small amount called the step size. Repeat." |
| 4 | `StepSize` | 2D | 20 | Three small parabola panels side by side (left/main/right): η = 0.1 crawls, η = 0.9 bounces, η = 1.05 flies off. Each panel has its η label in blue. | "The step size matters. Too small and you crawl. Too big and you bounce from side to side, or fly off completely." |
| 5 | `Landscape` | 3D | 14 | The surface rises from flat (`Create`, then height grows). The camera slowly orbits. Heading "Two directions" pinned at the top. | "Real problems have more than one direction to walk in. Here, the ground is a whole landscape." |
| 6 | `Gradient` | 3D | 16 | The ball at (−1.6, 1.5). Red arrow ∇f points uphill along the surface; green arrow points the opposite way. Formula ∇f = (∂f/∂x, ∂f/∂y) pinned top-right. | "The slope in every direction at once is called the gradient. It points straight uphill, so we step the opposite way." |
| 7 | `Descent3D` | 3D | 16 | η = 0.3: the ball hops step by step, leaving an orange trail on the surface, into the deep valley. The camera eases round to follow. | "Step, recompute, step again. The ball slides into the valley." |
| 8 | `ContourMap` | 2D | 16 | Flat contour map of the same landscape (main), with the same path drawn over it. The gradient arrow at one point crosses the contour lines at a right angle. | "Seen from above, the landscape becomes a contour map. The gradient always crosses the contour lines at right angles: the steepest way up." |
| 9 | `TooBig` | 2D | 14 | Same map. The path with η = 0.55 starts at the same point, leaps over the ridge on step 1, and settles in the shallow valley. A blue η = 0.55 label next to it. | "With too big a step, the first jump clears the ridge, and we settle in the wrong valley." |
| 10 | `LocalMinimum` | 3D | 16 | Back to 3D. Start at (1.6, 1.5) with η = 0.3: the ball rolls into the shallow valley and stops. The camera pulls back to show the deeper valley next door; a small "lowest point" marker blinks there. | "And start in the wrong place, and you get stuck in a dip that isn't the lowest point. Gradient descent only knows what's under its feet." |
| 11 | `Takeaway` | 2D | 12 | The rule p ← p − η∇f centred (main), coloured per the ledger. Blob, happy, at bottom-left. One small line under the rule: "This is how neural networks learn." | "Feel the slope, step downhill, repeat. That one rule is how most of machine learning learns." |

Total ≈ 166 s (≈ 2:45). Captions: one line each, at most 70 characters, so
the longer narration lines above get split into several captioned lines when
coded. Spoken text spells symbols out ("eta", "f prime"); captions show
symbols.

## New things this video tests

- 3D: `ThreeDScene` combined with our kit, `Surface` coloured by height,
  camera orbit and `move_camera`, fixed-in-frame text, objects on a surface
  (path, ball, arrows).
- Our own contour lines (marching squares, ~40 lines, no new packages:
  matplotlib and scikit-image aren't installed, and we won't install them).
  If it works well, it goes into `manim_kit.py` as `contour_lines()`.
- Same maths drawn in 2D and in 3D, which must line up (same path and points).
- Mixing 2D and 3D beats in one joined video.

## Tooling gaps (expected)

- `check_layout.py` checks 2D boxes. For 3D beats it can only check the
  pinned text (headings, captions, formulas), not the surface itself. For 3D
  beats we rely on frame review, and I'll make the checker skip 3D objects
  instead of reporting false errors.

## Render cost

Measured with the probe:

| Quality | Render time per second of 3D video | The four 3D beats (~62 s) |
|---|---|---|
| 480p15 | ~9 s | ~9 min per full pass |
| 1080p60 | ~38 s | ~40 min, once at the end |

2D beats are fast. This is workable as it is, so no renderer switch is
planned. If iteration gets painful, lower the surface resolution while
drafting (e.g. 20×20) and raise it for the final render.

## As built (changes from the plan)

- **Starts mirrored to the near side:** (−1.6, −1.5) and (1.6, −1.5). The
  landscape is symmetric in y, so the checked paths are the same with y
  flipped. From the camera angle, the planned starts were on the far side.
- **`OneDimension` uses η = 0.2,** not 0.45: six visible steps instead of two.
- **`ContourMap`** shows the gradient-vs-contour right angle at an empty
  spot (0.9, 0.55), not on the path. On the path, uphill points straight back
  along it.
- **The map is a heightmap image** in the landscape colours, with dark contour
  lines on top. The ledger said `MUTED` lines; dark lines read better on
  colour.
- **Beat lengths cut to fit:** total 2:12 instead of 2:46. Several beats had
  5–9 s of silent hold.
- **No headings.** `Landscape`'s "A whole landscape" was cut: once zoomed
  in, the orbiting landscape rose into it. Pinned text and a moving 3D camera
  need checking at every point of the orbit, not just the ends.
